#!/usr/bin/env python3
"""Posts one agent run's report to Slack, once.

Runs as a lifecycle.postRun container after the agent finishes. The report
arrives in AGENT_RESULT; the destination and the header come from the env the
chart sets. Nothing here touches Sympozium's event bus, which is the whole
point: every channel sidecar delivers every instance's outbound message, so a
report posted through the bus arrives once per bound persona. See
../MEMORY.md#every-report-arrived-five-times-and-only-one-agent-sent-it

    AGENT_RESULT      the run's own final text (may be empty)
    AGENT_LABEL       "<Agent> | <ensemble> | <cadence>", the header line
    SLACK_CHANNEL     destination, e.g. #monitoring-ai-alerts
    SLACK_BOT_TOKEN   from a Secret, by reference

The prompt asks the model for plain Markdown and this file owns the whole
translation to Slack mrkdwn. That split is deliberate: the model writes the one
notation it already knows, and the conversion is deterministic, testable and
identical for every persona. Asking a 4B model to emit mrkdwn directly did not
hold - `**bold**` and `##` arrived anyway.

Four classes, one job each, so that every pattern belongs to something:

    Html      reduces HTML to the text it wrapped
    Mrkdwn    Markdown -> Slack mrkdwn
    Report    the message body: conversion plus the header rule
    Slack     posts it

`Html.TAG_START` and `Mrkdwn.BOLD` were `TAG_START_RE` and `BOLD_RE` in one flat
namespace, where nothing said which pass owned which pattern - and the two
passes have to run in a fixed order, so that mattered.

Standard library only: the image is a bare python, and a delivery hook that
needs a pip install is a delivery hook that fails on a network blip.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser


class Html:
    """Reduces HTML to the text it wrapped.

    The model is told not to emit HTML at all, and then one report arrived
    carrying `<font face="monospace"**Drift:** ... .</font>` with an unclosed
    tag, which is what this class exists for.
    """

    # An opening or closing tag with its attributes, and no closing `>` -- the
    # `>` is looked for separately so an unterminated tag can be told from a
    # whole one.
    TAG_START = re.compile(
        r"</?[a-zA-Z][a-zA-Z0-9]*"
        r"""(?:\s+[a-zA-Z_:][\w:.-]*(?:\s*=\s*(?:"[^"<>]*"|'[^'<>]*'|[^\s<>"']+))?)*\s*/?"""
    )

    class _Collector(HTMLParser):
        """Keeps the text of every tag it is handed, and <br> as a newline."""

        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.text: list[str] = []

        def handle_starttag(self, tag: str, attrs: object) -> None:
            if tag == "br":
                self.text.append("\n")

        def handle_startendtag(self, tag: str, attrs: object) -> None:
            self.handle_starttag(tag, attrs)

        def handle_data(self, data: str) -> None:
            self.text.append(data)

    @classmethod
    def strip(cls, text: str) -> str:
        """Remove tags, keeping their text and turning <br> into a newline."""
        if "<" not in text:
            return text
        collector = cls._Collector()
        try:
            collector.feed(cls._repair_unclosed(text))
            collector.close()
        except Exception:  # noqa: BLE001 - a parse failure must not lose the report
            return text
        return "".join(collector.text)

    @classmethod
    def _repair_unclosed(cls, text: str) -> str:
        """Delete an opening tag that never closed, keeping the text after it.

        HTMLParser needs this pass and so did the regex it replaced: given
        `<font face="monospace"**Drift:** ... .</font>` both run from `<font`
        to the `>` of the *closing* tag and swallow the sentence between them.
        Here a tag reaches the parser only when its `>` arrives before the next
        `<`; otherwise just the `<name attr=...` prefix is dropped and the text
        it ran into is kept. `<70%` and `5 < 7` match no tag at all.
        """
        out: list[str] = []
        i, end = 0, len(text)
        while i < end:
            if text[i] != "<":
                out.append(text[i])
                i += 1
                continue
            match = cls.TAG_START.match(text, i)
            if not match:
                out.append(text[i])
                i += 1
                continue
            close = text.find(">", match.end())
            nxt = text.find("<", match.end())
            if close != -1 and (nxt == -1 or close < nxt):
                out.append(text[i : close + 1])  # well formed; let the parser strip it
                i = close + 1
            else:
                i = match.end()  # unterminated; drop the tag, keep the text
        return "".join(out)


class Mrkdwn:
    """Converts Markdown to Slack mrkdwn.

    Slack's notation is close enough to Markdown to look interchangeable and is
    not: bold is one asterisk, there are no headings, and a link is
    `<url|text>`. Every difference the model actually produces is handled here.
    """

    # Whole lines that are dropped: a fence renders the report as one grey slab,
    # and a horizontal rule renders as three literal hyphens.
    FENCE = re.compile(r"^\s*```[a-zA-Z0-9]*\s*$")
    RULE = re.compile(r"^\s*([-*_])\s*\1\s*\1[-*_\s]*$")

    # Inline, applied in this order. Links first so a `[text](url)` whose text
    # is bold is not half-rewritten; strikethrough before bold because `~~` is
    # unambiguous; bold last of the three.
    LINK = re.compile(r"\[([^\]]+)\]\(\s*([^)\s]+)[^)]*\)")
    STRIKE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~")
    BOLD = re.compile(r"(?<!\*)\*\*(?=\S)(.+?)(?<=\S)\*\*(?!\*)")
    BOLD_UNDERSCORE = re.compile(r"(?<![_\w])__(?=\S)(.+?)(?<=\S)__(?![_\w])")

    # Block level.
    HEADING = re.compile(r"^\s*#{1,6}\s*(.+?)\s*$")
    BULLET = re.compile(r"^(\s*)[-*+]\s+")
    # A short section label on its own line, or opening a line. Bounded to 22
    # characters so a sentence containing a colon is not taken for a label.
    LABEL_ALONE = re.compile(r"^([A-Z][A-Za-z ]{1,22}):\s*$")
    LABEL_INLINE = re.compile(r"^([A-Z][A-Za-z ]{1,22}):\s+")
    # Collapses the asterisks left when a heading already contained bold:
    # `## **Drift**` would otherwise end up `**Drift**`, which renders literally.
    OVERBOLD = re.compile(r"^\*{2,}([^*]+)\*{2,}$")

    # Code spans are held aside while the inline rules run, then restored
    # verbatim: a report quoting `increase(m[1h])` must reach Slack unchanged,
    # and rewriting Markdown inside it corrupts the one string a reader copies.
    # U+0000 cannot appear in a Slack message, so the sentinel cannot collide
    # with report text.
    CODE = re.compile(r"`[^`]*`")
    SENTINEL = "\x00{}\x00"
    SENTINEL_PATTERN = re.compile(r"\x00(\d+)\x00")

    @classmethod
    def convert(cls, text: str) -> str:
        """Convert a whole Markdown report."""
        lines: list[str] = []
        for raw in Html.strip(text).splitlines():
            if cls.FENCE.match(raw) or cls.RULE.match(raw):
                continue
            line = cls._inline(raw)
            heading = cls.HEADING.match(line)
            if heading:
                line = f"*{heading.group(1)}*"
            else:
                line = cls.BULLET.sub(r"\1- ", line)
                line = cls.LABEL_ALONE.sub(r"*\1*", line)
                line = cls.LABEL_INLINE.sub(r"*\1:* ", line)
            lines.append(cls.OVERBOLD.sub(r"*\1*", line))
        return "\n".join(lines)

    @classmethod
    def _inline(cls, line: str) -> str:
        """Apply the inline rules, leaving anything inside backticks alone."""
        spans: list[str] = []

        def hide(match: re.Match[str]) -> str:
            spans.append(match.group(0))
            return cls.SENTINEL.format(len(spans) - 1)

        line = cls.CODE.sub(hide, line)
        line = cls.LINK.sub(lambda m: f"<{m.group(2)}|{m.group(1)}>", line)
        line = cls.STRIKE.sub(r"~\1~", line)
        line = cls.BOLD.sub(r"*\1*", line)
        line = cls.BOLD_UNDERSCORE.sub(r"*\1*", line)
        return cls.SENTINEL_PATTERN.sub(lambda m: spans[int(m.group(1))], line)


class Report:
    """The message that gets posted: the run's text, converted, under a header."""

    EMPTY = "Error 404: the data is on a coffee break.. ☕☕\U0001f916"

    def __init__(self, result: str, label: str = "") -> None:
        self.result = result
        self.label = label

    def body(self) -> str:
        if not self.result.strip():
            return self.EMPTY
        return self._drop_own_header(Mrkdwn.convert(self.result), self.label)

    def message(self) -> str:
        """The body under the header, which is written here and not by the model.

        The header is the one line that must always be right and every value is
        known exactly, so the model is told not to write one -- and a model that
        writes one anyway must not produce a pair.
        """
        return f"*{self.label}*\n\n{self.body()}" if self.label else self.body()

    @staticmethod
    def _drop_own_header(body: str, label: str) -> str:
        """Drop a header the model wrote, recognised by its two pipes."""
        lines = body.split("\n")
        while lines and not lines[0].strip():
            lines.pop(0)
        if lines:
            first = lines[0].strip().strip("*")
            if first.count("|") >= 2 or first == label.strip():
                lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)
        return "\n".join(lines)


