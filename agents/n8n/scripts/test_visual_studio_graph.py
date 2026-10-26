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
import shutil
import subprocess
import tempfile
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
    # The artifact is stored by the temp-bucket server rather than fetched into this
    # execution: the workflow holds the object key, never the bytes.
    assert _targets(doc, "execute_author", 0) == ["store_artifact"]
    # A deck yields a second artifact, so the store is gated on the render mode.
    assert _targets(doc, "store_artifact", 0) == ["if_deck"]
    assert _targets(doc, "if_deck", 0) == ["store_paired_artifact"]
    assert _targets(doc, "if_deck", 1) == ["agent_result"]
    assert _targets(doc, "store_paired_artifact", 0) == ["agent_result"]
    # The asset is reviewed before it is offered: the review is this workflow's, not the
    # session's, and its clear path is what reaches the merge.
    assert _targets(doc, "agent_result", 0) == ["prepare_stills"]
    assert _targets(doc, "prepare_stills", 0) == ["if_stills"]
    assert _targets(doc, "if_stills", 0) == ["fetch_still"]
    assert _targets(doc, "if_stills", 1) == ["merge_branches"], "no still is a review that did not run"
    assert _targets(doc, "fetch_still", 0) == ["encode_stills"]
    assert _targets(doc, "encode_stills", 0) == ["critique"]
    assert _targets(doc, "critique", 0) == ["parse_verdict"]
    assert _targets(doc, "parse_verdict", 0) == ["if_review_findings"]
    assert _targets(doc, "if_review_findings", 0) == ["review_feedback"]
    assert _targets(doc, "if_review_findings", 1) == ["merge_branches"]
    # And a finding is corrected in the thread that owns the composition.
    assert _targets(doc, "review_feedback", 0) == ["build_author_brief"]


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_review_is_orchestrated_here_and_the_session_makes_no_model_call(label, doc):
    # The critic is a call this workflow makes: the session hands back stills and nothing else.
    # An api call inside the adapter was the first shape and was rejected -- orchestration is
    # this graph's job, and the agent's dependencies stay what they were.
    critique = _node(doc, "critique")
    assert critique["type"] == "n8n-nodes-base.httpRequest"
    assert "chat/completions" in critique["parameters"]["url"]
    assert critique["parameters"]["method"] == "POST"
    assert critique["credentials"]["httpBearerAuth"]["id"] == _node(doc, "generate_image")["credentials"]["httpBearerAuth"]["id"]
    # The prompt is a committed file, fetched like the motion rules, so the grammar a critic
    # applies is a prompt push rather than an image rebuild.
    fetch = _node(doc, "download_review_prompt")["parameters"]["workflowInputs"]["value"]
    assert fetch["template_name"] == "prompts/visual_review_composition.md"
    assert fetch["template_vars"] == "={{ {} }}"
    # The stills come from the session's own route, at the session the turn used.
    code = _node(doc, "prepare_stills")["parameters"]["jsCode"]
    assert "/artifacts/" in code and "$env.PI_RENDER_URL" in code
    assert "resp.stills" in code, "the names the render reported, not a guessed convention"
    # The critic sees the stills, not the artifact: the bytes that flow here are stills.
    encode = _node(doc, "encode_stills")["parameters"]["jsCode"]
    assert "getBinaryDataBuffer" in encode and "image_url" in encode
    assert "AUTHOR_BODY" in encode, "the critic judges against the brief the composer was given"


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_review_is_bounded_and_its_verdict_is_data(label, doc):
    # The bound lives with the request's defaults, and the loop's whole decision is one field
    # the gate reads -- so the bound and the verdict are asserted offline rather than trusted.
    normalize = _node(doc, "normalize_input")["parameters"]["jsCode"]
    assert "REVIEW_CYCLES = 2" in normalize
    assert "REVIEW_ROUND: 0" in normalize
    verdict = _node(doc, "parse_verdict")["parameters"]["jsCode"]
    assert "RETRY: verdict === 'fix' && round < cycles" in verdict
    assert "REVIEW: JSON.stringify(" in verdict, "the outcome rides on the asset"
    # An unreadable answer is a pass: the other direction spends every cycle and ships the
    # same defect.
    assert "unreadable = true" in verdict and "verdict = 'ok'" in verdict
    # The fix turn carries the findings and increments the round.
    feedback = _node(doc, "review_feedback")["parameters"]["jsCode"]
    assert "FEEDBACK: a.FINDINGS_TEXT" in feedback
    assert "REVIEW_ROUND: Math.max(0, Number(a.REVIEW_ROUND || 0)) + 1" in feedback
    # And the authoring brief honours an item-level correction, which is how the fix turn's
    # findings reach the composer.
    brief = _node(doc, "build_author_brief")["parameters"]["jsCode"]
    assert "const feedback = String(a.FEEDBACK || req.FEEDBACK || '')" in brief
    assert "REVIEW_ROUND: Math.max(0, Number(a.REVIEW_ROUND || 0))" in brief


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_authoring_answer_is_read_from_its_success_output(label, doc):
    # $('node').first() does not mean output 0: n8n walks upstream from the reading node and
    # takes the index of the connection it finds, so once execute_author's error output fed
    # agent_result (2026-10-25) the unqualified read resolved to output 1 -- empty on success.
    # prepare_stills threw on the undefined .json and killed a run whose asset was already
    # stored, and agent_result's guarded reads silently recorded an empty STORYBOARD (14997).
    readers = [n for n in doc["nodes"] if "$('execute_author')" in ((n.get("parameters") or {}).get("jsCode") or "")]
    assert readers, "expected a node to read the authoring answer"
    for node in readers:
        code = node["parameters"]["jsCode"]
        assert "$('execute_author').first()" not in code, (
            f"{label}: {node['name']} reads execute_author without pinning its success output"
        )
        assert "$('execute_author').first(0)" in code


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_raster_branch_reaches_the_merge(label, doc):
    assert _targets(doc, "download_raster_prompt", 0) == ["raster_director"]
    assert _targets(doc, "raster_director", 0) == ["generate_image"]
    assert _targets(doc, "generate_image", 0) == ["raster_result"]
    # The raster is reviewed too, and its clear path is what reaches the merge.
    assert _targets(doc, "raster_result", 0) == ["prepare_raster_review"]
    assert _targets(doc, "ready_pass", 0) == ["merge_branches"]
    # The merged assets go straight to the response. Nothing in this graph uploads: an
    # agent asset is stored by the temp-bucket server and arrives here already named, and
    # a raster asset keeps the data URL it was made with, so a chain that converted the
    # one into binary for an S3 node had nothing left to hand on.
    assert _targets(doc, "merge_branches", 0) == ["set_result"]
    names = {n["name"] for n in doc["nodes"]}
    assert "prepare_uploads" not in names and "upload_assets" not in names


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_a_types_form_is_honoured_ahead_of_the_callers(label, doc):
    # The type's own form wins, then the caller's FORCE, then the composer's choice: a
    # `diagram` type must not be talked out of being a diagram by a request-level knob that
    # was written for the whole request.
    shaped = _node(doc, "parse_registry")["parameters"]["jsCode"]
    assert "FORM: t.form || ''" in shaped
    assert "FORM: ''" in shaped, "the unknown/unavailable note must carry the field too"
    brief = _node(doc, "build_author_brief")["parameters"]["jsCode"]
    assert "a.FORM || req.FORCE || 'auto'" in brief


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_raster_frame_comes_from_the_type(label, doc):
    # The frame is the type's own data: the raster request used to hardcode `4:5`, so a
    # type declaring 16:9 was generated portrait and then composed for the wrong shape --
    # measured 2026-10-17, when the director's own prompt asked for "landscape 3:2" and the
    # API cropped it to 4:5. The director is told the frame too, so the prompt and the
    # request agree instead of one of them being authoritative.
    body = _node(doc, "generate_image")["parameters"]["jsonBody"]
    assert '"aspect_ratio": "4:5"' not in body
    assert "$json.ASPECT" in body or "ASPECT" in body
    vars_ = _node(doc, "download_raster_prompt")["parameters"]["workflowInputs"]["value"]["template_vars"]
    assert "ASPECT" in vars_


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
    for value in ("auto", "diagram", "story", "data", "poster", "code", "chart", "timeline", "quote", "ui", "manga", "retro"):
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
def test_the_brief_composes_a_still_in_one_settled_frame(label, doc):
    """A still artifact is the render's **last** frame (session-lib transcodeArgs
    samples the end with ``-sseof``), so the brief must say the card is complete
    there: an entrance is fine, an exit is not."""
    body = _code(doc, "build_author_brief")
    assert "format === 'png'" in body, "the brief has no still branch"
    start = body.index(": format === 'png'")
    still = body[start:body.index("].join", start)]
    assert "final frame" in still, "the still brief does not name the frame that ships"
    assert "first frame" not in still, "the still brief still promises the first frame"
    assert "stillSceneLine" in still, "a scene count is ignored rather than folded in"
    assert "sampling" not in still, "the still branch reuses the animated instruction"


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
    # The scene contract is fetched on the same chain, then the review prompt and the
    # registry: every node here reads what it needs by name.
    assert _targets(doc, "visual_forms", 0) == ["download_scene_rules"]
    assert _targets(doc, "download_scene_rules", 0) == ["scene_rules"]
    assert _targets(doc, "scene_rules", 0) == ["download_review_prompt"]
    assert _targets(doc, "download_review_prompt", 0) == ["download_raster_review_prompt"]
    assert _targets(doc, "download_raster_review_prompt", 0) == ["download_registry"]
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
def test_a_failed_composer_reports_its_own_reason(label, doc):
    # continueRegularOutput hid the failure *and* dropped its reason: the store then failed on
    # an artifact that was never rendered, so the asset named a 404 on out.mp4 where the
    # session had answered `EEXIST` (measured 2026-10-24, execution 14801). `neverError`
    # delivers a 4xx body as data and the error output carries a transport failure, so both
    # reach agent_result; the stores keep continuing on error for the same reason as before.
    author = _node(doc, "execute_author")
    assert author.get("onError") == "continueErrorOutput"
    assert author["parameters"]["options"]["response"]["response"]["neverError"] is True
    assert _targets(doc, "execute_author", 0) == ["store_artifact"]
    assert _targets(doc, "execute_author", 1) == ["agent_result"], "the reason must reach the asset"
    assert _node(doc, "store_artifact").get("onError") == "continueRegularOutput"
    assert _node(doc, "store_paired_artifact").get("onError") == "continueRegularOutput"
    code = _code(doc, "agent_result")
    assert "authoring failed" in code and "execute_author" in code


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_asset_carries_what_the_runtime_reported_about_its_container(label, doc):
    # The declared frame the caller reads is the request's; the session's note says what the
    # artifact was served at, and names the authored frame where the two differed (measured
    # 2026-10-17, run 13762: a 16:9 / 12s type served at 1080x1350 / 3s). Absent note means
    # empty fields, so "no report" and "the declared container" stay distinguishable.
    code = _code(doc, "agent_result")
    assert "conformance" in code
    assert "execute_author" in code
    for field in ("CONFORMED", "AUTHORED_FRAME", "SHORT"):
        assert field in code, field
    # And the request to the session carries both numbers of the declared frame: a
    # conformance that knows only the width can scale but cannot deliver the aspect, and the
    # session's own `height` read was dead until this was fixed.
    body = _code(doc, "build_author_brief").split("AUTHOR_BODY", 1)[1]
    assert "width: width" in body and "height: height" in body


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_asset_carries_the_container_the_request_declared(label, doc):
    # A review turn's item is built from the asset, so the declaration has to ride on it or
    # the correction turn re-invents one (measured 2026-10-17, run 13785: a tiles_wide
    # request at 16:9 / 1280 / 12s / 360 was corrected at 1080x1350 / 3s / 24 frames).
    code = _code(doc, "agent_result")
    for field in ("ASPECT: a.ASPECT", "VIEWPORT: String(Number(a.VIEWPORT)", "FRAMES: String(Number(a.FRAMES)",
                  "DURATION_SECONDS: String(Number(a.DURATION_SECONDS)", "FPS: String(Number(a.FPS)"):
        assert field in code, f"the asset does not carry {field!r}"
    # The declaration survives the loop's own nodes, which spread the asset they are handed.
    assert "...asset" in _code(doc, "prepare_stills"), "prepare_stills would drop the declaration"
    assert "...a" in _code(doc, "parse_verdict"), "parse_verdict would drop the declaration"
    assert "...a" in _code(doc, "review_feedback"), "the correction turn would lose the declaration"


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_brief_never_invents_a_container(label, doc):
    # The four silent defaults are the reason run 13785 shipped two wrong turns; absence is
    # now an error naming the field, because a plausible default is indistinguishable from
    # the caller's request once the run has produced an artifact.
    body = _code(doc, "build_author_brief")
    assert "cannot re-declare a container" in body
    for field in ("declared('VIEWPORT', a.VIEWPORT)", "declared('FRAMES', a.FRAMES)",
                  "declared('DURATION_SECONDS', a.DURATION_SECONDS)"):
        assert field in body, f"the brief does not require {field!r}"
    for fallback in ("|| 1080", "|| '4:5'", "|| 24", "|| 8"):
        assert fallback not in body, f"the brief still defaults its container via {fallback!r}"
    # The registry completes the container so every real type satisfies that requirement: a
    # type that declares no length (the launch card) still declares one, from its own budget,
    # rather than 0, which the brief would now refuse.
    registry = _code(doc, "parse_registry")
    assert "Number(t.durationSeconds) || frames / fps" in registry


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
def test_the_agent_result_names_an_object_rather_than_carrying_it(label, doc):
    # The render used to travel as a base64 data URL, which put a 60 MB asset into the
    # execution payload *and* into n8n's binary store - measured, `binary_data` grew by
    # six rows and a megabyte for a single still run with success data on. The
    # temp-bucket server stores the render and answers with the key and its size, so the
    # asset names an object. Reading a binary here again would undo that, and this
    # instance keeps binaries out of band anyway: binary.data is a reference
    # ("database:<id>"), so reading it directly once uploaded a 6-byte file.
    code = _code(doc, "agent_result")
    assert "S3_KEY" in code and "S3_BYTES" in code
    assert "getBinaryDataBuffer" not in code
    assert "data:'" not in code
    assert "temp_store" not in code, "the store is a node of its own, not built in here"
    # A store that failed is this asset's ERROR, not the run's.
    assert "STATUS: 'ERROR'" in code and "PI_RENDER_URL" in code and "MCP_UTILS_URL" in code


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
def test_an_animated_clip_with_no_declared_count_opens_on_the_subject(label, doc):
    # Run 14335 (2026-10-19) opened on a detail: the count-gated rule said nothing when the
    # composer owned the storyboard, and only a human retry asked for the title.
    body = _code(doc, "build_author_brief")
    assert "scenes === 0 && a.INTRO_SCENE === true" in body, label
    assert "before the content scenes the storyboard sets" in body, label
    # The line reaches the video branch and no other: a deck, an SVG or a still carries no
    # sequence, so none of them may be asked for a title scene.
    assert "sceneLine,\n      introLine,\n      ...sceneBlock," in body, label
    assert "deckPlanLine,\n      sceneLine,\n      introLine" not in body, label
    assert "...vocab,\n      sceneLine,\n      ...sceneBlock,\n      styleLine,\n      'Use a " in body, label
    # The declaration is data on the type, and it rides on the asset a review turn reads.
    assert "INTRO_SCENE: t.introScene === true" in _code(doc, "parse_registry"), label
    assert "INTRO_SCENE: a.INTRO_SCENE === true" in _code(doc, "agent_result"), label


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_scene_contract_is_a_prompt_file(label, doc):
    # A definition is not a count: the brief says how many and in what order, and the file
    # says what a scene is. It is fetched like the motion rules and appended to every
    # scene-bearing branch, so the composer never infers the unit from a number.
    fetch = _node(doc, "download_scene_rules")
    assert fetch["parameters"]["workflowInputs"]["value"]["template_name"] == "prompts/visual_scene.md"
    body = _code(doc, "scene_rules")
    assert "SCENE" in body
    brief = _code(doc, "build_author_brief")
    assert "$('scene_rules')" in brief, label
    assert "...sceneBlock," in brief, label
    # The deck, the SVG and the clip carry scenes; the still does not.
    assert brief.count("...sceneBlock,") == 3, label
    text = (ROOT / "prompts" / "visual_scene.md").read_text()
    assert "A scene is one beat" in text
    assert "additional to them" in text
    # The copy budget: a clip is watched, so a scene carries one short line and the
    # detail stays in the post text rather than competing with the motion.
    assert "six words at most" in text
    assert "post text" in text


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_a_deck_run_stores_both_artifacts(label, doc):
    body = _code(doc, "build_author_brief")
    assert "PAIRED_ARTIFACT_URL" in body and "PAIRED_ARTIFACT_KEY" in body
    assert "out.html" in body, "the deck brief does not name the deck file"
    assert "a.RENDER_MODE" in body and "'deck'" in body
    # The deck honours a named scene count like every other animated video.
    assert "deckPlanLine,\n      sceneLine," in body
    node = _node(doc, "store_paired_artifact")
    assert "PAIRED_ARTIFACT_URL" in node["parameters"]["jsonBody"]
    assert "PAIRED_ARTIFACT_KEY" in node["parameters"]["jsonBody"]
    assert node.get("onError") == "continueRegularOutput"
    # The deck and its video are two assets of one run, each with its own key.
    result = _code(doc, "agent_result")
    assert "PAIRED_ASSET_TYPE" in result and "store_paired_artifact" in result
    assert "PAIRED_ARTIFACT_URL" in result


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
def test_the_adapter_owns_author_vs_edit_and_the_brief_never_claims_it(label, doc):
    # A brief that says "this continues the composition already in this session" is a
    # claim about the session directory, and the brief cannot see it. Naming a session
    # is not the same as that session holding work: run 13356 named a brand-new session
    # and was told to "apply the change below to it and keep everything else" against an
    # empty directory, while the adapter -- which does check -- said first authoring.
    body = _code(doc, "build_author_brief")
    assert "isIteration" not in body, "the brief must not infer author-vs-edit from SESSION_ID"
    assert "const opening" not in body and "...opening," not in body
    assert "This continues the composition already in this session" not in body
    # Every authoring branch still plans, so a first authoring is unchanged.
    assert "planLine,\n      form," in body, "the video branch must still plan"
    assert "deckPlanLine,\n      sceneLine," in body, "the deck branch must still plan"
    # The session resolution itself is untouched: a named session is used as given and
    # a blank one is scoped to the run.
    assert "safe(req.SESSION_ID) ||" in body
    assert "safe(a.ASSET_TYPE) + '-' + safe(req.RUN_ID)" in body


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_adapter_is_what_tells_a_turn_to_author_or_edit(label, doc):
    # The other half of the contract: the instruction the composer is handed does
    # distinguish the two, and it is chosen from the directory marker.
    lib = (Path(__file__).resolve().parents[2] / "adapters" / "pi-render" / "session-lib.mjs").read_text()
    assert "export function compositionMarker(format)" in lib
    assert "case \"svg\":" in lib and "return \"out.svg\";" in lib
    assert "return \"index.html\";" in lib
    assert "export function turnInstruction({ format, isIteration } = {})" in lib
    assert "are the deck and its video from an earlier turn in this session" in lib
    assert "is the composition from an earlier turn in this session" in lib
    server = (Path(__file__).resolve().parents[2] / "adapters" / "pi-render" / "session-server.mjs").read_text()
    assert "exists(join(dir, compositionMarker(format)))" in server, \
        "the adapter must decide author-vs-edit from the directory, not the request"


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_response_carries_the_resolved_session(label, doc):
    # The row that carried the request is gone, so the response carries the resolved
    # session id: a caller that sent none cannot otherwise learn the id its thread was
    # scoped to, and continuing that thread needs it.
    code = _code(doc, "set_result")
    assert "SESSION_ID: sessionId" in code
    assert "build_author_brief" in code and "SESSION_ID" in code


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_raster_is_reviewed_the_same_way_with_a_rewritten_prompt(label, doc):
    # The raster's bytes are made inside n8n, so nothing is fetched back and no still is
    # needed: the data URL the image model returned is what the critic looks at. The fix is a
    # rewritten image prompt, which is what `visual_raster.md`'s feedback block is for.
    assert _targets(doc, "raster_result", 0) == ["prepare_raster_review"]
    assert _targets(doc, "prepare_raster_review", 0) == ["if_raster_review"]
    assert _targets(doc, "if_raster_review", 0) == ["critique_raster"]
    assert _targets(doc, "if_raster_review", 1) == ["merge_branches"], "no image is a review that did not run"
    assert _targets(doc, "critique_raster", 0) == ["parse_raster_verdict"]
    assert _targets(doc, "parse_raster_verdict", 0) == ["if_raster_findings"]
    assert _targets(doc, "if_raster_findings", 0) == ["raster_feedback"]
    assert _targets(doc, "if_raster_findings", 1) == ["merge_branches"]
    assert _targets(doc, "raster_feedback", 0) == ["download_raster_prompt"], "the fix is a rewritten prompt"
    # One critic, one credential, one grammar per medium.
    assert _node(doc, "critique_raster")["credentials"]["httpBearerAuth"]["id"] == _node(doc, "critique")["credentials"]["httpBearerAuth"]["id"]
    assert _node(doc, "critique_raster")["parameters"]["jsonBody"] == "={{ $json.CRITIQUE_BODY }}"
    fetch = _node(doc, "download_raster_review_prompt")["parameters"]["workflowInputs"]["value"]
    assert fetch["template_name"] == "prompts/visual_review_raster.md"
    assert _targets(doc, "download_review_prompt", 0) == ["download_raster_review_prompt"]
    assert _targets(doc, "download_raster_review_prompt", 0) == ["download_registry"]
    # The image, the prompt it came from and the source text are what the critic judges against.
    code = _node(doc, "prepare_raster_review")["parameters"]["jsCode"]
    assert "a.IMAGE" in code and "a.PROMPT" in code and "a.CONTENT" in code
    assert "image_url" in code
    # The bound is the same one, and the round has a home on the item.
    assert "RASTER_REVIEW_ROUND" in _node(doc, "parse_registry")["parameters"]["jsCode"]
    assert "RETRY: verdict === 'fix' && round < cycles" in _node(doc, "parse_raster_verdict")["parameters"]["jsCode"]
    assert "REVIEW: JSON.stringify(" in _node(doc, "parse_raster_verdict")["parameters"]["jsCode"]


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_a_critic_that_cannot_answer_does_not_fail_the_run(label, doc):
    # Measured 2026-10-17 (execution 13762): the critic's second call hit the node timeout and
    # the whole authoring run errored, taking an asset that had already been fixed once with it.
    # The node continues on error, and the verdict node is where the empty answer is handled --
    # which is why the note has to name it.
    for name in ("critique", "critique_raster"):
        node = _node(doc, name)
        assert node["onError"] == "continueRegularOutput", f"{name} would fail the run it was checking"
        assert node["notes"], f"{name} must say where the empty result is handled"
        assert "parse_verdict" in node["notes"] or "parse_raster_verdict" in node["notes"]
        # A four-still critique took 102s on the first call and over 120s on the second.
        assert node["parameters"]["options"]["timeout"] >= 300000, f"{name} would time out on a real critique"
    # And the empty answer is recorded rather than read as a pass.
    for name in ("parse_verdict", "parse_raster_verdict"):
        assert "REVIEW_REASON: unreadable ?" in _code(doc, name)


