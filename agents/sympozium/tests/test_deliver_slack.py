"""Tests for the Slack delivery hook's Markdown conversion.

This is the first pytest suite under agents/sympozium/, and it exists for one
reason: files/deliver-slack.py is the only *code* in this sub-project that runs
in production. Everything else here is YAML and prompt text, checked by
scripts/validate.py and by `helm template`. A regex pipeline that rewrites every
report before it reaches a human is worth assertions rather than review.

Several cases below are real reports, named as such. They are the ones a rewrite
has to keep passing.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import urllib.error
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "files" / "deliver-slack.py"
_spec = importlib.util.spec_from_file_location("deliver_slack", _PATH)
assert _spec and _spec.loader
deliver = importlib.util.module_from_spec(_spec)
sys.modules["deliver_slack"] = deliver
_spec.loader.exec_module(deliver)


# -- HTML -------------------------------------------------------------------


def test_unclosed_tag_keeps_its_text():
    """The real gitops-auditor report that reached #monitoring-ai-drift.

    The obvious fix, `s/<[^>]*>//g`, matches from `<font` to the `>` of
    `</font>` and deletes the sentence between them - the line came out empty,
    losing the run's only finding. The text must survive the tag.
    """
    raw = (
        "*Status:* synced\n\n"
        '<font face="monospace"**Drift:** Everything is Synced and Healthy.</font>\n\n'
        "**Escalating**<br>\nNothing new."
    )
    got = deliver.Mrkdwn.convert(raw)
    assert "Everything is Synced and Healthy." in got
    assert "<font" not in got and "</font>" not in got and "<br>" not in got
    assert "*Drift:*" in got


def test_br_becomes_a_newline():
    assert deliver.Mrkdwn.convert("one<br>two") == "one\ntwo"
    assert deliver.Mrkdwn.convert("one<br />two") == "one\ntwo"


@pytest.mark.parametrize(
    "line",
    [
        "Disk headroom is <70% on all nodes.",
        "Cache age <1h on every node.",
        "A 5 < 7 comparison must survive.",
    ],
)
def test_comparisons_are_not_tags(line):
    """A tag-shaped regex has to be talked out of these; a parser does not."""
    assert deliver.Mrkdwn.convert(line) == line


# -- Code spans -------------------------------------------------------------


def test_code_spans_are_not_rewritten():
    """The sed pipeline could not do this, and it is the main reason for Python.

    A report quoting a PromQL expression or a metric name must reach Slack
    unchanged; converting Markdown inside it corrupts the one thing the reader
    is meant to copy.
    """
    raw = "Use `increase(m[1h])` and `a**b**c` and `[x](y)` verbatim."
    got = deliver.Mrkdwn.convert(raw)
    assert "`increase(m[1h])`" in got
    assert "`a**b**c`" in got
    assert "`[x](y)`" in got


def test_conversion_still_applies_outside_code():
    got = deliver.Mrkdwn.convert("**bold** and `**not bold**` and **bold again**")
    assert got == "*bold* and `**not bold**` and *bold again*"


# -- Inline Markdown --------------------------------------------------------


def test_links_become_angle_bracketed():
    got = deliver.Mrkdwn.convert("See [the notes](https://example.test/a) for detail.")
    assert got == "See <https://example.test/a|the notes> for detail."


def test_bold_and_strikethrough():
    assert deliver.Mrkdwn.convert("**b**") == "*b*"
    assert deliver.Mrkdwn.convert("__b__") == "*b*"
    assert deliver.Mrkdwn.convert("~~s~~") == "~s~"


def test_bare_asterisks_are_left_alone():
    """A lone asterisk is not bold, and must not be paired across a line."""
    assert deliver.Mrkdwn.convert("2 * 3 * 4") == "2 * 3 * 4"


# -- Block structure --------------------------------------------------------


def test_headings_become_bold():
    assert deliver.Mrkdwn.convert("## Findings") == "*Findings*"
    assert deliver.Mrkdwn.convert("###### Deep") == "*Deep*"


def test_heading_containing_bold_does_not_double_up():
    """`## **Drift**` must not end up `**Drift**`, which renders literally."""
    assert deliver.Mrkdwn.convert("## **Drift**") == "*Drift*"


def test_bullets_are_normalised():
    assert deliver.Mrkdwn.convert("* one\n- two\n+ three") == "- one\n- two\n- three"


def test_fences_and_rules_are_dropped():
    raw = "---\n```yaml\nkey: value\n```\n***\ntext"
    assert deliver.Mrkdwn.convert(raw) == "key: value\ntext"


def test_section_labels_are_bolded():
    assert deliver.Mrkdwn.convert("Migration: none required") == "*Migration:* none required"
    assert deliver.Mrkdwn.convert("Backups:") == "*Backups*"


def test_long_sentence_with_colon_is_not_a_label():
    """The 22-character bound is what keeps prose out of the label rule."""
    line = "Note that this particular sentence happens to contain: a colon"
    assert deliver.Mrkdwn.convert(line) == line


# -- Header handling --------------------------------------------------------


def test_model_written_header_is_dropped():
    label = "DB Steward | homelab-ops | heartbeat, daily"
    body = f"*{label}*\n\n*Status:* healthy"
    assert deliver.Report._drop_own_header(body, label) == "*Status:* healthy"


def test_two_pipe_header_is_dropped():
    got = deliver.Report._drop_own_header("Some Agent | team | daily\n\nbody", "Other | x | y")
    assert got == "body"


def test_real_body_is_kept():
    body = "*Status:* healthy\n\n*Postgres:* fine"
    assert deliver.Report._drop_own_header(body, "DB Steward | homelab-ops | daily") == body


# -- Posting ----------------------------------------------------------------


class _Response:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_post_returns_the_parsed_response(monkeypatch):
    monkeypatch.setattr(
        deliver.urllib.request, "urlopen", lambda *a, **k: _Response({"ok": True})
    )
    assert deliver.Slack("tok", "#c").post("text") == {"ok": True}


def test_post_retries_a_5xx_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError("u", 503, "boom", {}, None)
        return _Response({"ok": True})

    monkeypatch.setattr(deliver.urllib.request, "urlopen", fake)
    monkeypatch.setattr(deliver.time, "sleep", lambda _s: None)
    assert deliver.Slack("tok", "#c").post("text") == {"ok": True}
    assert calls["n"] == 2


def test_post_does_not_retry_a_401(monkeypatch):
    """An auth failure is a fact about the request; retrying re-posts nothing."""
    calls = {"n": 0}

    def fake(*_args, **_kwargs):
        calls["n"] += 1
        raise urllib.error.HTTPError("u", 401, "nope", {}, None)

    monkeypatch.setattr(deliver.urllib.request, "urlopen", fake)
    with pytest.raises(urllib.error.HTTPError):
        deliver.Slack("tok", "#c").post("text")
    assert calls["n"] == 1


# -- End to end -------------------------------------------------------------


def test_empty_result_posts_the_placeholder(monkeypatch, capsys):
    sent = {}

    def fake(self, text):
        sent.update(channel=self.channel, text=text)
        return {"ok": True}

    monkeypatch.setattr(deliver.Slack, "post", fake)
    monkeypatch.setenv("SLACK_CHANNEL", "#c")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "tok")
    monkeypatch.setenv("AGENT_LABEL", "A | b | c")
    monkeypatch.setenv("AGENT_RESULT", "   ")

    assert deliver.main() == 0
    assert deliver.Report.EMPTY in sent["text"]
    assert "delivered ok" in capsys.readouterr().out


def test_failed_delivery_exits_nonzero(monkeypatch):
    monkeypatch.setattr(
        deliver.Slack, "post", lambda self, text: {"ok": False, "error": "channel_not_found"}
    )
    monkeypatch.setenv("SLACK_CHANNEL", "#missing")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "tok")
    monkeypatch.setenv("AGENT_LABEL", "A | b | c")
    monkeypatch.setenv("AGENT_RESULT", "body")
    assert deliver.main() == 1


def test_full_report_round_trip(monkeypatch):
    """A real db-steward report, start to finish."""
    sent = {}
    monkeypatch.setattr(
        deliver.Slack, "post", lambda self, text: sent.update(text=text) or {"ok": True}
    )
    monkeypatch.setenv("SLACK_CHANNEL", "#c")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "tok")
    monkeypatch.setenv("AGENT_LABEL", "DB Steward | homelab-ops | heartbeat, daily")
    monkeypatch.setenv(
        "AGENT_RESULT",
        "## Headline\n**Status:** healthy\n\n## Findings\n"
        "- Archiver healthy, `increase(m[1h])=0`\n"
        "- See [notes](https://example.test/n)\n",
    )
    assert deliver.main() == 0
    text = sent["text"]
    assert text.startswith("*DB Steward | homelab-ops | heartbeat, daily*")
    assert "*Headline*" in text
    assert "*Status:* healthy" in text
    assert "`increase(m[1h])=0`" in text
    assert "<https://example.test/n|notes>" in text
    assert "##" not in text and "**" not in text


# -- Structure --------------------------------------------------------------


def test_each_pattern_has_one_owner():
    """The reason for the classes: a reader must not have to guess which pass
    owns a pattern, and the two passes run in a fixed order.
    """
    assert hasattr(deliver.Html, "TAG_START")
    assert hasattr(deliver.Mrkdwn, "BOLD")
    assert not hasattr(deliver.Mrkdwn, "TAG_START")
    assert not hasattr(deliver.Html, "BOLD")
    # Nothing regex-shaped is left loose at module level.
    loose = [n for n, v in vars(deliver).items() if isinstance(v, type(deliver.Html.TAG_START))]
    assert loose == [], f"module-level patterns with no owner: {loose}"
