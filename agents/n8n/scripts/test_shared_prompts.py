"""Guard the prompt block both lanes share.

The AI-speak list is one file, ``prompts/ai_speak.md``, fetched by both lanes and injected into each
lane's own rules file. The alternative — the list copied into two rules files — is the shape that
drifts, and this repository has already paid for that class once: a banned-word list a gate enforced
while the drafter read a different one cost five drafts and 3m44s on 2026-09-30.

The list is also the reason the "banned as filler, allowed when it names the subject" clause is
pinned here: a list that bans a word in its only legitimate use is a rule no draft can satisfy, and
that has cost runs in both lanes since.
"""

import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
PROMPTS = BASE / "prompts"
WORKFLOWS = BASE / "workflows"

SHARED = PROMPTS / "ai_speak.md"

# lane export -> (its rules file, the node that fetches that file)
LANES = {
    "article_creator.workflow.json": ("article_writer_system.md", "download_system_prompt"),
    "linked_in_post_creator.workflow.json": ("linkedin_post_rules.md", "download_post_rules_prompt"),
}

PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Z_]+)\s*\}\}")
VAR_KEY_RE = re.compile(r'"([A-Z_]+)":')

# Distinctive enough that their presence in a prompt means the list was copied back in.
TELLTALES = ("delve", "tapestry", "synergy")


def test_the_shared_block_is_one_file():
    text = SHARED.read_text(encoding="utf-8")
    assert "AI-speak" in text and "Robotic scaffolding" in text, "the block lost one of its halves"
    assert "names the subject" in text, (
        "the filler-versus-names-the-subject rule is gone, so a listed word is banned in its only "
        "legitimate use"
    )


def test_every_lane_carries_the_shared_block_and_supplies_it():
    for export, (rules_name, fetch) in LANES.items():
        rules = (PROMPTS / rules_name).read_text(encoding="utf-8")
        assert "{{ AI_SPEAK }}" in rules, f"{rules_name} does not carry the shared block"
        node = {n["name"]: n for n in json.loads((WORKFLOWS / export).read_text(encoding="utf-8"))["nodes"]}[fetch]
        value = node["parameters"]["workflowInputs"]["value"]
        assert value["template_name"] == f"prompts/{rules_name}", export
        declared = set(PLACEHOLDER_RE.findall(rules))
        supplied = set(VAR_KEY_RE.findall(value["template_vars"]))
        assert supplied == declared, f"{export}: {supplied ^ declared}"


def test_no_prompt_restates_the_list():
    """A second copy of a banned word is a second list to keep in step."""
    for path in sorted(PROMPTS.glob("*.md")):
        if path.name == SHARED.name:
            continue
        text = path.read_text(encoding="utf-8")
        for word in TELLTALES:
            assert word not in text, f"{path.name} restates the banned list ({word})"
