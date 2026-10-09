"""Guard the one hook registry and its consumers.

The hook used to be decided twice and stored as prose: the curator's judge assigned
one of six hooks, wrote it as the ``Hook: X.`` prefix on ``EXTRA_PROMPT``, and the
post creator then ignored it and re-picked a hook at random. The media decision was
a hand-set sheet column read by nobody's rule. This change makes
``datasets/hook_types.json`` the single list and carries the judge's hook and visual
intent into the queue as columns.

These are structural properties of committed files and exports, so they are asserted
offline. Both copies of every graph are checked -- the exports carry their nodes
twice, at the top level and inside ``activeVersion``.
"""

import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATASETS = BASE / "datasets"
PROMPTS = BASE / "prompts"
WORKFLOWS = BASE / "workflows"

REGISTRY = DATASETS / "hook_types.json"
CURATOR = WORKFLOWS / "content_feed_curator.workflow.json"
CREATOR = WORKFLOWS / "linked_in_post_creator.workflow.json"
SHARING = WORKFLOWS / "linked_in_post_sharing.workflow.json"
STUDIO = WORKFLOWS / "visual_studio.workflow.json"
IMAGE = WORKFLOWS / "linked_in_image_creator.workflow.json"

# The six archetypes that used to live in three places; none of them may be an
# inline enumeration in the prompt any more.
LEGACY_HOOKS = ["CONTRARIAN", "WAR_STORY", "MISCONCEPTION", "TRADE_OFF", "NEWS_REACTION", "HARD_NUMBER"]


def _copies(path):
    data = json.loads(path.read_text())
    yield "top level", data
    yield "activeVersion", data.get("activeVersion") or {"nodes": [], "connections": {}}


def _node(document, name):
    for node in document["nodes"]:
        if node["name"] == name:
            return node
    raise KeyError(name)


def _targets(connections, source):
    return [edge["node"] for branch in (connections.get(source) or {}).get("main", []) for edge in (branch or [])]


def _registry():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _forms():
    forms = set()
    for _, doc in _copies(STUDIO):
        code = _node(doc, "normalize_input")["parameters"]["jsCode"]
        match = re.search(r"const FORCES = \[([^\]]*)\]", code)
        assert match, "normalize_input has no FORCES enum"
        forms |= {x.strip().strip("'\"") for x in match.group(1).split(",") if x.strip()}
    return forms


def test_registry_declares_the_required_hooks():
    reg = _registry()
    hooks = reg["hooks"]
    assert len(hooks) >= 15, "the registry must carry at least fifteen hooks"
    ids = [h["id"] for h in hooks]
    assert len(ids) == len(set(ids)), "hook ids must be unique"
    forms = _forms()
    for hook in hooks:
        assert hook.get("when"), hook["id"]
        assert hook.get("opening"), hook["id"]
        visual = hook["visual"]
        assert visual["form"] in forms, f"{hook['id']} names a form the studio does not accept"
        assert isinstance(visual["motion"], bool)
        assert isinstance(visual["scenes"], int) and visual["scenes"] >= 0
        assert hook.get("image"), hook["id"]


def test_roundup_is_a_multi_scene_motion_hook():
    """The state-of case: a list is one item per scene, animated."""
    roundup = next(h for h in _registry()["hooks"] if h["id"] == "ROUNDUP")
    assert roundup["visual"]["motion"] is True


def test_the_hook_list_is_not_carried_twice():
    motifs = json.loads((DATASETS / "image_motifs.json").read_text(encoding="utf-8"))
    assert "hooks" not in motifs, "the hook map moved to the registry"
    assert "default_hook" not in motifs

    for label, doc in _copies(CREATOR):
        names = {n["name"] for n in doc["nodes"]}
        assert "classify_content" not in names, f"{label}: classify_content must be retired"
        assert "download_post_classify_prompt" not in names
        code = _node(doc, "set_variety_directives")["parameters"]["jsCode"]
        assert "parse_hook_registry" in code, f"{label}: the generator must read the registry"
        assert "classify_content" not in code
        for legacy in ("WAR STORY", "MISCONCEPTION", "TRADE-OFF:"):
            assert legacy not in code, f"{label}: a hardcoded hook archetype remains"


