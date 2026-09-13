"""Tests for the Slack delivery hook's Markdown conversion.

This is the only pytest suite under agents/sympozium/, and it exists for one
reason: files/deliver-slack.py is the only *code* in this sub-project that runs
in production. Everything else here is YAML and prompt text, gated only by the
render since scripts/validate.py was removed. A regex pipeline that rewrites
every report before it reaches a human is worth assertions rather than review.

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


def test_table_header_row_is_not_taken_for_the_agent_header():
    """A report opening with a table kept its pipes and lost its column names.

    The prompts forbid `|` tables and the model emits them anyway - the oracle
    sent a 14-row one. A table's header row has more than two pipes, so the
    two-pipe rule dropped it, leaving a headless table and nothing saying a line
    had gone. A pipe-delimited row is never the agent header.
    """
    body = "| Node | Disk |\n|---|---|\n| amd-1 | 34% |"
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
    monkeypatch.setattr(deliver.urllib.request, "urlopen", lambda *a, **k: _Response({"ok": True}))
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


# -- Verdict ----------------------------------------------------------------
#
# The emoji on the Status line is computed here, never written by the model.
# These are the shapes the personas actually emit, taken from live reports.

STATUS = deliver.Verdict


def test_ok_when_every_section_is_a_nothing_form():
    body = (
        "*Status:* all clear.\n\n*New:* Nothing new.\n\n*Still firing:* 4, all chronic:\n"
        "- CPUThrottlingHigh, chronic, on x\n- InfoInhibitor, chronic, on data\n\n"
        "*Resolved:* Nothing resolved.\n\n*Filling up:* Nothing above the warn threshold."
    )
    assert STATUS.classify(body) == STATUS.OK


def test_chronic_alerts_alone_do_not_warn():
    """chronic fires permanently here; a run whose only continuing items are
    chronic is a clean run, not a warning."""
    body = "*Status:* all clear.\n\n*Still firing:* Nothing new.\n- Watchdog, chronic"
    assert STATUS.classify(body) == STATUS.OK


def test_a_real_entry_inside_still_firing_warns():
    """The 2026-09-13 shape: the real finding sat inside Still firing, marked
    class `-` rather than `chronic`."""
    body = (
        "*Status:* 0 new, 5 still firing.\n\n*New:* Nothing new.\n\n"
        "*Still firing:* 5 alerts:\n"
        "- PrometheusOperatorRejectedResources (warning), class -\n"
        "- CPUThrottlingHigh, chronic x2\n- Watchdog, chronic\n\n"
        "*Resolved:* Nothing resolved."
    )
    assert STATUS.classify(body) == STATUS.WARNING


def test_a_populated_finding_section_warns():
    body = (
        "*Status:* one finding.\n\n*Findings:* amd-1 - kernel drift - upgrade.\n\n"
        "*Maintenance:* Nothing to act on."
    )
    assert STATUS.classify(body) == STATUS.WARNING


def test_drift_that_is_not_a_nothing_form_warns():
    body = "*Status:* 1 not synced.\n\n*Drift:* app, sync=Unknown.\n\n*Escalating:* growing."
    assert STATUS.classify(body) == STATUS.WARNING


def test_error_literal_beats_everything():
    body = "*Status:* degraded.\n\n*Postgres:* ERROR: archiver query failed.\n\n*Cache:* healthy."
    assert STATUS.classify(body) == STATUS.ERROR


def test_plain_colon_labels_are_read():
    """The un-bolded form converts nothing and must still be classified."""
    body = "Status: all clear.\nNew: Nothing new.\nFilling up: Nothing above the warn threshold."
    assert STATUS.classify(body) == STATUS.OK


def test_bold_labels_without_a_colon_are_read():
    body = "*Backups*\nNothing inside the window.\n\n*Expiring*\nNothing inside the window."
    assert STATUS.classify(body) == STATUS.OK


def test_prose_with_a_colon_is_not_a_section():
    """A sentence containing a colon must not start a phantom section."""
    body = "*Status:* healthy.\n\nNote that this sentence happens to contain: a colon and more."
    assert STATUS.classify(body) == STATUS.OK


def test_prefix_puts_the_emoji_on_the_status_line():
    body = "*Status:* all clear.\n\n*New:* Nothing new."
    assert STATUS.prefix(body) == f"{STATUS.OK} *Status:* all clear.\n\n*New:* Nothing new."


def test_prefix_adds_an_emoji_when_no_status_section_exists():
    body = "Just prose, then a section.\n\n*New:* Nothing new."
    assert STATUS.prefix(body).startswith(STATUS.OK + " ")


def test_prefix_on_an_empty_body_is_just_the_emoji():
    assert STATUS.prefix("") == STATUS.OK


def test_empty_result_placeholder_wears_no_verdict(monkeypatch):
    """A run with no text has no report; the placeholder must not get a tick."""
    sent = {}
    monkeypatch.setattr(
        deliver.Slack, "post", lambda self, text: sent.update(text=text) or {"ok": True}
    )
    monkeypatch.setenv("SLACK_CHANNEL", "#c")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "tok")
    monkeypatch.setenv("AGENT_LABEL", "A | b | c")
    monkeypatch.setenv("AGENT_RESULT", "   ")
    assert deliver.main() == 0
    assert STATUS.OK not in sent["text"]
    assert STATUS.WARNING not in sent["text"]
    assert STATUS.ERROR not in sent["text"]


def test_verdict_is_on_the_real_report(monkeypatch):
    """A real db-steward report, end to end, with its computed verdict."""
    sent = {}
    monkeypatch.setattr(
        deliver.Slack, "post", lambda self, text: sent.update(text=text) or {"ok": True}
    )
    monkeypatch.setenv("SLACK_CHANNEL", "#c")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "tok")
    monkeypatch.setenv("AGENT_LABEL", "DB Steward | homelab-ops | heartbeat, daily")
    monkeypatch.setenv(
        "AGENT_RESULT",
        "**Status:** healthy\n\n**Postgres:** healthy\n\n**Room to grow:** Nothing above the warn threshold.",
    )
    assert deliver.main() == 0
    assert sent["text"].startswith(f"*DB Steward | homelab-ops | heartbeat, daily*\n\n{STATUS.OK} ")


# -- Failed runs ------------------------------------------------------------

# The LiteLLM 429 that reached #monitoring-ai-alerts on 2026-09-13 as
# `sre-sentinel-schedule-70`, truncated by the controller exactly as here.
LLM_429 = (
    'OpenAI API error (HTTP 429): POST "http://datahub-local-core-data-litellm.data'
    '.svc.cluster.local:4000/v1/chat/completions": 429 Too Many Requests '
    '{"message":"litellm.RateLimitError: RateLimitError: OpenAIException - 5-hour '
    "usage limit reached. Resets in 42min. Received Model Group="
    "opencode-go/deepseek-v4.1-flash\nError doin..."
)


def test_a_failed_run_does_not_wear_a_green_check():
    """The real one: a failed run's error read as a clean report.

    Nothing in the text says failure - `Verdict` found no `ERROR:` literal and
    no populated finding section, so the run that produced no report at all was
    posted under a tick. The exit code is the only thing that knows.
    """
    text = deliver.Report(
        LLM_429, "SRE Sentinel | homelab-ops | scheduled", "1", "run-70"
    ).message()
    assert STATUS.OK not in text
    assert text.startswith("*SRE Sentinel | homelab-ops | scheduled*\n\n" + STATUS.ERROR)
    assert "Run failed (exit 1)" in text
    assert "run-70" in text


def test_a_failed_run_quotes_its_error_verbatim():
    """The error is evidence, not Markdown: the passes must not touch it."""
    raw = "boom: <nil> **not bold** [x](y) ## nope"
    text = deliver.Report(raw, "A | b | c", "1").message()
    assert raw in text
    assert text.count("```") == 2


def test_a_fence_in_the_error_cannot_close_the_block():
    text = deliver.Report("before\n```\nafter", "A | b | c", "1").message()
    assert text.count("```") == 2
    assert "after" in text


def test_a_long_error_is_truncated():
    text = deliver.Report("x" * 5000, "A | b | c", "1").message()
    assert len(text) < 2000
    assert text.rstrip("`\n").endswith("...")


def test_a_failed_run_with_no_detail_still_says_so():
    text = deliver.Report("", "A | b | c", "1", "run-9").message()
    assert STATUS.ERROR in text
    assert deliver.Report.NO_DETAIL in text
    assert deliver.Report.EMPTY not in text
    assert "run-9" in text


def test_exit_code_zero_is_an_ordinary_report():
    text = deliver.Report("**Status:** healthy", "A | b | c", "0").message()
    assert text.endswith(f"{STATUS.OK} *Status:* healthy")


def test_a_missing_exit_code_is_a_success():
    """Nothing here may start calling every run a failure if the var goes away."""
    assert not deliver.Report("**Status:** healthy", "A | b | c").failed


def test_failed_run_end_to_end(monkeypatch):
    """The hook runs on a failed run - postRun is best-effort - so main() sees it."""
    sent = {}
    monkeypatch.setattr(
        deliver.Slack, "post", lambda self, text: sent.update(text=text) or {"ok": True}
    )
    monkeypatch.setenv("SLACK_CHANNEL", "#c")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "tok")
    monkeypatch.setenv("AGENT_LABEL", "SRE Sentinel | homelab-ops | scheduled")
    monkeypatch.setenv("AGENT_RESULT", LLM_429)
    monkeypatch.setenv("AGENT_EXIT_CODE", "1")
    monkeypatch.setenv("AGENT_RUN_ID", "homelab-ops-sre-sentinel-schedule-70")

    # Delivery itself worked, so the hook must not report a PostRunFailed.
    assert deliver.main() == 0
    assert STATUS.ERROR in sent["text"]
    assert STATUS.OK not in sent["text"]
    assert "homelab-ops-sre-sentinel-schedule-70" in sent["text"]
