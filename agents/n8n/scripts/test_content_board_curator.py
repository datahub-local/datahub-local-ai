"""The GitHub board intake and the queue's age ceiling.

Offline: reads the committed exports and datasets, and executes the two Code nodes whose
decisions are invisible in the graph (which issues are new, which rows are past the
ceiling) against stubs. The board itself is not contacted - the read is asserted from the
node's own parameters, because what it filters on is the thing that decides the output.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

AGENTS = Path(__file__).resolve().parents[1]
WORKFLOWS = AGENTS / "workflows"
BOARD = json.loads((WORKFLOWS / "content_board_curator.workflow.json").read_text())
CURATOR = json.loads((WORKFLOWS / "content_feed_curator.workflow.json").read_text())
BOARD_CFG = json.loads((AGENTS / "datasets" / "board_intake.json").read_text())
CURATOR_CFG = json.loads((AGENTS / "datasets" / "curator_config.json").read_text())
BLOG_CATEGORIES = json.loads((AGENTS / "datasets" / "blog_categories.json").read_text())["categories"]
CATCH_ERRORS_ID = "fejq5nN6LP3F820w"

NODE_REQUIRED = "node is required to execute a Code node's decisions"

# n8n runs a Code node inside an async wrapper with `$`, `$input` and `$execution` in
# scope; this is the smallest version of that scope the two nodes under test use.
RUNNER = r"""
async function __n8n_main__() {
  const stubs = JSON.parse(process.env.STUBS || '{}');
  const $ = (name) => {
    const items = (stubs.nodes && stubs.nodes[name]) || [];
    return {
      first: () => ({ json: items[0] || {} }),
      all: () => items.map((j) => ({ json: j })),
      item: { json: items[0] || {} },
    };
  };
  const $input = { all: () => ((stubs.input || []).map((j) => ({ json: j }))) };
  const $execution = { id: stubs.execution_id || '1' };
  const console = { log: () => {}, warn: () => {}, error: () => {} };
  const __result = await (async () => {
__CODE__
  })();
  process.stdout.write(JSON.stringify(__result));
}
__n8n_main__().catch((e) => { process.stderr.write(String((e && e.stack) || e)); process.exit(1); });
"""


def _nodes(doc, copy="nodes"):
    if copy == "nodes":
        return doc["nodes"]
    return (doc.get("activeVersion") or {}).get("nodes") or []


def _node(doc, name, copy="nodes"):
    for node in _nodes(doc, copy):
        if node["name"] == name:
            return node
    raise AssertionError(f"no node {name!r} in {copy}")


def _js(doc, name, copy="nodes"):
    return _node(doc, name, copy)["parameters"]["jsCode"]


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def _run(code, nodes=None, input_=None, execution_id="1"):
    src = RUNNER.replace("__CODE__", code)
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False) as fh:
        fh.write(src)
        path = fh.name
    env = dict(
        os.environ,
        STUBS=json.dumps({"nodes": nodes or {}, "input": input_ or [], "execution_id": execution_id}),
    )
    try:
        done = subprocess.run(["node", path], capture_output=True, text=True, env=env, check=False)
    finally:
        Path(path).unlink()
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def _items(result):
    return [item["json"] for item in result]


# --------------------------------------------------------------------------- intake

def test_the_entry_point_is_scheduled_and_reports_its_failure():
    trigger = _node(BOARD, "schedule_trigger")
    assert trigger["type"] == "n8n-nodes-base.scheduleTrigger"
    # A manual trigger alongside it, so the editor's Execute workflow can force a run
    # without waiting for the daily tick.
    assert _node(BOARD, "click_trigger")["type"] == "n8n-nodes-base.manualTrigger"
    # An entry point carries errorWorkflow (nothing upstream could report for it), and the
    # target must be a workflow the repository has, or it is a call the backup cannot restore.
    assert BOARD["settings"]["errorWorkflow"] == CATCH_ERRORS_ID
    ids = {
        json.loads(p.read_text()).get("id")
        for p in WORKFLOWS.glob("*.workflow.json")
    }
    assert CATCH_ERRORS_ID in ids


def test_the_board_is_read_by_label_and_never_written():
    node = _node(BOARD, "list_board_issues")
    assert node["type"] == "n8n-nodes-base.github"
    params = node["parameters"]
    # Listing issues of a repository is the `getIssues` operation, not an `issue` one.
    assert (params["resource"], params["operation"]) == ("repository", "getIssues")
    assert params["owner"]["value"] == "={{ $json.owner }}"
    assert params["repository"]["value"] == "={{ $json.repo }}"
    filters = params["getRepositoryIssuesFilters"]
    assert filters["state"] == "={{ $json.state }}"
    assert filters["labels"] == "={{ $json.label }}"
    # An empty board must not stop the run, or the ceiling below would never run on a quiet week.
    assert node["alwaysOutputData"] is True
    assert "githubApi" in node["credentials"]


def test_the_board_config_names_the_repo_and_the_label():
    assert BOARD_CFG["label"] == "post"
    assert BOARD_CFG["owner"] and BOARD_CFG["repo"]
    assert BOARD_CFG["state"] == "open"
    # The article is read in a text column, so its default pair is the wide frame. The 4:5
    # pair is the LinkedIn feed's, and a row imported with it published a phone poster.
    assert BOARD_CFG["defaults"]["asset_types"] == "image_wide,svg_wide"


@pytest.mark.skipif(shutil.which("node") is None, reason=NODE_REQUIRED)
def test_the_board_config_falls_back_to_the_wide_pair():
    # parse_board_config defaults every key, so a dataset that omits asset_types must still
    # yield a frame the article lane can publish.
    out = _items(_run(_js(BOARD, "parse_board_config"), {
        "download_board_config": [{"output": "{}"}],
        "download_curator_config": [{"output": "{}"}],
    }))[0]
    assert out["asset_types"] == "image_wide,svg_wide"


def test_an_imported_row_is_the_issues_own_data_with_the_lane_defaults():
    cfg = {
        "categories": "OSS", "asset_types": "image_wide,svg_wide", "max_words": 1200, "priority": "MEDIUM",
        "audience": "LOW", "run_at": "2026-10-18T10:00:00.000Z",
    }
    issues = [{
        "number": 80, "title": "Post about how to use sympozium", "body": "Explain it",
        "html_url": "https://github.com/datahub-local/datahub-local/issues/80",
    }]
    rows = _items(_run(_js(BOARD, "build_intake_rows"), {
        "parse_board_config": [cfg], "list_board_issues": issues, "read_article_queue": [],
    }))
    assert len(rows) == 1
    row = rows[0]
    assert row["ENTRY_ID"] == "gh-80"
    assert row["TOPIC"] == "Post about how to use sympozium"
    assert row["DESCRIPTION"] == "Explain it"
    assert row["LINK"] == "https://github.com/datahub-local/datahub-local/issues/80"
    assert row["ORIGIN"] == "BOARD"
    assert row["STATUS"] == "QUEUE"
    assert row["UPDATE_DATE"] == cfg["run_at"]
    assert row["CATEGORIES"] == "OSS"
    assert row["ASSET_TYPES"] == "image_wide,svg_wide"
    assert row["MAX_WORDS"] == 1200
    assert row["PRIORITY"] == "MEDIUM"
    assert row["AUDIENCE"] == "LOW"
    assert row["NEW_COUNT"] == 1
    # A category the blog does not know would be refused by the article lane before it
    # drafts, so the default has to be one of the taxonomy.
    assert BOARD_CFG["defaults"]["categories"] in BLOG_CATEGORIES
    # The audience default is a reader level; the article lane refuses anything else, naming it.
    assert BOARD_CFG["defaults"]["audience"] == "NONE"


def test_an_issue_already_in_the_queue_is_not_imported_again():
    cfg = {"categories": "General", "asset_types": "image,svg", "max_words": 1200, "priority": "MEDIUM",
           "run_at": "2026-10-18T10:00:00.000Z"}
    queue = [{"ENTRY_ID": "gh-80", "LINK": "https://github.com/datahub-local/datahub-local/issues/80"}]
    issues = [
        {"number": 80, "title": "old", "html_url": "https://github.com/datahub-local/datahub-local/issues/80"},
        {"number": 91, "title": "new", "html_url": "https://github.com/datahub-local/datahub-local/issues/91"},
    ]
    rows = _items(_run(_js(BOARD, "build_intake_rows"), {
        "parse_board_config": [cfg], "list_board_issues": issues, "read_article_queue": queue,
    }))
    assert [r["ENTRY_ID"] for r in rows] == ["gh-91"]


def test_a_pull_request_is_not_an_article_idea():
    cfg = {"categories": "General", "asset_types": "image,svg", "max_words": 1200, "priority": "MEDIUM",
           "run_at": "2026-10-18T10:00:00.000Z"}
    issues = [
        {"number": 5, "title": "a PR", "pull_request": {"url": "x"}},
        {"number": 6, "title": "an idea"},
    ]
    rows = _items(_run(_js(BOARD, "build_intake_rows"), {
        "parse_board_config": [cfg], "list_board_issues": issues, "read_article_queue": [],
    }))
    assert [r["ENTRY_ID"] for r in rows] == ["gh-6"]


def test_nothing_new_still_lets_the_ceiling_run():
    cfg = {"categories": "General", "asset_types": "image,svg", "max_words": 1200, "priority": "MEDIUM",
           "run_at": "2026-10-18T10:00:00.000Z"}
    rows = _items(_run(_js(BOARD, "build_intake_rows"), {
        "parse_board_config": [cfg], "list_board_issues": [], "read_article_queue": [],
    }))
    assert len(rows) == 1 and rows[0]["NEW_COUNT"] == 0


def test_the_queue_empty_still_lets_the_ceiling_run():
    # read_article_queue carries alwaysOutputData; without it the chain would stop at an
    # empty queue and the ceiling would never run on a first or quiet day.
    for copy in ("nodes", "activeVersion.nodes"):
        node = _node(BOARD, "read_article_queue", copy)
        assert node["alwaysOutputData"] is True
        # A Sheets read past 4.1 runs once per input item, and this one's input is one item
        # per issue: without executeOnce the whole queue came back once per open issue
        # (measured 2026-10-19, execution 14349: 792 items for 198 rows).
        assert node["executeOnce"] is True
        # The append must keep every row: it consumes the item stream, it does not read
        # the sheet through $('node').all().
        assert not _node(BOARD, "append_article_queue", copy).get("executeOnce")


def test_the_appended_row_reaches_article_queue():
    for copy in ("nodes", "activeVersion.nodes"):
        node = _node(BOARD, "append_article_queue", copy)
        assert node["parameters"]["operation"] == "append"
        assert node["parameters"]["sheetName"]["value"] == "article_queue"
        mapped = node["parameters"]["columns"]["value"]
        for column in ("ENTRY_ID", "TOPIC", "DESCRIPTION", "LINK", "CATEGORIES", "ASSET_TYPES",
                       "MAX_WORDS", "PRIORITY", "AUDIENCE", "ORIGIN", "STATUS", "UPDATE_DATE"):
            assert column in mapped, column
    # The Content-Board-Curator lesson: defineBelow without a schema entry is not written at all.
    for copy in ("nodes", "activeVersion.nodes"):
        columns = _node(BOARD, "append_article_queue", copy)["parameters"]["columns"]
        entry = next(s for s in columns["schema"] if s["id"] == "AUDIENCE")
        assert entry["removed"] is False, f"{copy}: the Sheets node would silently not write AUDIENCE"


ARTICLE_QUEUE_COLUMNS = (
    "ENTRY_ID", "TOPIC", "DESCRIPTION", "STATUS", "PRIORITY", "ORIGIN", "LINK",
    "CATEGORIES", "ASSET_TYPES", "MAX_WORDS", "AUDIENCE", "EXTRA_PROMPT", "ARTICLE_STATUS",
    "ARTICLE_ROUND", "ARTICLE_FEEDBACK", "ARTICLE_TITLE", "ARTICLE_REF",
    "PUBLISHED_URL", "COMMIT_REF", "PUBLISHED_AT", "EXECUTION_ID", "ERROR",
    "UPDATE_DATE",
)


def test_both_queue_writes_describe_the_whole_sheet():
    # `defineBelow` without `columns.schema` is a runtime error on append (hit live
    # 2026-10-19, execution 14322), not a UI-only nicety: n8n validates the schema
    # against the live header before it writes.
    for copy in ("nodes", "activeVersion.nodes"):
        for name in ("append_article_queue", "cancel_stale_articles"):
            schema = _node(BOARD, name, copy)["parameters"]["columns"].get("schema") or []
            ids = [s["id"] for s in schema]
            assert ids, f"{copy} {name} has no columns.schema"
            missing = [c for c in ARTICLE_QUEUE_COLUMNS if c not in ids]
            assert not missing, f"{copy} {name} schema is missing {missing}"
            assert "row_number" in ids


# --------------------------------------------------------------------------- ceiling

def _ceiling(days=7, run_at="2026-10-18T10:00:00.000Z"):
    cfg = {"cancel_after_days": days, "run_at": run_at}
    rows = [
        {"row_number": 2, "TOPIC": "stuck run", "STATUS": "IN_PROGRESS", "UPDATE_DATE": "2026-10-08T10:00:00.000Z"},
        {"row_number": 3, "TOPIC": "fresh approval", "STATUS": "WAITING_APPROVAL", "UPDATE_DATE": "2026-10-16T10:00:00.000Z"},
        {"row_number": 4, "TOPIC": "queued long", "STATUS": "QUEUE", "UPDATE_DATE": "2026-10-09T10:00:00.000Z"},
        {"row_number": 5, "TOPIC": "published", "STATUS": "PUBLISHED", "UPDATE_DATE": "2026-09-01T10:00:00.000Z"},
        {"row_number": 6, "TOPIC": "already cancelled", "STATUS": "CANCELLED", "UPDATE_DATE": "2026-09-01T10:00:00.000Z"},
    ]
    return _items(_run(_js(BOARD, "build_cancel_rows"), {
        "parse_board_config": [cfg], "read_article_queue": rows,
    }))


def test_an_article_row_still_in_play_past_the_ceiling_is_cancelled():
    rows = _ceiling()
    assert sorted(r["row_number"] for r in rows) == [2, 4]
    assert rows[0]["CANCELLED_COUNT"] == 2


def test_a_terminal_or_recent_row_is_never_cancelled():
    numbers = {r["row_number"] for r in _ceiling()}
    assert 3 not in numbers  # recent approval
    assert 5 not in numbers  # published is terminal
    assert 6 not in numbers  # already cancelled


def test_the_ceiling_measures_from_the_rows_own_clock():
    # The same row, 9 days after its last update, qualifies; shifted to 3 days it does not,
    # which is what keeps a live run (whose every phase rewrites UPDATE_DATE) safe.
    old = _ceiling(run_at="2026-10-18T10:00:00.000Z")
    young = _ceiling(run_at="2026-10-12T10:00:00.000Z")
    assert 2 in {r.get("row_number") for r in old}
    assert 2 not in {r.get("row_number") for r in young}


def test_the_cancel_update_clears_both_status_fields():
    node = _node(BOARD, "cancel_stale_articles")
    mapped = node["parameters"]["columns"]["value"]
    assert node["parameters"]["operation"] == "update"
    assert node["parameters"]["sheetName"]["value"] == "article_queue"
    # ARTICLE_STATUS is what stops the article lane resuming a claimed row it never finished.
    assert mapped["STATUS"] == "CANCELLED"
    assert mapped["ARTICLE_STATUS"] == "CANCELLED"
    assert node["parameters"]["columns"]["matchingColumns"] == ["row_number"]


def test_nothing_to_cancel_is_a_normal_day():
    cfg = {"cancel_after_days": 7, "run_at": "2026-10-18T10:00:00.000Z"}
    rows = _items(_run(_js(BOARD, "build_cancel_rows"), {
        "parse_board_config": [cfg], "read_article_queue": [],
    }))
    assert len(rows) == 1 and rows[0]["CANCELLED_COUNT"] == 0


# ------------------------------------------------------- the curator's own ceiling

def test_the_post_queue_ceiling_is_wired_into_the_curator():
    for copy in ("nodes", "activeVersion.nodes"):
        node = _node(CURATOR, "build_cancel_rows", copy)
        assert node["type"] == "n8n-nodes-base.code"
        assert _node(CURATOR, "cancel_stale_queue", copy)["parameters"]["sheetName"]["value"] == "content_queue"


def test_the_post_queue_cancels_with_this_lanes_spelling():
    for copy in ("nodes", "activeVersion.nodes"):
        mapped = _node(CURATOR, "cancel_stale_queue", copy)["parameters"]["columns"]["value"]
        # Content Feed Curator's lane writes CANCELED (one L); article_queue writes CANCELLED.
        assert mapped["STATUS"] == "CANCELED"


def test_the_curator_cancels_in_play_rows_past_the_ceiling():
    cfg = {"cancel_after_days": 7, "run_at": "2026-10-18T10:00:00.000Z"}
    rows = [
        {"row_number": 1, "TITLE": "queued", "STATUS": "QUEUE", "UPDATE_DATE": "2026-10-01T00:00:00Z"},
        {"row_number": 2, "TITLE": "running", "STATUS": "IN_PROGRESS", "UPDATE_DATE": "2026-10-02T00:00:00Z"},
        {"row_number": 3, "TITLE": "waiting", "STATUS": "WAITING_APPROVAL", "UPDATE_DATE": "2026-10-17T00:00:00Z"},
        {"row_number": 4, "TITLE": "done", "STATUS": "PUBLISHED", "UPDATE_DATE": "2026-01-01T00:00:00Z"},
    ]
    result = _items(_run(_js(CURATOR, "build_cancel_rows"), {
        "parse_curator_config": [cfg], "read_articles_sheet": rows,
    }))
    assert sorted(r["row_number"] for r in result) == [1, 2]


def test_the_ceiling_is_the_expire_pass_s_exclusion():
    # build_expire_rows owns the hook TTL and the caps; a row past the ceiling is the cancel
    # pass's, so this node skips it and the two never write the same row.
    for copy in ("nodes", "activeVersion.nodes"):
        js = _js(CURATOR, "build_expire_rows", copy)
        assert "const cancelDays = num(cfg.cancel_after_days, 7);" in js
        assert "const sinceUpdate = isFinite(updatedAt) ? (nowMs - updatedAt) / 86400000 : 0;" in js
        assert "if (sinceUpdate > cancelDays) continue;" in js


def test_the_expire_pass_skips_on_the_ceilings_own_clock():
    # The skip and the ceiling must share one clock (the row's UPDATE_DATE). Measured from
    # PUBLISHED_AT, an old article rewritten recently is neither past the ceiling nor - having
    # been skipped - ever past its hook TTL, so it would escape both passes.
    cfg = {
        "cancel_after_days": 7,
        "run_at": "2026-10-18T00:00:00.000Z",
        "backlog": {"max_per_category": 6, "max_total": 60,
                    "ttl_days": {"NEWS_REACTION": 10, "default": 60}},
    }
    rows = [
        # old article, written yesterday: not the ceiling's, and past its own TTL -> expire
        {"row_number": 1, "TITLE": "old article, fresh row", "HOOK": "NEWS_REACTION", "ORIGIN": "AUTO",
         "STATUS": "QUEUE", "PUBLISHED_AT": "2026-09-18T00:00:00.000Z", "UPDATE_DATE": "2026-10-17T00:00:00.000Z"},
        # fresh article, untouched for a month: the ceiling's job, so skipped here
        {"row_number": 2, "TITLE": "stuck row", "HOOK": "NEWS_REACTION", "ORIGIN": "AUTO",
         "STATUS": "QUEUE", "PUBLISHED_AT": "2026-10-17T00:00:00.000Z", "UPDATE_DATE": "2026-09-18T00:00:00.000Z"},
    ]
    result = _items(_run(_js(CURATOR, "build_expire_rows"), {
        "parse_curator_config": [cfg], "read_articles_sheet": rows, "admit_to_backlog": [],
    }))
    emitted = {r["row_number"] for r in result}
    assert 1 in emitted  # expired on its hook TTL
    assert 2 not in emitted  # left to the ceiling pass


def test_the_ceiling_is_one_value_for_both_queues():
    assert isinstance(CURATOR_CFG.get("cancel_after_days"), int)
    # The board curator reads the same file rather than keeping a second ceiling.
    assert _node(BOARD, "download_curator_config")["parameters"]["workflowInputs"]["value"]["template_name"] == "datasets/curator_config.json"
    for copy in ("nodes", "activeVersion.nodes"):
        assert "cancel_after_days: Math.max(1, num(cfg.cancel_after_days, 7))," in _js(CURATOR, "parse_curator_config", copy)
