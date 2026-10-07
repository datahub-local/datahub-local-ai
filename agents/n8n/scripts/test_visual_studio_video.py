"""Guard the render-service video branch of Visual Studio.

A video type is produced by POSTing the validated content spec to the render
service and returning the MP4; the workflow builds no markup and captures no
frames for it. The premises are properties of the graph, so they are asserted
here, offline, against the committed export.

Both copies of the graph are checked -- the exports carry their nodes twice, at
the top level and inside ``activeVersion``, and a fix applied to one copy is a
live bug.

The last test is the trust boundary: the request the workflow sends must be a
spec and nothing executable, which is what lets the service refuse caller markup.
"""

import json
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"
STUDIO = WORKFLOWS / "visual_studio.workflow.json"
HARNESS = WORKFLOWS / "visual_studio_test.workflow.json"
TYPES = WORKFLOWS.parent / "datasets" / "visual_types.json"


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


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_video_is_routed_to_the_service_branch(label, doc):
    conns = doc["connections"]
    assert conns["merge_assets"]["main"][0][0]["node"] == "if_video"
    true_branch, false_branch = conns["if_video"]["main"]
    assert true_branch[0]["node"] == "build_video"
    assert false_branch[0]["node"] == "if_raster"


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_service_branch_reaches_the_merge(label, doc):
    conns = doc["connections"]
    assert conns["build_video"]["main"][0][0]["node"] == "render_video"
    assert conns["render_video"]["main"][0][0]["node"] == "video_result"
    out = conns["video_result"]["main"][0][0]
    assert out["node"] == "merge_branches"


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_a_failed_render_is_continued_and_handled(label, doc):
    # continueRegularOutput makes a failure invisible unless a downstream node
    # consumes the empty result, so both halves are required.
    assert _node(doc, "render_video").get("onError") == "continueRegularOutput"
    code = _node(doc, "video_result")["parameters"]["jsCode"]
    assert "STATUS: 'ERROR'" in code
    assert "bin" in code
    # Binary is read through the helper: this instance stores it out of band, so
    # binary.data is a reference and concatenating it corrupts the asset.
    assert "getBinaryDataBuffer(0, 'data')" in code
    assert "bin.data" not in code


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_only_a_spec_crosses_to_the_service(label, doc):
    body = _node(doc, "build_video")["parameters"]["jsCode"]
    # The request body is the spec plus render options, and nothing executable.
    assert "RENDER_BODY" in body
    assert "spec: spec" in body
    for forbidden in ("html", "markup", "composition", "script"):
        assert f"{forbidden}:" not in body
    assert _node(doc, "render_video")["parameters"]["jsonBody"] == "={{ $json.RENDER_BODY }}"


def test_the_video_type_is_declared():
    registry = json.loads(TYPES.read_text())
    video = [t for t in registry["types"] if t["id"] == "diagram_video"]
    assert len(video) == 1
    assert video[0]["render"] == "video"
    assert video[0]["format"] == "mp4"
    assert video[0]["author"] == "spec_service"


def test_unknown_types_are_reported_not_crashed():
    # parse_registry's note() covers UNKNOWN and over-cap types. A bare `STATUS`
    # shorthand there is undefined and aborts the whole run with a 500 instead of
    # reporting the type, which is how a not-yet-published registry entry showed
    # up as a server error rather than "unknown asset type".
    doc = json.loads(STUDIO.read_text())
    for node in doc["nodes"]:
        if node["name"] == "parse_registry":
            code = node["parameters"]["jsCode"]
            assert "STATUS: status" in code
            assert "STATUS, ERROR" not in code


def test_existing_renderers_are_untouched():
    # The raster and in-workflow animated branches must still exist unchanged.
    for _, doc in _copies():
        assert _node(doc, "if_raster")["parameters"]["conditions"]["conditions"][0]["leftValue"]
        assert _node(doc, "if_animated")["parameters"]["conditions"]["conditions"][0]["leftValue"]
        assert "merge_assets" in doc["connections"]


def test_the_test_harness_names_an_mp4_download():
    # Visual Studio Test maps an asset's content type to a file extension for the
    # download URL it hands back. Without a `video/mp4` case an MP4 asset is named
    # `diagram_video.png`, so the saved file's extension lies about its bytes.
    doc = json.loads(HARNESS.read_text())
    copies = [("top", doc)]
    if isinstance(doc.get("activeVersion"), dict) and "nodes" in doc["activeVersion"]:
        copies.append(("activeVersion", doc["activeVersion"]))
    for label, c in copies:
        code = _node(c, "unpack_assets")["parameters"]["jsCode"]
        assert "ct === 'video/mp4' ? 'mp4'" in code, f"{label}: unpack_assets has no mp4 extension"
