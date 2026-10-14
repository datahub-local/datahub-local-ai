"""Guard the agent-first Visual Studio graph and its trigger contract.

Authoring is one composer turn for the agent types and one Gemini image for the
``image`` type. The typed content spec, the markup templates, the in-workflow frame
capture and the render-service call are gone, and those are properties of the graph,
so they are asserted here, offline, against the committed export.

Both copies of the graph are checked -- the exports carry their nodes twice, at the
top level and inside ``activeVersion``, and a fix applied to one copy is a live bug.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "workflows" / "visual_studio.workflow.json"

RETIRED_NODES = {
    "pick_spec_type", "if_spec_given", "spec_from_param", "download_spec_prompt",
    "author_spec", "parse_spec", "spec_ready", "download_html_template",
    "download_svg_template", "merge_assets", "if_video", "build_video", "render_video",
    "video_result", "if_animated", "if_capture_ok", "mkdir_frames", "capture_frames",
    "capture_failed", "build_assemble", "assemble_animation", "animated_result",
    "cleanup_frames",
}


def _copies():
    doc = json.loads(STUDIO.read_text())
    yield "top", doc
    if isinstance(doc.get("activeVersion"), dict) and "nodes" in doc["activeVersion"]:
        yield "activeVersion", doc["activeVersion"]


def _node(doc, name):
    for node in doc["nodes"]:
        if node["name"] == name:
            return node
    raise AssertionError(f"node {name!r} is missing from the export")


def _code(doc, name):
    node = _node(doc, name)
    return node["parameters"].get("jsCode") or node["parameters"].get("scriptCode") or ""


def _targets(doc, source, output):
    return [e["node"] for e in doc["connections"][source]["main"][output]]


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_deterministic_path_is_gone(label, doc):
    names = {n["name"] for n in doc["nodes"]}
    left = names & RETIRED_NODES
    assert not left, f"{label}: retired node(s) still present: {sorted(left)}"


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_agent_and_image_branches_are_wired(label, doc):
    conns = doc["connections"]
    assert conns["parse_registry"]["main"][0][0]["node"] == "if_agent"
    # Agent types go to the composer; everything else is offered to the image branch.
    assert _targets(doc, "if_agent", 0) == ["build_author_brief"]
    assert _targets(doc, "if_agent", 1) == ["if_raster"]
    assert _targets(doc, "if_raster", 0) == ["download_raster_prompt"]
    # A non-agent, non-image entry (UNKNOWN / SKIPPED / UNAVAILABLE) reports as-is.
    assert _targets(doc, "if_raster", 1) == ["ready_pass"]


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_agent_branch_reaches_the_merge(label, doc):
    assert _targets(doc, "build_author_brief", 0) == ["execute_author"]
    assert _targets(doc, "execute_author", 0) == ["fetch_artifact"]
    # A deck yields a second artifact, so the fetch is gated on the render mode.
    assert _targets(doc, "fetch_artifact", 0) == ["if_deck"]
    assert _targets(doc, "if_deck", 0) == ["fetch_paired_artifact"]
    assert _targets(doc, "if_deck", 1) == ["agent_result"]
    assert _targets(doc, "fetch_paired_artifact", 0) == ["agent_result"]
    assert _targets(doc, "agent_result", 0) == ["merge_branches"]


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_raster_branch_reaches_the_merge(label, doc):
    assert _targets(doc, "download_raster_prompt", 0) == ["raster_director"]
    assert _targets(doc, "raster_director", 0) == ["generate_image"]
    assert _targets(doc, "generate_image", 0) == ["raster_result"]
    assert _targets(doc, "raster_result", 0) == ["merge_branches"]
    assert _targets(doc, "ready_pass", 0) == ["merge_branches"]
    # The merged assets are stored in Garage before the response is built, so the
    # response can name the object each asset was written to.
    assert _targets(doc, "merge_branches", 0) == ["prepare_uploads"]
    assert _targets(doc, "prepare_uploads", 0) == ["upload_assets"]
    assert _targets(doc, "upload_assets", 0) == ["set_result"]


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_raster_model_still_has_its_llm(label, doc):
    # ai_model and ai_model_fallback are the raster director's language models; they
    # used to also feed the spec author, which is gone.
    for name in ("ai_model", "ai_model_fallback"):
        edges = doc["connections"][name]["ai_languageModel"]
        targets = {e["node"] for branch in edges for e in branch}
        assert targets == {"raster_director"}, f"{name} feeds {targets}"


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_branch_conditions_name_the_new_authors(label, doc):
    assert _node(doc, "if_agent")["parameters"]["conditions"]["conditions"][0]["leftValue"] == (
        "={{ $json.AUTHOR === 'agent' }}"
    )
    assert _node(doc, "if_raster")["parameters"]["conditions"]["conditions"][0]["leftValue"] == (
        "={{ $json.AUTHOR === 'image' }}"
    )


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_trigger_contract_carries_force_and_style(label, doc):
    code = _code(doc, "normalize_input")
    assert "FORCE" in code and "STYLE" in code
    assert "SPEC_JSON" not in code
    # FORCE is an enum and an unknown value fails naming it.
    for value in ("auto", "diagram", "story", "data", "poster", "code", "chart", "timeline", "quote", "ui", "manga"):
        assert f"'{value}'" in code, f"FORCE enum is missing {value}"
    assert "'image'" not in code, "the raster medium is not a composition form"
    assert "unknown FORCE" in code

    main_values = {v["name"] for v in _node(doc, "main_trigger")["parameters"]["workflowInputs"]["values"]}
    assert {"CONTENT", "ASSET_TYPES", "FEEDBACK", "FORCE", "STYLE", "EXTRA_PROMPT"} <= main_values
    assert "SPEC_JSON" not in main_values
    form_fields = {f["fieldLabel"] for f in _node(doc, "form_trigger")["parameters"]["formFields"]["values"]}
    assert {"CONTENT", "ASSET_TYPES", "FEEDBACK", "FORCE", "STYLE", "EXTRA_PROMPT"} <= form_fields
    assert "SPEC_JSON" not in form_fields


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_style_is_resolved_where_the_schemes_live(label, doc):
    # brand.json is the only place the scheme names live, so brand_tokens defaults
    # and validates STYLE there and an unknown scheme fails naming it.
    code = _code(doc, "brand_tokens")
    assert "defaultScheme" in code
    assert "unknown STYLE" in code
    assert "STYLE:" in code


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_brief_carries_force_style_brand_and_frame(label, doc):
    body = _code(doc, "build_author_brief")
    assert "req.FORCE" in body and "brand.STYLE" in body
    assert "brand.BRAND" in body, "the brand block must reach the composer"
    # The frame: format, size and duration.
    assert "a.FORMAT" in body and "WIDTH" in body and "HEIGHT" in body
    assert "durationSeconds" in body and "frames" in body
    assert "storyboard" in body.lower(), "the brief must ask the composer to plan first"
    assert _node(doc, "execute_author")["parameters"]["jsonBody"] == "={{ $json.AUTHOR_BODY }}"


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_form_vocabulary_is_fetched_and_reaches_the_brief(label, doc):
    """One committed copy of the vocabulary, fetched the way the motion rules are.

    A form name is our word, not the framework's: ``data`` and ``poster`` mean nothing
    to the composer unless the brief defines them. ``prompts/visual_forms.md`` is the
    one copy, appended to every brief; the workflow does not restate the definitions.
    """
    dl = _node(doc, "download_visual_forms")
    name = dl["parameters"]["workflowInputs"]["value"]["template_name"]
    assert name == "prompts/visual_forms.md"
    assert _targets(doc, "download_visual_forms", 0) == ["visual_forms"]
    assert _targets(doc, "visual_forms", 0) == ["download_registry"]
    body = _code(doc, "build_author_brief")
    assert "visual_forms" in body and "FORMS" in body
    assert "vocab" in body, "the brief does not append the vocabulary"


def test_the_form_enum_matches_the_vocabulary():
    """The enum minus ``auto`` (which only means "no pin") is exactly the file's forms."""
    text = (ROOT / "prompts" / "visual_forms.md").read_text(encoding="utf-8")
    defined = set(re.findall(r"^- `([a-z]+)`: .+", text, re.MULTILINE))
    assert defined, "the vocabulary file defines no forms"
    for label, doc in _copies():
        match = re.search(r"const FORCES = \[([^\]]*)\]", _code(doc, "normalize_input"))
        assert match, f"{label}: normalize_input has no FORCES enum"
        enum = {x.strip().strip("'\"") for x in match.group(1).split(",") if x.strip()}
        assert enum - {"auto"} == defined, f"{label}: enum {sorted(enum)} vs vocabulary {sorted(defined)}"


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_storyboard_reaches_the_response(label, doc):
    # The composer states a storyboard first; agent_result keeps its report as
    # STORYBOARD and set_result returns the assets, so a bad visual is diagnosable from
    # the response. No run row carries it: nothing read one, so the table is gone.
    assert "STORYBOARD" in _code(doc, "agent_result")
    assert "execute_author" in _code(doc, "agent_result")
    assert "ASSETS" in _code(doc, "set_result")
    assert "SPEC_GIVEN" not in _code(doc, "set_result")
    assert [n for n in doc["nodes"] if n["type"] == "n8n-nodes-base.dataTable"] == []


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_a_failed_composer_is_continued_and_handled(label, doc):
    # continueRegularOutput makes a failure invisible unless a downstream node
    # consumes the empty result, so both halves are required.
    assert _node(doc, "execute_author").get("onError") == "continueRegularOutput"
    assert _node(doc, "fetch_artifact").get("onError") == "continueRegularOutput"
    code = _code(doc, "agent_result")
    assert "STATUS: 'ERROR'" in code
    assert "PI_RENDER_URL" in code


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_only_the_brief_crosses_to_the_composer(label, doc):
    # The request is the brief plus the output frame; no markup is sent, which is
    # what keeps the workflow out of the composition.
    body = _code(doc, "build_author_brief")
    assert "AUTHOR_BODY" in body
    assert "req.CONTENT" in body
    assert "messages:" in body and "session_id" in body and "format" in body
    for forbidden in ('"html"', '"markup"', '"script"', '"css"'):
        assert forbidden not in body


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_a_transient_empty_agent_turn_is_retried(label, doc):
    # A turn can come back empty (the model returned nothing and no artifact was
    # written); one retry covers the transient case without burning a whole run.
    node = _node(doc, "execute_author")
    assert node.get("retryOnFail") is True
    assert node.get("maxTries", 0) >= 2


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_agent_result_is_content_not_a_reference(label, doc):
    code = _code(doc, "agent_result")
    assert "IMAGE: 'data:'" in code
    assert "ARTIFACT_URL" not in code
    # This instance stores binaries out of band, so binary.data is a reference
    # ("database:<id>"), not base64; reading it directly uploaded a 6-byte file.
    assert "getBinaryDataBuffer(0, 'data')" in code
    assert "bin.data" not in code


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_motion_rules_are_fetched_once_and_reach_the_brief(label, doc):
    # One committed copy of the grammar, fetched the way brand.json is, and appended
    # to every brief; the workflow does not restate the rules in its own logic.
    dl = _node(doc, "download_visual_rules")
    name = dl["parameters"]["workflowInputs"]["value"]["template_name"]
    assert name == "prompts/visual_motion_rules.md"
    assert _targets(doc, "download_visual_rules", 0) == ["visual_rules"]
    assert _targets(doc, "visual_rules", 0) == ["download_visual_forms"]
    body = _code(doc, "build_author_brief")
    assert "visual_rules" in body and "RULES" in body


