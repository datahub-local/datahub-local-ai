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
CAP = 300

_FORMAT = re.compile(r"Write exactly once.*?(?=\n## Delivery|\Z)", re.DOTALL)
_HEADING = re.compile(r"^## +([A-Za-z][A-Za-z ]{0,20}?)\s*$", re.MULTILINE)
_INLINE_LABEL = re.compile(r"\*\*([A-Za-z][A-Za-z ]{0,20}?):?\*\*")
_ANY_CAP = re.compile(r"at most (\d+) words")


def reporters() -> list[Path]:
    """Every persona prompt that posts to a channel: it carries the token."""
    found = [p for p in sorted(_PROJECTS.glob("*_system.md")) if "{{ DELIVERY }}" in p.read_text()]
    assert found, "no reporter prompt carries {{ DELIVERY }}, so the scan found nothing"
    return found


def formats(prompt: Path) -> str:
    block = _FORMAT.search(prompt.read_text())
    assert block, f"{prompt.name} has no `Write exactly once` format block"
    return block.group(0)


def labels(prompt: Path) -> list[str]:
    """`status` plus the `##` headings, which is the shape the hook renders."""
    return ["status"] + [m.group(1).strip().lower() for m in _HEADING.finditer(formats(prompt))]


def test_the_shared_contract_states_the_shape_and_the_cap():
    hook = _HOOK.read_text()
    assert "### Shape" in hook
    assert "at most 300 words" in hook
    # The three rules that answer the measured failures: one bullet per fact
    # across machines, a stated drop order, and a gap that is not a clause in
    # the outcome sentence.
    assert "one bullet per machine per check" in hook
    assert "Never drop a finding" in hook
    assert "(*) `pg_get_top_queries` failed" in hook
    assert "A footnote exists only when there is a gap" in hook
    assert "never a line saying that nothing was unused" in hook


def test_the_shared_contract_states_the_one_layout():
    hook = _HOOK.read_text()
    assert "Every other section is a `##` heading on its own line, then `- ` bullets" in hook
    assert "One fact, one bullet" in hook
    assert "at most 25" in hook.lower()
    # The marker anchors the footnote block; anywhere else and it truncates a section.
    assert "`(*)` ends the `Status` line and nothing else" in hook
    assert "never paste one over 40" in hook
    # A reading and its action are two bullets once the pair would wrap.
    assert "the reading, then `action:" in hook


def test_every_reporter_receives_the_shared_shape_and_raises_no_other_cap():
    hook = _HOOK.read_text()
    for prompt in reporters():
        text = prompt.read_text()
        assert "{{ DELIVERY }}" in text, prompt.name
        for cap in _ANY_CAP.findall(text):
            assert int(cap) <= CAP, f"{prompt.name} asks for {cap} words against a {CAP} cap"
    assert _ANY_CAP.search(hook)


def test_every_reporter_uses_one_layout():
    """Status is the one label its sentence sits on; every other label is `##`.

    Two conventions in one fleet is the defect this pins: four personas wrote a
    heading and two wrote `**Label:** inline`, so no two reports scanned alike.
    """
    for prompt in reporters():
        block = formats(prompt)
        # The one inline label is Status, and it is the first line of the format.
        assert block.split("\n", 1)[1].startswith("**Status:**"), (
            f"{prompt.name} does not open its format on the Status line"
        )
        inline = {m.group(1) for m in _INLINE_LABEL.finditer(block)}
        assert inline == {"Status"}, f"{prompt.name} writes inline labels: {sorted(inline)}"
        assert _HEADING.search(block), f"{prompt.name} has no ## section"


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
            body = deliver.Mrkdwn.convert(
                f"**Status:** all clear\n\n## {label.title()}\n- 3 pending"
            )
            # `Still firing` is not a finding section by name; it warns by its own
            # rule, which a non-chronic bullet triggers.
            expected = (
                deliver.Verdict.WARNING
                if label in deliver.Verdict.FINDING_SECTIONS or label == "still firing"
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
