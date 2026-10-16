"""Guard the research workflow the article writer calls as a tool.

`Content Research` searches Hacker News and the author's own Miniflux feeds and returns one
digest. It exists because the writer researches with tools, and the tool node types are
constrained: the agent hands a tool call to the workflow engine, which needs an `execute`
method, and `toolHttpRequest` in this build has only `supplyData` -- so an HTTP tool cannot
carry the search (measured, execution 13598: every call died and the draft came back empty).
A workflow tool keeps the HTTP detail in one place and hands the model a digest instead of
two raw API payloads.

No source here needs an API key. The feed half reuses the same Miniflux env and base64 auth
idiom the `Content Feed Curator` uses, so there is one way to reach that service rather than
two.
"""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]  # agents/n8n
WORKFLOWS = BASE / "workflows"
RESEARCH = WORKFLOWS / "content_research.workflow.json"
CREATOR = WORKFLOWS / "article_creator.workflow.json"


def _research() -> dict:
    return json.loads(RESEARCH.read_text(encoding="utf-8"))


def _node(name: str) -> dict:
    for node in _research()["nodes"]:
        if node["name"] == name:
            return node
    raise KeyError(name)


def test_trigger_takes_one_query():
    declared = {value["name"] for value in _node("main_trigger")["parameters"]["workflowInputs"]["values"]}
    assert declared == {"QUERY"}


def test_a_blank_query_is_refused_by_name():
    # An empty search reported as "no results" reads as a finding; it is a bug in the caller.
    code = _node("normalize_input")["parameters"]["jsCode"]
    assert "QUERY is required" in code
    assert "throw" in code


def test_both_sources_answer_without_an_api_key():
    search = _node("search_hn")["parameters"]
    assert "hn.algolia.com" in search["url"]
    assert search["method"] == "GET"
    feeds = _node("search_feeds")["parameters"]
    assert 'MINIFLUX_URL' in feeds["url"]
    # The curator's idiom, not a second way to reach the same service.
    assert "base64Encode" in feeds["headerParameters"]["parameters"][0]["value"]
    assert "MINIFLUX_API_USER" in feeds["headerParameters"]["parameters"][0]["value"]


def test_a_dead_source_is_reported_rather_than_hidden():
    # `continueRegularOutput` forwards the node's input unchanged, so a failure leaves no marker
    # on the item: the digest reads each source by node name and says which one did not answer.
    for name in ("search_hn", "search_feeds"):
        node = _node(name)
        assert node["onError"] == "continueRegularOutput"
        assert node.get("notes")
    code = _node("build_digest")["parameters"]["jsCode"]
    assert "readNode('search_hn')" in code
    assert "readNode('search_feeds')" in code
    assert "Unavailable this run" in code
    assert "No source answered" in code


def test_the_digest_runs_even_when_no_source_answers():
    # Otherwise a total search outage skips the node and the writer gets an empty tool result.
    assert _node("build_digest")["alwaysOutputData"] is True


def test_both_searches_run_from_one_query():
    edges = {
        edge["node"]
        for branches in _research()["connections"]["normalize_input"]["main"]
        for edge in branches
    }
    assert edges == {"search_hn", "search_feeds"}
    for name in ("search_hn", "search_feeds"):
        assert _research()["connections"][name]["main"][0][0]["node"] == "build_digest"


def test_a_sub_workflow_raises_instead_of_notifying():
    settings = _research()["settings"]
    assert "errorWorkflow" not in settings
    assert _research().get("activeVersion")


def test_the_writer_points_at_this_workflow():
    creator = json.loads(CREATOR.read_text(encoding="utf-8"))
    tool = next(node for node in creator["nodes"] if node["name"] == "research_sources")
    assert tool["parameters"]["workflowId"]["value"] == _research()["id"]
