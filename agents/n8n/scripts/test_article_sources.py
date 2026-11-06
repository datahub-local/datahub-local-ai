"""The ledger check in the drafting gate and its twin in the improvement pass.

`parse_article` and `check_improved_draft` are the two places an article's fenced blocks meet
`sources.json`. The server rewrites the ledger and drops a URL that did not answer, so the
checks here are about what n8n does with the ledger it was handed: a block absent from it, a
block the page did not carry, a dry-run that failed. `check_improved_draft` must answer the
same for the ledger stored on the row, and must report a missing cell as not run rather than
silently passing it.

Offline: the two committed Code nodes, executed with a stubbed n8n context.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[1]  # agents/n8n
WORKFLOWS = BASE / "workflows"
CREATOR = WORKFLOWS / "article_creator.workflow.json"
ENTRY = WORKFLOWS / "article_content_writer.workflow.json"
NODE_REQUIRED = "node is required to execute a Code node"

BLOCK = "kubectl apply -f https://example.test/install.yaml"
ARTICLE_BODY = (
    "Install it.\n\n"
    "<!-- asset:svg_wide -->\n\n"
    "```bash\n" + BLOCK + "\n```\n\n"
    "That is all.\n"
)
ARTICLE = "# Install\n\n" + ARTICLE_BODY
LEDGER_ENTRY = {
    "block": BLOCK,
    "url": "https://example.test/docs",
    "found": True,
    "sha256": "a" * 64,
    "excerpt": "kubectl apply -f   https://example.test/install.yaml",
    "status": 200,
    "body_sha256": "b" * 64,
    "validated": "none",
    "validation_error": "",
}


def _node(path, name):
    return next(n for n in json.loads(path.read_text(encoding="utf-8"))["nodes"] if n["name"] == name)


def _run(path, name, scope, incoming):
    code = _node(path, name)["parameters"]["jsCode"]
    harness = (
        """
const scope = %s; const incoming = %s;
const $ = (n) => {
  if (!(n in scope)) throw new Error('the test did not provide node ' + n);
  const items = scope[n].map((json) => ({ json }));
  return { isExecuted: true, first: () => items[0], last: () => items[items.length - 1],
           all: () => items, item: items[0] };
};
const $input = { all: () => incoming.map((json) => ({ json })), first: () => ({ json: incoming[0] }) };
const $json = incoming[0];
const console = { log: () => {} };
const fn = new Function('$', 'console', '$input', '$json', %s);
process.stdout.write(JSON.stringify(fn($, console, $input, $json)));
"""
    ) % (json.dumps(scope), json.dumps(incoming), json.dumps(code))
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write(harness)
        handle = fh.name
    try:
        done = subprocess.run(["node", handle], capture_output=True, text=True, check=False)
    finally:
        Path(handle).unlink()
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def _parse(article, ledger, present=True):
    scope = {
        "set_workflow_vars": [{"MAX_WORDS": 1200}],
        "main_trigger": [{"ASSET_TYPES": "svg_wide"}],
        "fetch_article": [{"statusCode": 200, "data": article}],
    }
    if present:
        scope["fetch_sources"] = [{"statusCode": 200, "data": json.dumps(ledger)}]
    return _run(CREATOR, "parse_article", scope, [{}])["json"]


def _improved(draft, ledger=None, feedback="", base="The draft before the edit."):
    ctx = {
        "MAX_WORDS": 1200,
        "ASSET_TYPES": "svg_wide",
        "BASE_TITLE": "Install",
        "BASE_TEXT": base,
        "ENTRY_ID": "e1",
        "HAS_FEEDBACK": bool(feedback),
        "FEEDBACK": feedback,
    }
    if ledger is not None:
        ctx["SOURCES"] = json.dumps(ledger)
    return _run(
        ENTRY,
        "check_improved_draft",
        {"build_improvement_context": [ctx]},
        [{"output": "<article>\n" + draft + "\n</article>"}],
    )[0]["json"]


def _select(item, ctx):
    return _run(
        ENTRY,
        "select_final_draft",
        {"build_improvement_context": [ctx], "merge_aspect_findings": [{"FINDINGS_SUMMARY": ""}]},
        [item],
    )[0]["json"]


def _ledger(*entries):
    return {"sources": list(entries)}


pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)


def test_a_ledgered_block_passes_and_is_counted():
    item = _parse(ARTICLE, _ledger(LEDGER_ENTRY))
    assert item["PROBLEM"] == ""
    assert item["FIDELITY"] == "checked"
    assert item["SOURCES_NOTE"] == "SOURCES: 1 quoted"
    assert json.loads(item["SOURCES"])["sources"][0]["url"] == "https://example.test/docs"
    assert "kubectl apply -f https://example.test/install.yaml" in item["SOURCES_TEXT"]
    assert "https://example.test/docs" in item["SOURCES_TEXT"]


def test_whitespace_differences_still_match():
    """The docs render the same YAML with other indentation; the block is the unit, not the line."""
    indented = ARTICLE.replace(
        "```bash\n" + BLOCK + "\n```",
        "```bash\n" + BLOCK.replace(" -f ", "\n  -f  ") + "\n```",
    )
    item = _parse(indented, _ledger(LEDGER_ENTRY))
    assert item["PROBLEM"] == "", item["PROBLEM"]


def test_a_block_absent_from_the_ledger_is_rejected_naming_it():
    item = _parse(ARTICLE.replace(BLOCK, "kubectl delete -f /tmp/never-read.yaml"), _ledger())
    assert item["PROBLEM"].startswith("UNQUOTED:")
    assert "kubectl delete -f /tmp/never-read.yaml" in item["PROBLEM"]


def test_a_dropped_entry_is_rejected():
    """The server drops a URL that did not answer, so the block it carried has no entry."""
    item = _parse(ARTICLE, _ledger())
    assert item["PROBLEM"].startswith("UNQUOTED:")
    assert "not in sources.json" in item["PROBLEM"]


def test_an_entry_the_server_did_not_find_is_rejected():
    item = _parse(ARTICLE, _ledger(dict(LEDGER_ENTRY, found=False, excerpt="")))
    assert item["PROBLEM"].startswith("SOURCE_NOT_FOUND:")
    assert "https://example.test/docs" in item["PROBLEM"]


def test_a_block_the_page_did_not_carry_is_rejected():
    """The ledger's block matches but its excerpt is a different page: the edit is unverified."""
    item = _parse(ARTICLE, _ledger(dict(LEDGER_ENTRY, excerpt="kubectl apply -f https://other.test/x")))
    assert item["PROBLEM"].startswith("UNQUOTED:")
    assert "no longer matches https://example.test/docs" in item["PROBLEM"]