def test_the_motion_rules_require_the_sidecar_and_the_hatch_discipline():
    # `check` verifies motion only when a *.motion.json sidecar exists, and the overflow
    # hatch silences the clipping findings for every descendant of the element carrying
    # it. Both were absent from the manga run on 2026-10-13: fifteen panels carried
    # data-layout-allow-overflow, no sidecar existed, and check passed a clip whose
    # panels never reached the screen. Measured, not assumed -- the hatch on a container
    # removes its child's container_overflow finding from the same composition.
    text = (ROOT / "prompts" / "visual_motion_rules.md").read_text(encoding="utf-8")
    assert "motion.json" in text
    for assertion in ("appearsBy", "staysInFrame", "keepsMoving"):
        assert assertion in text, f"the rules do not name the {assertion} assertion"
    assert "data-layout-allow-overflow" in text
    assert "overflow: hidden" in text


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_brief_carries_the_rules_feedback_and_extra_prompt(label, doc):
    body = _code(doc, "build_author_brief")
    assert "req.FEEDBACK" in body, "the reviewer's correction does not reach the composer"
    assert "req.EXTRA_PROMPT" in body, "the caller's extra direction does not reach the composer"
    # The harness this change removes must not come back.
    assert "holdLine" not in body and "End on a hold" not in body
    assert "reviewLine" not in body and "Before rendering, review" not in body
    assert "HOLD_SECONDS" not in body


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_brief_gives_each_scene_a_minimum_and_keeps_the_declared_rate(label, doc):
    # A clip is at least the type's declared floor, and a named scene count gives each
    # scene at least the type's declared scene length; the frame count scales with the
    # longer duration so the clip is longer rather than faster.
    body = _code(doc, "build_author_brief")
    assert "SCENE_SECONDS" in body
    assert "Math.max(declaredSeconds, scenes * sceneSeconds)" in body
    assert "declaredFrames * seconds / declaredSeconds" in body
    registry = _code(doc, "parse_registry")
    assert "secondsPerScene" in registry and "SCENE_SECONDS" in registry


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_a_multi_scene_request_opens_on_a_title_scene(label, doc):
    # A declared sequence is introduced by a title scene that names the subject, so
    # the clip carries the declared count plus the title; a count of one is unchanged.
    body = _code(doc, "build_author_brief")
    assert "scenes > 1" in body, f"{label}: the title scene must be gated on a multi-scene count"
    assert "title scene that names the subject" in body, label
    assert "(scenes + 1)" in body, f"{label}: the clip must carry the title beside the declared scenes"


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_a_deck_run_fetches_both_artifacts(label, doc):
    body = _code(doc, "build_author_brief")
    assert "PAIRED_ARTIFACT_URL" in body
    assert "out.html" in body, "the deck brief does not name the deck file"
    assert "a.RENDER_MODE" in body and "'deck'" in body
    # The deck honours a named scene count like every other animated video.
    assert "...(isIteration ? opening : [deckPlanLine]),\n      sceneLine," in body
    node = _node(doc, "fetch_paired_artifact")
    assert "PAIRED_ARTIFACT_URL" in node["parameters"]["url"]
    assert node.get("onError") == "continueRegularOutput"
    # The deck and its video are two assets of one run.
    result = _code(doc, "agent_result")
    assert "'paired'" in result and "PAIRED_ASSET_TYPE" in result


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_a_named_session_is_continued_and_a_blank_one_is_run_scoped(label, doc):
    # SESSION_ID is part of the contract on every surface...
    main_values = {v["name"] for v in _node(doc, "main_trigger")["parameters"]["workflowInputs"]["values"]}
    form_fields = {f["fieldLabel"] for f in _node(doc, "form_trigger")["parameters"]["formFields"]["values"]}
    assert "SESSION_ID" in main_values
    assert "SESSION_ID" in form_fields
    assert "SESSION_ID: v('SESSION_ID')" in _code(doc, "normalize_input")

    body = _code(doc, "build_author_brief")
    # ...a named session is used as given, and a blank one keeps the run-scoped id...
    assert "safe(req.SESSION_ID) ||" in body
    assert "safe(a.ASSET_TYPE) + '-' + safe(req.RUN_ID)" in body, "the run-scoped fallback must remain"
    # ...and that resolved value is what the adapter is called with and what the
    # artifact is addressed under, so a continuation fetches the same URL.
    assert "session_id: sessionId" in body
    assert "'/artifacts/' + sessionId" in body


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_a_continuation_brief_differs_from_a_first_authoring(label, doc):
    body = _code(doc, "build_author_brief")
    assert "const isIteration = Boolean(String(req.SESSION_ID || '').trim());" in body
    # A continuation keeps the work already in the session and applies only the change.
    assert "This continues the composition already in this session" in body
    assert "change below" in body
    # A first authoring still plans before it builds.
    assert "Plan first: state a short storyboard" in body
    # Each authoring branch chooses between the two by isIteration.
    assert body.count("isIteration ? opening") >= 2
    assert "...opening," in body, "the SVG branch carries the continuation"


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_response_carries_the_resolved_session(label, doc):
    # The row that carried the request is gone, so the response carries the resolved
    # session id: a caller that sent none cannot otherwise learn the id its thread was
    # scoped to, and continuing that thread needs it.
    code = _code(doc, "set_result")
    assert "SESSION_ID: sessionId" in code
    assert "build_author_brief" in code and "SESSION_ID" in code