def test_the_judge_reads_the_registry():
    text = (PROMPTS / "curator_judge.md").read_text(encoding="utf-8")
    assert "{{ HOOKS }}" in text, "the judge prompt must be injected the registry"
    for hook in LEGACY_HOOKS:
        if hook == "TRADE_OFF":
            continue  # appears once as the example output value
        assert hook not in text, f"{hook} is inlined in the prompt instead of the registry"


def test_the_curator_carries_hook_and_visual_columns():
    for label, doc in _copies(CURATOR):
        admit = _node(doc, "admit_to_backlog")["parameters"]["jsCode"]
        for column in ("HOOK", "VISUAL_FORM", "ANIMATED", "SCENES"):
            assert f"{column}:" in admit, f"{label}: admit_to_backlog does not emit {column}"
        rows = _node(doc, "build_queue_rows")["parameters"]["jsCode"]
        for column in ("'HOOK'", "'VISUAL_FORM'", "'ANIMATED'", "'SCENES'"):
            assert column in rows, f"{label}: build_queue_rows omits {column}"
        assert "parse_hook_registry" in _node(doc, "parse_judge")["parameters"]["jsCode"]
        assert "parse_hook_registry" in _node(doc, "download_judge_prompt")["parameters"]["workflowInputs"]["value"]["template_vars"]


def test_sharing_drives_the_studio_from_the_row():
    for label, doc in _copies(SHARING):
        studio = _node(doc, "execute_visual_studio")["parameters"]["workflowInputs"]["value"]
        assert "VISUAL_FORM" in studio["FORCE"], label
        assert "SCENES" in studio["SCENES"], label
        left = _node(doc, "switch_post_media")["parameters"]["conditions"]["conditions"][0]["leftValue"]
        assert "ANIMATED" in left, f"{label}: the media switch must read the row's intent"
        assert "POST_MEDIA" in left, f"{label}: a manual override must still win"
        creator = _node(doc, "execute_post_creator")["parameters"]["workflowInputs"]["value"]
        assert "HOOK" in creator, f"{label}: the creator must receive the row's hook"


def test_the_curator_self_heals_unclassified_rows():
    """Rows admitted before the columns existed are re-judged, a bounded number per run."""
    for label, doc in _copies(CURATOR):
        names = {n["name"] for n in doc["nodes"]}
        assert {"select_unclassified_queue", "loop_backfill_queue", "update_backfill_columns"} <= names, label
        assert "parse_hook_registry" in _node(doc, "parse_judge_backfill")["parameters"]["jsCode"], label
        read_targets = [e["node"] for e in doc["connections"]["read_articles_sheet"]["main"][0]]
        assert "select_unclassified_queue" in read_targets, label
        # the backfill loop must close: parse -> update -> loop
        assert "loop_backfill_queue" in _targets(doc["connections"], "update_backfill_columns"), label


def test_image_creator_reads_the_registry_for_the_hook():
    for label, doc in _copies(IMAGE):
        names = {n["name"] for n in doc["nodes"]}
        assert "download_hook_registry" in names, label
        assert "download_hook_registry" in _node(doc, "parse_image_motifs")["parameters"]["jsCode"], label


def test_visual_studio_accepts_a_scene_plan():
    for label, doc in _copies(STUDIO):
        assert "SCENES" in _node(doc, "normalize_input")["parameters"]["jsCode"], label
        assert "req.SCENES" in _node(doc, "build_author_brief")["parameters"]["jsCode"], label
        fields = {f["fieldLabel"] for f in _node(doc, "form_trigger")["parameters"]["formFields"]["values"]}
        assert "SCENES" in fields, f"{label}: the form must speak the same contract"
