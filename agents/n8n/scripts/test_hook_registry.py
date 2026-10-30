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
import shutil
import subprocess
from pathlib import Path

import pytest

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
        assert "motion" not in visual, f"{hook['id']} declares a motion flag; media is always animated"
        assert isinstance(visual["scenes"], int) and visual["scenes"] >= 0
        assert hook.get("image"), hook["id"]


def test_registry_has_no_template_placeholder():
    """DownloadTemplate scans the whole file for doubled curly braces and demands a
    variable for each, even in a comment - a data file is fetched with empty vars."""
    assert "{{" not in REGISTRY.read_text(encoding="utf-8")


def test_every_admitted_row_is_animated():
    """The media is always animated; a still is only the visual author's fallback.

    The judge used to return a ``motion`` flag and the registry declared a per-hook
    default, so a static row was a classification outcome. Animated is now
    unconditional: the curator writes ``POST_MEDIA=ANIMATED`` for every admitted row
    and nothing reads a motion flag. A hand-edited ``STATIC`` cell still overrides,
    which is what keeps the still path reachable when an animation cannot be produced.
    """
    for label, doc in _copies(CURATOR):
        judge = _node(doc, "parse_judge")["parameters"]["jsCode"]
        backfill = _node(doc, "parse_judge_backfill")["parameters"]["jsCode"]
        admit = _node(doc, "admit_to_backlog")["parameters"]["jsCode"]
        assert "visual_motion" not in judge, f"{label}: parse_judge still reads a motion flag"
        assert "motion" not in judge, f"{label}: parse_judge still reads a motion flag"
        assert "motion" not in backfill, f"{label}: parse_judge_backfill still reads a motion flag"
        assert "POST_MEDIA: 'ANIMATED'" in admit, f"{label}: admit_to_backlog does not force ANIMATED"
        assert "POST_MEDIA: 'ANIMATED'" in backfill, f"{label}: backfill does not force ANIMATED"

    reg = _registry()
    for hook in reg["hooks"]:
        assert "motion" not in hook["visual"], f"{hook['id']} still declares a motion flag"

    prompt = (PROMPTS / "curator_judge.md").read_text(encoding="utf-8")
    assert '"motion"' not in prompt, "the judge prompt still asks for a motion flag"


def test_the_form_vocabulary_is_one_file():
    """The studio enum, the curator's two FORMS arrays and ``prompts/visual_forms.md``
    are one vocabulary; a value added to one and not the others is silently clamped."""
    text = (PROMPTS / "visual_forms.md").read_text(encoding="utf-8")
    defined = set(re.findall(r"^- `([a-z]+)`: .+", text, re.MULTILINE))
    assert defined, "the vocabulary file defines no forms"
    forms = _forms()
    assert forms - {"auto"} == defined, f"studio enum {sorted(forms)} vs vocabulary {sorted(defined)}"
    for label, doc in _copies(CURATOR):
        for name in ("parse_judge", "parse_judge_backfill"):
            code = _node(doc, name)["parameters"]["jsCode"]
            match = re.search(r"const FORMS = \[([^\]]*)\]", code)
            assert match, f"{label}: {name} has no FORMS list"
            listed = {x.strip().strip("'\"") for x in match.group(1).split(",") if x.strip()}
            assert listed == forms, f"{label}: {name} FORMS differ from the studio enum"


def test_the_judge_selects_from_the_vocabulary():
    """The judge overrides a hook's default form, so it must read the same definitions
    the composer builds from; both judge prompts carry the fetched file as ``{{ FORMS }}``."""
    prompt = (PROMPTS / "curator_judge.md").read_text(encoding="utf-8")
    assert "{{ FORMS }}" in prompt, "the judge prompt is not injected the vocabulary"
    for label, doc in _copies(CURATOR):
        for name in ("download_judge_prompt", "download_judge_prompt_backfill"):
            value = _node(doc, name)["parameters"]["workflowInputs"]["value"]["template_vars"]
            assert "download_visual_forms" in value and "FORMS" in value, f"{label}: {name}"


def test_a_benchmark_and_a_cost_plot_a_chart():
    by_id = {h["id"]: h for h in _registry()["hooks"]}
    for hook in ("BENCHMARK", "COST"):
        assert by_id[hook]["visual"]["form"] == "chart", hook


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
        for column in ("HOOK", "VISUAL_FORM", "POST_MEDIA", "SCENES"):
            assert f"{column}:" in admit, f"{label}: admit_to_backlog does not emit {column}"
        rows = _node(doc, "build_queue_rows")["parameters"]["jsCode"]
        for column in ("'HOOK'", "'VISUAL_FORM'", "'POST_MEDIA'", "'SCENES'"):
            assert column in rows, f"{label}: build_queue_rows omits {column}"
        assert "parse_hook_registry" in _node(doc, "parse_judge")["parameters"]["jsCode"]
        assert "parse_hook_registry" in _node(doc, "download_judge_prompt")["parameters"]["workflowInputs"]["value"]["template_vars"]


