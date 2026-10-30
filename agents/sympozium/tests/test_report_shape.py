"""The shape a reporter's prompt declares, held to the hook that renders it.

A report has no schema: its shape exists only as prose in a prompt, and the emoji
it carries is computed from that prose by `Verdict`. So the two halves are
asserted together here rather than reviewed — a renamed section is a dirty run
posted with a clean verdict, and nothing else in this repository would notice.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_HOOK = _ROOT / "prompts" / "delivery" / "hook.md"
_PROJECTS = _ROOT / "projects" / "homelab-ops" / "prompts"

_spec = importlib.util.spec_from_file_location(
    "deliver_slack", _ROOT / "files" / "deliver-slack.py"
)
assert _spec and _spec.loader
deliver = importlib.util.module_from_spec(_spec)
sys.modules["deliver_slack"] = deliver
_spec.loader.exec_module(deliver)

# The one budget, stated once in the contract every reporter receives.
CAP = 250

_FORMAT = re.compile(r"Write exactly once.*?(?=\n## Delivery|\Z)", re.DOTALL)
_LABEL = re.compile(r"\*\*([A-Za-z][A-Za-z ]{0,20}?):?\*\*")
_ANY_CAP = re.compile(r"at most (\d+) words")


def reporters() -> list[Path]:
    """Every persona prompt that posts to a channel: it carries the token."""
    found = [p for p in sorted(_PROJECTS.glob("*_system.md")) if "{{ DELIVERY }}" in p.read_text()]
    assert found, "no reporter prompt carries {{ DELIVERY }}, so the scan found nothing"
    return found


def labels(prompt: Path) -> list[str]:
    block = _FORMAT.search(prompt.read_text())
    assert block, f"{prompt.name} has no `Write exactly once` format block"
    return [m.group(1).strip().lower() for m in _LABEL.finditer(block.group(0))]


def test_the_shared_contract_states_the_shape_and_the_cap():
    hook = _HOOK.read_text()
    assert "### Shape" in hook
    assert "at most 250 words" in hook
    # The two rules that answer the measured failures: one bullet per condition
    # across machines, and a stated drop order so a cap never eats a finding.
    assert "one bullet per machine per check" in hook
    assert "Never drop a finding" in hook
    # A failed check is a gap, not a clause in the outcome sentence.
    assert "(*) `pg_get_top_queries` failed" in hook
    assert "No gap: no `(*)` and no footnote." in hook


def test_every_reporter_receives_the_shared_shape_and_raises_no_other_cap():
    hook = _HOOK.read_text()
    for prompt in reporters():
        text = prompt.read_text()
        assert "{{ DELIVERY }}" in text, prompt.name
        for cap in _ANY_CAP.findall(text):
            assert int(cap) <= CAP, f"{prompt.name} asks for {cap} words against a {CAP} cap"
    assert _ANY_CAP.search(hook)


def test_every_reporter_leads_with_its_outcome():
    for prompt in reporters():
        assert labels(prompt)[0] == "status", f"{prompt.name} does not open on Status"


def test_every_section_label_is_one_the_verdict_knows():
    known = deliver.Verdict.FINDING_SECTIONS | deliver.Verdict.CLEAN_SECTIONS
    for prompt in reporters():
        unknown = sorted(set(labels(prompt)) - known)
        assert not unknown, f"{prompt.name} writes sections nothing classifies: {unknown}"


def test_no_label_is_both_a_finding_and_clean():
    assert not deliver.Verdict.FINDING_SECTIONS & deliver.Verdict.CLEAN_SECTIONS


def test_a_populated_finding_section_warns_and_a_clean_one_does_not():
    for prompt in reporters():
        for label in labels(prompt):
            body = deliver.Mrkdwn.convert(f"**{label.title()}:** 3 pending")
            expected = (
                deliver.Verdict.WARNING
                if label in deliver.Verdict.FINDING_SECTIONS
                else deliver.Verdict.OK
            )
            assert deliver.Verdict.classify(body) == expected, f"{prompt.name}: {label}"


def test_the_report_that_mandated_a_dump_now_mandates_grouping():
    """`endpoint-warden` reached 32 bullets for four conditions.

    Its format said "Report every line the tool printed ... none of them
    summarised away", so the length was instructed rather than chosen. A cap
    beside that sentence would be a rule the model cannot satisfy.
    """
    text = (_PROJECTS / "endpoint_warden_system.md").read_text()
    assert "summarised away" not in text
    assert "one bullet per distinct condition" in text
