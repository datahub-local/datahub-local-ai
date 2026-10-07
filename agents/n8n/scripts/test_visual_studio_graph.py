"""Guard the agent-first Visual Studio graph and its trigger contract.

Authoring is one composer turn for the agent types and one Gemini image for the
``image`` type. The typed content spec, the markup templates, the in-workflow frame
capture and the render-service call are gone, and those are properties of the graph,
so they are asserted here, offline, against the committed export.

Both copies of the graph are checked -- the exports carry their nodes twice, at the
top level and inside ``activeVersion``, and a fix applied to one copy is a live bug.
"""

import json
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
    assert _targets(doc, "fetch_artifact", 0) == ["agent_result"]
    assert _targets(doc, "agent_result", 0) == ["merge_branches"]


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_raster_branch_reaches_the_merge(label, doc):
    assert _targets(doc, "download_raster_prompt", 0) == ["raster_director"]
    assert _targets(doc, "raster_director", 0) == ["generate_image"]
    assert _targets(doc, "generate_image", 0) == ["raster_result"]
    assert _targets(doc, "raster_result", 0) == ["merge_branches"]
    assert _targets(doc, "ready_pass", 0) == ["merge_branches"]
    assert _targets(doc, "merge_branches", 0) == ["run_record"]


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
    for value in ("auto", "diagram", "story", "data", "poster", "image"):
        assert f"'{value}'" in code, f"FORCE enum is missing {value}"
    assert "unknown FORCE" in code

    main_values = {v["name"] for v in _node(doc, "main_trigger")["parameters"]["workflowInputs"]["values"]}
    assert {"CONTENT", "ASSET_TYPES", "FEEDBACK", "FORCE", "STYLE"} <= main_values
    assert "SPEC_JSON" not in main_values
    form_fields = {f["fieldLabel"] for f in _node(doc, "form_trigger")["parameters"]["formFields"]["values"]}
    assert {"CONTENT", "ASSET_TYPES", "FEEDBACK", "FORCE", "STYLE"} <= form_fields
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
def test_the_storyboard_is_recorded(label, doc):
    # The composer states a storyboard first; agent_result keeps its report as
    # STORYBOARD and run_record carries it in RESULT, so a bad visual is diagnosable.
    assert "STORYBOARD" in _code(doc, "agent_result")
    assert "execute_author" in _code(doc, "agent_result")
    assert "STORYBOARD" in _code(doc, "run_record")
    assert "SPEC_GIVEN" not in _code(doc, "run_record")


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