def test_sharing_drives_the_studio_from_the_row():
    for label, doc in _copies(SHARING):
        studio = _node(doc, "execute_visual_studio")["parameters"]["workflowInputs"]["value"]
        assert "VISUAL_FORM" in studio["FORCE"], label
        assert "SCENES" in studio["SCENES"], label
        left = _node(doc, "switch_post_media")["parameters"]["conditions"]["conditions"][0]["leftValue"]
        assert "POST_MEDIA" in left, f"{label}: the media switch must read the row's POST_MEDIA"
        assert "item.json.ANIMATED" not in left, f"{label}: POST_MEDIA is the one media column now"
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


def _run_selector(document, rows):
    """Execute the committed selector's jsCode against a fixture of sheet rows.

    The node logs a summary, so console.log is redirected before the result is written:
    a stray line on stdout would be parsed as the answer.
    """
    code = _node(document, "select_unclassified_queue")["parameters"]["jsCode"]
    script = (
        "console.log = (...a) => console.error(...a);\n"
        "const ROWS = JSON.parse(process.argv[1]);\n"
        "const $input = { all: () => ROWS.map((json) => ({ json })) };\n"
        "function __n8n() {\n" + code + "\n}\n"
        "process.stdout.write(JSON.stringify(__n8n()));\n"
    )
    done = subprocess.run(
        ["node", "-e", script, json.dumps(rows)], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr.strip()[:400]
    return [item["json"] for item in json.loads(done.stdout)]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is required to run the selector")
def test_the_self_heal_classifies_a_hand_queued_row_too():
    """ORIGIN is not a reason to leave a queued row without a hook.

    Row 126 of ``content_queue`` was hand-queued with ``HOOK``, ``VISUAL_FORM``,
    ``POST_MEDIA`` and ``SCENES`` all blank, and the selector filtered on
    ``ORIGIN === 'AUTO'``: it emitted nothing, ``loop_backfill_queue`` never executed,
    and the row would have published a still with no opening hook (2026-10-30).
    """
    rows = [
        {"row_number": 1, "URL": "u-auto", "STATUS": "QUEUE", "ORIGIN": "AUTO", "HOOK": ""},
        {"row_number": 2, "URL": "u-manual", "STATUS": "QUEUE", "ORIGIN": "MANUAL", "HOOK": ""},
        {"row_number": 3, "URL": "u-done", "STATUS": "QUEUE", "ORIGIN": "AUTO", "HOOK": "BENCHMARK"},
        {"row_number": 4, "URL": "u-pub", "STATUS": "PUBLISHED", "ORIGIN": "AUTO", "HOOK": ""},
        {"row_number": 5, "URL": "u-expired", "STATUS": "EXPIRED", "ORIGIN": "MANUAL", "HOOK": ""},
    ]
    for label, doc in _copies(CURATOR):
        got = _run_selector(doc, rows)
        assert [r["row_number"] for r in got] == [1, 2], f"{label}: {got}"
        assert [r["url"] for r in got] == ["u-auto", "u-manual"], label


def test_the_sheets_nodes_write_post_media_from_the_row():
    """A rename that kept the old $json.ANIMATED expression wrote an empty POST_MEDIA."""
    for label, doc in _copies(CURATOR):
        for name in ("append_content_queue", "update_backfill_columns"):
            value = _node(doc, name)["parameters"]["columns"]["value"]
            assert value.get("POST_MEDIA") == "={{ $json.POST_MEDIA }}", f"{label}: {name} mapping"


def test_the_backfill_chain_has_a_model_and_a_fallback():
    """chainLlm needs both sub-nodes: the model at input 0 and the fallback at input 1."""
    for label, doc in _copies(CURATOR):
        conns = doc["connections"]
        model = [e for e in conns["ai_model"]["ai_languageModel"][0] if e["node"] == "judge_llm_backfill"]
        fallback = [e for e in conns["ai_model_fallback"]["ai_languageModel"][0] if e["node"] == "judge_llm_backfill"]
        assert model and model[0]["index"] == 0, f"{label}: backfill model must be input 0"
        assert fallback and fallback[0]["index"] == 1, f"{label}: backfill fallback must be input 1"


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
        inputs = {v["name"] for v in _node(doc, "main_trigger")["parameters"]["workflowInputs"]["values"]}
        assert "SCENES" in inputs, f"{label}: the sub-workflow trigger must accept SCENES"
        # The final hold this change's predecessor added was superseded by
        # upgrade-visual-studio-authoring: no type mandates a frozen frame, so
        # neither the registry plumbing nor the brief may carry it.
        assert "HOLD_SECONDS" not in _node(doc, "parse_registry")["parameters"]["jsCode"], label
        brief = _node(doc, "build_author_brief")["parameters"]["jsCode"]
        assert "End on a hold" not in brief and "HOLD_SECONDS" not in brief, label