# ---------------------------------------------------------------------------
# The container across the loop, executed rather than asserted textually.
#
# A review turn's item is asset-shaped, so the honest check is to run the two Code nodes
# with the environment n8n gives them and read the brief they produce: `agent_result`
# builds the asset the loop carries, and `build_author_brief` turns that asset into the
# correction turn's declaration. A missing declaration is a thrown error, which is the
# other half of the contract. n8n runs a Code node as an async body with `$input`, `$`,
# `$env` and `$execution` in scope and `this.helpers` on the instance, so the driver
# supplies exactly those.

NODE_REQUIRED = "node is required to execute the exports' Code nodes"

_DRIVER = r"""
const { readFileSync } = require("node:fs");
const spec = JSON.parse(readFileSync(process.argv[2], "utf8"));
async function main() {
  const out = [];
  for (const c of spec.cases) {
    const nodes = c.nodes || {};
    const $ = (name) => {
      const items = nodes[name];
      if (!items) throw new Error("unknown node " + name);
      return { first: () => items[0], all: () => items };
    };
    const input = c.input || [];
    const $input = { first: () => input[0], all: () => input };
    const $json = input[0] || {};
    const $env = c.env || {};
    const $execution = c.execution || { id: "1" };
    const helpers = {};
    try {
      const fn = new Function("$", "$input", "$json", "$env", "$execution", "helpers",
        "\"use strict\"; return (async function(){\n" + c.code + "\n}).call({ helpers });");
      const result = await fn($, $input, $json, $env, $execution, helpers);
      out.push({ ok: true, items: JSON.parse(JSON.stringify(result || [])) });
    } catch (e) {
      out.push({ ok: false, error: String((e && e.message) || e) });
    }
  }
  process.stdout.write(JSON.stringify(out));
}
main();
"""