def test_a_failed_dry_run_is_rejected_naming_the_failure():
    entry = dict(LEDGER_ENTRY, validated="dry-run", validation_error="error: could not parse YAML")
    item = _parse(ARTICLE, _ledger(entry))
    assert item["PROBLEM"].startswith("VALIDATION_FAILED:")
    assert "could not parse YAML" in item["PROBLEM"]
    assert "kubectl apply -f https://example.test/install.yaml" in item["PROBLEM"]


def test_a_prose_draft_with_no_ledger_may_not_fence():
    prose = "# Install\n\nNo command was found.\n\n<!-- asset:svg_wide -->\n"
    assert _parse(prose, _ledger())["PROBLEM"] == ""
    assert _parse(prose, _ledger())["FIDELITY"] == "checked"
    fenced = _parse(ARTICLE, _ledger())
    assert fenced["PROBLEM"].startswith("UNQUOTED:")


def test_a_missing_ledger_accepts_prose_and_rejects_a_fence():
    prose = "# Install\n\nNo command was found.\n\n<!-- asset:svg_wide -->\n"
    item = _parse(prose, _ledger(), present=False)
    assert item["PROBLEM"] == ""
    assert item["FIDELITY"] == "not run"
    assert item["SOURCES"] == ""
    item = _parse(ARTICLE, _ledger(), present=False)
    assert item["PROBLEM"].startswith("SOURCES: sources.json could not be read")


def test_a_refused_session_is_reported_as_data():
    scope = {
        "set_workflow_vars": [{"MAX_WORDS": 1200}],
        "main_trigger": [{"ASSET_TYPES": "svg_wide"}],
        "request_article": [{"statusCode": 400, "data": json.dumps({"error": {"message": "messages is required"}})}],
        "fetch_article": [{"statusCode": 404, "data": "not found"}],
    }
    item = _run(CREATOR, "parse_article", scope, [{}])["json"]
    assert item["PROBLEM"] == "SESSION: HTTP 400: messages is required"


def test_a_failed_article_fetch_is_reported_as_data():
    """A 200 turn whose article.md fetch failed must name the fetch, not the missing H1."""
    scope = {
        "set_workflow_vars": [{"MAX_WORDS": 1200}],
        "main_trigger": [{"ASSET_TYPES": "svg_wide"}],
        "request_article": [{"statusCode": 200, "data": "{\"ok\":true}"}],
        "fetch_article": [{"statusCode": 404, "data": "not found"}],
    }
    item = _run(CREATOR, "parse_article", scope, [{}])["json"]
    assert item["PROBLEM"] == "DRAFT: HTTP 404: not found"


def test_a_body_shaped_answer_still_drafts():
    """The older `body` key stays readable for a node configured that way."""
    prose = "# Install\n\nInstall it.\n\n<!-- asset:svg_wide -->"
    scope = {
        "set_workflow_vars": [{"MAX_WORDS": 1200}],
        "main_trigger": [{"ASSET_TYPES": "svg_wide"}],
        "fetch_article": [{"statusCode": 200, "body": prose}],
    }
    item = _run(CREATOR, "parse_article", scope, [{}])["json"]
    assert item["TITLE"] == "Install"
    assert item["PROBLEM"] == ""


