"""Guard the agent-author branch of Visual Studio.

An `author: agent` type is produced by sending the request's CONTENT (the brief)
to the pi-render session and returning the fetched artifact as the asset. The
workflow builds no markup and captures no frames for it, and it never receives the
agent's composition -- only the rendered file. Those are properties of the graph,
so they are asserted here, offline, against the committed export.

Both copies of the graph are checked -- the exports carry their nodes twice, at
the top level and inside ``activeVersion``, and a fix applied to one copy is a
live bug.
"""

import json
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"
STUDIO = WORKFLOWS / "visual_studio.workflow.json"
TYPES = WORKFLOWS.parent / "datasets" / "visual_types.json"

AGENT_TYPE = "diagram_agent"


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
def test_agent_types_are_routed_to_the_agent_branch(label, doc):
    conns = doc["connections"]
    assert conns["parse_registry"]["main"][0][0]["node"] == "if_agent"
    true_branch, false_branch = conns["if_agent"]["main"]
    assert true_branch[0]["node"] == "build_author_brief"
    # Everything that is not agent-authored keeps flowing to the spec path.
    assert false_branch[0]["node"] == "pick_spec_type"
    assert _node(doc, "if_agent")["parameters"]["conditions"]["conditions"][0]["leftValue"] == (
        "={{ $json.AUTHOR === 'agent' }}"
    )


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_agent_branch_reaches_the_merge(label, doc):
    conns = doc["connections"]
    assert conns["build_author_brief"]["main"][0][0]["node"] == "execute_author"
    assert conns["execute_author"]["main"][0][0]["node"] == "fetch_artifact"
    assert conns["fetch_artifact"]["main"][0][0]["node"] == "agent_result"
    assert conns["agent_result"]["main"][0][0]["node"] == "merge_branches"


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_a_failed_authoring_is_continued_and_handled(label, doc):
    # continueRegularOutput makes a failure invisible unless a downstream node
    # consumes the empty result, so both halves are required. The agent is a
    # model call that can fail or time out, so its failure must cost one asset.
    assert _node(doc, "execute_author").get("onError") == "continueRegularOutput"
    assert _node(doc, "fetch_artifact").get("onError") == "continueRegularOutput"
    code = _node(doc, "agent_result")["parameters"]["jsCode"]
    assert "STATUS: 'ERROR'" in code
    assert "bin" in code
    assert "PI_RENDER_URL" in code


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_only_the_brief_crosses_to_the_agent(label, doc):
    body = _node(doc, "build_author_brief")["parameters"]["jsCode"]
    # The request is the brief plus the output kind; no markup is sent.
    assert "AUTHOR_BODY" in body
    assert "req.CONTENT" in body
    assert "messages:" in body and "session_id" in body and "format" in body
    for forbidden in ('"html"', '"markup"', '"script"', '"css"'):
        assert forbidden not in body
    assert _node(doc, "execute_author")["parameters"]["jsonBody"] == "={{ $json.AUTHOR_BODY }}"


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_the_result_is_content_not_a_reference(label, doc):
    # The studio returns asset content, never a URL; the agent path must too.
    code = _node(doc, "agent_result")["parameters"]["jsCode"]
    assert "IMAGE: 'data:'" in code
    assert "ARTIFACT_URL" not in code


@pytest.mark.parametrize("label,doc", list(_copies()))
def test_merge_assets_skips_agent_types(label, doc):
    # merge_assets loops every registry item; agent types are produced by the
    # branch off parse_registry, so emitting them here would duplicate them.
    code = _node(doc, "merge_assets")["parameters"]["jsCode"]
    assert "a.AUTHOR === 'agent'" in code and "continue" in code


def test_the_agent_type_is_declared():
    registry = json.loads(TYPES.read_text())
    entries = [t for t in registry["types"] if t["id"] == AGENT_TYPE]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["author"] == "agent"
    assert entry["render"] == "agent"
    assert entry["format"] == "gif"
    assert entry["specTemplate"] is None, "the agent takes the brief, not a content spec"