class Slack:
    """Posts one message to chat.postMessage."""

    URL = "https://slack.com/api/chat.postMessage"
    TIMEOUT = 30

    def __init__(self, token: str, channel: str, attempts: int = 3) -> None:
        self.token = token
        self.channel = channel
        self.attempts = attempts

    def post(self, text: str) -> dict:
        """Send `text`, retrying only what is worth retrying.

        A 429 or 5xx is the transport having a bad moment; every other failure
        is a fact about the request, and retrying it posts the same thing again.
        """
        payload = json.dumps({"channel": self.channel, "text": text, "mrkdwn": True}).encode()
        last: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            request = urllib.request.Request(
                self.URL,
                data=payload,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=self.TIMEOUT) as response:
                    return json.loads(response.read().decode())
            except urllib.error.HTTPError as err:
                last = err
                if err.code != 429 and err.code < 500:
                    raise
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
                last = err
            if attempt < self.attempts:
                time.sleep(2**attempt)
        raise SystemExit(f"DELIVERY FAILED: {last}")


def main() -> int:
    report = Report(os.environ.get("AGENT_RESULT", ""), os.environ.get("AGENT_LABEL", ""))
    slack = Slack(os.environ["SLACK_BOT_TOKEN"], os.environ["SLACK_CHANNEL"])

    response = slack.post(report.message())
    print(f"slack response: {json.dumps(response)}")
    if not response.get("ok"):
        # A delivery failure has to be loud: postRun failures are recorded as
        # Conditions on the run, and that is the only place a dropped report
        # leaves a trace.
        print(f"DELIVERY FAILED: {response.get('error', 'unknown')}", file=sys.stderr)
        return 1
    print("delivered ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
