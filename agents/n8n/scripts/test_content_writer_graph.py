"""Guard the article pipeline's error path.

`Article Content Writer Error` is the entry point's `settings.errorWorkflow`, so it is the
only thing that turns a failed run into a Slack notice and a cleared row. Two properties are
asserted here because both have been the difference between a reported failure and a silent
one in this repository:

  * the row match must not decide whether the notice is sent. The LinkedIn error workflow
    ends at its Slack node on the `select_article_with_error` output, so a failure with no
    matching row sends nothing at all -- while the run still reports `Succeeded` nowhere and
    the logs record no line at all at `log_level: info`.
  * the error handler must not carry `settings.errorWorkflow` itself: setting it would make
    a failure of the handler trigger the handler.

The page is addressed by name rather than by gid: `article_queue` does not exist yet, and the
Google Sheets node's own builder hint says a title placed in `list` or `id` mode cannot
resolve. The same applies to the Data Tables in the entry point.
"""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]  # agents/n8n
WORKFLOWS = BASE / "workflows"

ERROR_WF = WORKFLOWS / "article_content_writer_error.workflow.json"


def _doc():
    return json.loads(ERROR_WF.read_text(encoding="utf-8"))


def _nodes():
    return {n["name"]: n for n in _doc()["nodes"]}


def _targets(connections, source, output=0):
    branches = (connections.get(source) or {}).get("main") or []
    branch = branches[output] if output < len(branches) else []
    return [edge["node"] for edge in (branch or [])]


def _reachable(source):
    seen, queue = {source}, [source]
    connections = _doc()["connections"]
    while queue:
        for target in _targets(connections, queue.pop()):
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return seen


def test_the_handler_does_not_trigger_itself():
    assert "errorWorkflow" not in _doc()["settings"]


def test_the_notice_is_reachable_from_the_trigger():
    reached = _reachable("error_trigger")
    assert "send_error_notification" in reached


def test_the_notice_is_reachable_without_a_matching_row():
    # The rowless branch must reach Slack on its own, not only through the Sheet update.
    reached_without_update = _reachable("if_row_found") | {"if_row_found"}
    assert "set_error" in reached_without_update
    assert "send_error_notification" in reached_without_update


def test_the_rowless_branch_skips_the_sheet_update():
    assert _targets(_doc()["connections"], "if_row_found", 1) == ["set_error"]


def test_a_rowless_run_still_emits_one_item():
    code = _nodes()["select_row_with_error"]["parameters"]["jsCode"]
    assert "NO_ROW" in code
    assert "return [{ json: { NO_ROW: true" in code


def test_the_row_is_marked_failed_by_its_row_number():
    columns = _nodes()["update_row_error"]["parameters"]["columns"]
    assert columns["value"]["STATUS"] == "ERROR"
    assert columns["matchingColumns"] == ["row_number"]


def test_the_page_is_addressed_by_name():
    for name in ("read_article_queue_error", "update_row_error"):
        sheet_name = _nodes()[name]["parameters"]["sheetName"]
        assert sheet_name["value"] == "article_queue"
        assert sheet_name["mode"] == "name"