def _exec_code(cases):
    with tempfile.TemporaryDirectory() as td:
        driver = Path(td) / "driver.cjs"
        driver.write_text(_DRIVER)
        spec = Path(td) / "spec.json"
        spec.write_text(json.dumps({"cases": cases}))
        done = subprocess.run(["node", str(driver), str(spec)], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


# What the composer's brief carries for a ``tiles_wide`` request: the type's own container,
# as ``parse_registry`` fills it (16:9, viewport 1280, 12 s, 360 frames at 30 fps).
_TILES_WIDE = {
    "ASSET_TYPE": "tiles_wide", "RENDER_MODE": "video", "FORMAT": "mp4", "FORM": "tiles",
    "ASPECT": "16:9", "VIEWPORT": "1280", "FRAMES": "360", "DURATION_SECONDS": "12", "FPS": "30",
    "WIDTH": "1280", "HEIGHT": "720", "SCENE_SECONDS": 0, "REVIEW_ROUND": 0, "FEEDBACK": "",
    "SESSION_ID": "tiles_wide-13785", "AUTHOR_URL": "http://pi/v1/chat/completions",
    "STORE_URL": "http://utils/mcp", "PAIRED_ARTIFACT_URL": "",
}
# The request the two nodes share, as ``normalize_input`` emits it.
_REQUEST = {"RUN_ID": "13785", "CONTENT": "a tiling loop", "SESSION_ID": "", "FEEDBACK": "",
            "EXTRA_PROMPT": "", "FORCE": "auto", "SCENES": "", "REVIEW_CYCLES": 2}
_ENV = {"PI_RENDER_URL": "http://pi", "MCP_UTILS_URL": "http://utils"}


def _brief_nodes():
    return {
        "normalize_input": [{"json": dict(_REQUEST)}],
        "brand_tokens": [{"json": {"STYLE": "dark", "BRAND": "the brand block"}}],
        "visual_rules": [{"json": {"RULES": "the motion rules"}}],
        "scene_rules": [{"json": {"SCENE": "the scene contract"}}],
        "visual_forms": [{"json": {"FORMS": "the form vocabulary"}}],
    }


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def test_the_asset_names_the_authoring_failure_rather_than_the_missing_artifact():
    # Three shapes of the same call: a 4xx body, a transport failure, and a success. The first
    # two are why the asset's ERROR must prefer the authoring call over the store's own verdict.
    doc = json.loads(STUDIO.read_text())
    cases = [
        {
            # The session answered before any turn started: `neverError` puts the body in the item.
            "execute_author": [{"json": {"error": {"message": "EEXIST: file already exists, mkdir '/tmp/x/runs/lips-106'"}}}],
            "store_artifact": [{"json": {"result": {"content": [
                {"text": "ERROR: /artifacts/lips-106/out.mp4 answered HTTP 404. Nothing was stored."}
            ]}}}],
        },
        {
            # A transport failure reaches the error output as `{error}` and the store never ran.
            "execute_author": [{"json": {"error": {"message": "timeout of 1200000ms exceeded", "name": "Error"}}}],
        },
        {
            "execute_author": [{"json": {"choices": [{"message": {"content": "storyboard"}}]}}],
            "store_artifact": [{"json": {"result": {"content": [
                {"text": "key=visual-studio/14801-tiles_wide.mp4 bytes=9 content-type=video/mp4"}
            ]}}}],
        },
    ]
    out = _exec_code([
        {
            "code": _code(doc, "agent_result"),
            "nodes": {"build_author_brief": [{"json": dict(_TILES_WIDE)}], **case},
            "env": _ENV,
            "execution": {"id": "14801"},
        }
        for case in cases
    ])
    body, transport, ok = (case["items"][0]["json"] for case in out)
    assert body["STATUS"] == "ERROR" and "EEXIST" in body["ERROR"], body["ERROR"]
    assert "404" not in body["ERROR"], "the symptom outranks the cause"
    assert transport["STATUS"] == "ERROR" and "timeout" in transport["ERROR"].lower(), transport["ERROR"]
    assert ok["STATUS"] == "RENDERED" and ok["S3_KEY"] == "visual-studio/14801-tiles_wide.mp4"


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def test_a_correction_turn_keeps_the_container_the_request_declared():
    # The measurement this fixes: run 13785's correction turns were asked for
    # 1080x1350 / 3 s / 24 frames for a request whose registry entry says the container
    # asserted below. `agent_result` builds the asset the review loop carries; feeding that
    # asset to `build_author_brief` is the correction turn's own input.
    doc = json.loads(STUDIO.read_text())
    built = _exec_code([{
        "code": _code(doc, "agent_result"),
        "nodes": {
            "build_author_brief": [{"json": dict(_TILES_WIDE)}],
            "execute_author": [{"json": {
                "choices": [{"message": {"content": "storyboard: a tiling loop"}}],
                "conformance": {"fit": "scale", "authored": "1920x1080", "short": False},
            }}],
            "store_artifact": [{"json": {"result": {"content": [
                {"text": "key=visual-studio/13785-tiles_wide.mp4 bytes=9 content-type=video/mp4"}
            ]}}}],
        },
        "env": _ENV,
        "execution": {"id": "13785"},
    }])[0]
    assert built["ok"], built.get("error")
    asset = built["items"][0]["json"]
    # The asset names the declaration beside what the runtime delivered.
    assert (asset["ASPECT"], asset["VIEWPORT"], asset["FRAMES"], asset["DURATION_SECONDS"], asset["FPS"]) == (
        "16:9", "1280", "360", "12", "30"
    )
    assert (asset["WIDTH"], asset["HEIGHT"]) == ("1280", "720")
    assert asset["CONFORMED"] == "scale" and asset["AUTHORED_FRAME"] == "1920x1080"

    brief = _exec_code([{
        "code": _code(doc, "build_author_brief"),
        "input": [{"json": asset}],
        "nodes": _brief_nodes(),
        "env": _ENV,
    }])[0]
    assert brief["ok"], brief.get("error")
    out = brief["items"][0]["json"]
    # The correction turn declares the type's container, not the defaults it used to invent.
    assert (out["WIDTH"], out["HEIGHT"], out["FRAMES"], out["DURATION_SECONDS"], out["FPS"]) == (1280, 720, 360, 12, 30)
    assert '"width":1280' in out["AUTHOR_BODY"] and '"height":720' in out["AUTHOR_BODY"]
    assert '"frames":360' in out["AUTHOR_BODY"] and '"durationSeconds":12' in out["AUTHOR_BODY"]


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
@pytest.mark.parametrize("missing", ["ASPECT", "VIEWPORT", "FRAMES", "DURATION_SECONDS"])
def test_the_brief_refuses_a_turn_with_no_declared_container(missing):
    # Absence is expressible: a plausible default is indistinguishable from the caller's
    # request once the run has produced an artifact, so a missing field stops the turn.
    doc = json.loads(STUDIO.read_text())
    item = dict(_TILES_WIDE, **_REQUEST)
    item.pop(missing)
    result = _exec_code([{
        "code": _code(doc, "build_author_brief"),
        "input": [{"json": item}],
        "nodes": _brief_nodes(),
        "env": _ENV,
    }])[0]
    assert result["ok"] is False, f"a turn without {missing} was briefed anyway"
    assert missing in result["error"], result["error"]
    assert "cannot re-declare a container" in result["error"]