def test_the_twin_agrees_on_the_same_fixtures():
    assert _improved(ARTICLE, _ledger(LEDGER_ENTRY))["PROBLEM"] == ""
    assert _improved(ARTICLE, _ledger(LEDGER_ENTRY))["FIDELITY"] == "checked"
    assert _improved(ARTICLE, _ledger())["PROBLEM"].startswith("UNQUOTED:")
    assert _improved(ARTICLE, _ledger(dict(LEDGER_ENTRY, found=False)))["PROBLEM"].startswith(
        "SOURCE_NOT_FOUND:"
    )
    assert _improved(ARTICLE, _ledger(dict(LEDGER_ENTRY, validation_error="bad yaml")))[
        "PROBLEM"
    ].startswith("VALIDATION_FAILED:")
    assert _improved(ARTICLE, _ledger(dict(LEDGER_ENTRY, excerpt="something else")))[
        "PROBLEM"
    ].startswith("UNQUOTED:")


def test_the_twin_reports_a_missing_ledger_as_not_run():
    """A row stored before this change has no SOURCES: the edit is taken, the check is not."""
    item = _improved(ARTICLE)
    assert item["PROBLEM"] == ""
    assert item["FIDELITY"] == "not run"
    assert item["SOURCES"] == ""
    prose = "# Install\n\nNo command was found.\n\n<!-- asset:svg_wide -->"
    assert _improved(prose)["PROBLEM"] == ""
    assert _improved(prose)["FIDELITY"] == "not run"


def test_a_feedback_round_accepts_a_block_no_source_carries():
    """The human asked for the command, so it is written and counted rather than rejected."""
    draft = ARTICLE.replace("That is all.", "```bash\nkind create cluster\n```\n\nThat is all.")
    item = _improved(draft, _ledger(LEDGER_ENTRY), feedback="share the commands to create the cluster")
    assert item["PROBLEM"] == "", item["PROBLEM"]
    assert item["UNVERIFIED"] == 1
    assert item["FIDELITY"] == "feedback"


def test_a_first_draft_edit_still_rejects_a_block_no_source_carries():
    draft = ARTICLE.replace("That is all.", "```bash\nkind create cluster\n```\n\nThat is all.")
    item = _improved(draft, _ledger(LEDGER_ENTRY))
    assert item["PROBLEM"].startswith("UNQUOTED:")
    assert "kind create cluster" in item["PROBLEM"]


def test_a_feedback_round_still_rejects_a_ledgered_block_the_page_lost():
    item = _improved(ARTICLE, _ledger(dict(LEDGER_ENTRY, found=False)), feedback="apply my changes")
    assert item["PROBLEM"].startswith("SOURCE_NOT_FOUND:")


def test_an_unchanged_edit_is_reported_as_unchanged():
    item = _improved(ARTICLE, _ledger(LEDGER_ENTRY), feedback="apply my changes", base=ARTICLE_BODY)
    assert item["PROBLEM"] == ""
    assert item["UNCHANGED"] is True
    assert item["UNVERIFIED"] == 0


def test_an_unchanged_edit_is_not_an_improvement():
    ctx = {
        "MAX_WORDS": 1200,
        "ASSET_TYPES": "svg_wide",
        "BASE_TITLE": "Install",
        "BASE_TEXT": ARTICLE_BODY,
        "ENTRY_ID": "e1",
        "HAS_FEEDBACK": True,
    }
    item = {
        "IMPROVED_TEXT": ARTICLE_BODY.strip(),
        "IMPROVED_TITLE": "Install",
        "WORD_COUNT": 10,
        "PROBLEM": "",
        "UNCHANGED": True,
        "UNVERIFIED": 0,
    }
    out = _select(item, ctx)
    assert out["IMPROVED"] == "UNCHANGED"
    assert out["text"] == ARTICLE_BODY
    assert "unchanged" in out["IMPROVEMENT_NOTE"]


def test_the_unverified_count_reaches_the_converged_draft():
    ctx = {
        "MAX_WORDS": 1200,
        "ASSET_TYPES": "svg_wide",
        "BASE_TITLE": "Install",
        "BASE_TEXT": ARTICLE_BODY,
        "ENTRY_ID": "e1",
        "HAS_FEEDBACK": True,
    }
    item = {
        "IMPROVED_TEXT": ARTICLE_BODY + "\n\n```bash\nkind create cluster\n```\n",
        "IMPROVED_TITLE": "Install",
        "WORD_COUNT": 10,
        "PROBLEM": "",
        "UNCHANGED": False,
        "UNVERIFIED": 1,
        "FIDELITY": "feedback",
    }
    out = _select(item, ctx)
    assert out["IMPROVED"] == "IMPROVED"
    assert out["UNVERIFIED"] == 1
    assert "not checked against a source" in out["IMPROVEMENT_NOTE"]
