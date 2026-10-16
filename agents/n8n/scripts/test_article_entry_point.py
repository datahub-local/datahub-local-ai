"""Guard the Article Content Writer entry point's graph.

The entry point is authored as a create body, so nothing about it is live yet and its
behaviour cannot be exercised here. What can be asserted offline is the set of decisions the
graph has to get right for the live run in 6.2 to mean anything -- each of these has a failure
mode that is silent at run time, which is why they are pinned rather than reviewed once:

  * the references the run needs that do not exist yet (the sheet page, the two Data Tables)
    are addressed **by name**, so the export is complete before the human creates them;
  * the claim is written before the first model call, and every sheet write is keyed on
    `row_number`, because an update that matches nothing is a silent no-op;
  * the publish path never borrows a node from the asset path: a resumed publish run has not
    executed `if_all_assets_approved`, and `$('that node').first()` would throw;
  * a raster asset's bytes have no durable handle, so they are stored on the asset row, while
    an agent asset is re-fetched from its object key;
  * the studio is asked for the pending types on a resume, so an approved asset is never
    re-authored.
"""

import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]  # agents/n8n
WORKFLOWS = BASE / "workflows"

ENTRY = WORKFLOWS / "article_content_writer.workflow.json"
REF_RE = re.compile(r"\$\(\s*['\"]([^'\"]+)['\"]\s*\)")


def _doc():
    return json.loads(ENTRY.read_text(encoding="utf-8"))


def _nodes():
    return {n["name"]: n for n in _doc()["nodes"]}


def _connections():
    return _doc()["connections"]


def _targets(source, output=0):
    branches = (_connections().get(source) or {}).get("main") or []
    branch = branches[output] if output < len(branches) else []
    return [edge["node"] for edge in (branch or [])]


def _reachable(*sources):
    seen, queue = set(sources), list(sources)
    while queue:
        for target in _targets(queue.pop()):
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return seen


def _js(name):
    return _nodes()[name]["parameters"]["jsCode"]


def test_the_new_references_are_addressed_by_name():
    nodes = _nodes()
    sheet_refs = [
        n["parameters"]["sheetName"]
        for n in _doc()["nodes"]
        if n["type"] == "n8n-nodes-base.googleSheets"
    ]
    assert sheet_refs, "no sheet node at all"
    for ref in sheet_refs:
        assert ref["value"] == "article_queue"
        assert ref["mode"] == "name"
    tables = {
        n["parameters"]["dataTableId"]["value"]
        for n in _doc()["nodes"]
        if n["type"] == "n8n-nodes-base.dataTable"
    }
    assert tables == {"article_drafts", "article_assets"}
    for node in nodes.values():
        ref = (node.get("parameters") or {}).get("dataTableId")
        if ref:
            assert ref["mode"] == "name"


def test_every_sheet_write_is_keyed_on_the_row_number():
    updates = [
        n
        for n in _doc()["nodes"]
        if n["type"] == "n8n-nodes-base.googleSheets" and n["parameters"].get("operation") == "update"
    ]
    assert updates
    for node in updates:
        assert node["parameters"]["columns"]["matchingColumns"] == ["row_number"], node["name"]


def test_the_claim_is_written_before_the_first_model_call():
    assert _targets("select_article_to_queue") == ["update_status_in_progress"]
    claim = _nodes()["update_status_in_progress"]["parameters"]["columns"]["value"]
    assert claim["STATUS"] == "IN_PROGRESS"
    assert claim["EXECUTION_ID"] == "={{ $execution.id }}"
    # The creator is downstream of the claim, not the other way round.
    assert "execute_article_creator" in _reachable("update_status_in_progress")


def test_the_draft_is_gated_before_anything_is_reviewed():
    # A failed draft must reach stopAndError and no Slack message at all.
    assert _targets("check_draft_error", 1) == ["fail_draft"]
    assert not [t for t in _reachable("fail_draft") if t.startswith(("notify_", "upload_"))]
    assert _targets("check_draft_error", 0) == ["derive_slug"]


def test_the_rendered_asset_is_the_only_thing_that_gets_reviewed():
    # An asset the studio could not render keeps its reason and takes no review.
    assert _targets("if_asset_rendered") == ["if_asset_has_bytes"]


def test_a_resumed_asset_phase_asks_only_for_the_pending_types():
    studio = _nodes()["execute_visual_studio"]["parameters"]["workflowInputs"]["value"]
    assert "PENDING_ASSETS" in studio["ASSET_TYPES"]
    # The draft comes from the Data Table, not from a node that did not run in this execution.
    assert studio["CONTENT"] == "={{ $('read_draft_for_assets').first().json.ARTICLE_TEXT }}"
    assert studio["SESSION_ID"] == "={{ 'blog-' + $('select_article_to_queue').item.json.ENTRY_ID }}"


def test_the_publish_path_owns_its_own_reads():
    # A resumed publish run has not executed the asset-review nodes, so anything it borrows
    # from them throws at run time.
    publish = _reachable("read_asset_rows_for_publish")
    for node in (
        "plan_asset_uploads",
        "build_commit_files",
        "collect_tree_entries",
        "record_published",
        "send_published_notification",
    ):
        assert node in publish, node
        references = set(REF_RE.findall(json.dumps(_nodes()[node]["parameters"])))
        assert "if_all_assets_approved" not in references, node
    assert _targets("switch_phase", 2) == ["read_asset_rows_for_publish"]
    assert _targets("if_all_assets_approved") == ["read_asset_rows_for_publish"]


def test_a_raster_is_stored_and_an_agent_asset_is_refetched():
    store = _nodes()["store_assets"]["parameters"]["columns"]["value"]
    assert "DATA_BASE64" in store
    assert "IMAGE" in store["DATA_BASE64"]
    plan = _js("plan_asset_uploads")
    assert "DATA_BASE64" in plan
    assert "S3_KEY" in plan
    assert "NEEDS_FETCH" in plan
    # The fetch branch exists and converges back on the blob call.
    assert _targets("if_asset_needs_fetch", 0) == ["create_blobs"]
    assert _targets("if_asset_needs_fetch", 1) == ["presign_asset_publish"]
    assert "create_blobs" in _reachable("asset_bytes_from_download")


def test_the_draft_row_is_upserted_so_a_round_does_not_accumulate_rows():
    draft = _nodes()["store_draft"]["parameters"]
    assert draft["operation"] == "upsert"
    assert draft["filters"]["conditions"][0]["keyName"] == "ENTRY_ID"
    # The slug is frozen at the draft, which is what a retry reuses (D11).
    assert "SLUG" in draft["columns"]["value"]


def test_the_article_text_is_committed_inline_and_assets_as_blobs():
    body = _js("build_commit_files")
    assert "FILE_IS_BINARY" in body
    assert "categories: [" in body
    assert "authors: [alvsanand]" in body
    # A marker the draft omitted is placed rather than dropped.
    assert "placed without a marker" in body
    entries = _js("collect_tree_entries")
    assert "content = f.FILE_TEXT" in entries
    assert "expected[i]" in entries  # a mis-paired sha fails instead of committing the wrong file


def test_one_commit_sequence_with_a_guarded_fast_forward_retry():
    names = set(_nodes())
    assert {"create_tree", "create_commit", "patch_ref"} <= names
    assert _nodes()["patch_ref"].get("onError") == "continueErrorOutput"
    # The retry re-reads the branch and rebuilds on its new head rather than force-pushing.
    assert _targets("patch_ref", 1) == ["get_base_ref_again"]
    assert "force: false" in _nodes()["patch_ref"]["parameters"]["jsonBody"]
    assert "force: false" in _nodes()["patch_ref_again"]["parameters"]["jsonBody"]
    assert _targets("patch_ref_again") == ["check_ref_retry"]
    assert _targets("check_ref_retry") == ["record_published"]


def test_the_row_categories_are_checked_before_anything_is_drafted():    # The one taxonomy copy is fetched, not restated in the node, and an unreadable file fails
    # the run rather than skipping the check.
    download = _nodes()["download_blog_categories"]["parameters"]["workflowInputs"]["value"]
    assert download["template_name"] == "datasets/blog_categories.json"
    assert download["template_vars"] == "={{ {} }}"
    code = _js("validate_categories")
    assert "known.categories" in code
    assert "throw new Error" in code
    assert _targets("pick_candidate") == ["download_blog_categories"]
    assert _targets("validate_categories") == ["read_asset_rows_for_entry"]


def test_the_only_continue_regular_output_is_normalised_downstream():
    # A non-AI node forwards its input unchanged on failure, so the flag has to be set by a
    # following node rather than read off the failed one.
    lenient = [n["name"] for n in _doc()["nodes"] if n.get("onError") == "continueRegularOutput"]
    assert lenient == ["download_content"]
    assert _targets("download_content") == ["set_link_flags"]
    assert "LINK_USED" in _js("set_link_flags")


def test_the_schedule_is_declared_and_the_handler_is_this_repositorys():
    # 6.6 keeps the schedule inactive until every path has been exercised; the workflow is
    # created inactive, so that is a live state, not a field in this body.
    assert any(n["type"] == "n8n-nodes-base.scheduleTrigger" for n in _doc()["nodes"])
    handler = json.loads((WORKFLOWS / "article_content_writer_error.workflow.json").read_text(encoding="utf-8"))
    assert _doc()["settings"]["errorWorkflow"] == handler["id"], (
        "the entry point's handler must be the workflow this repository carries"
    )
    # The handler does not report to itself.
    assert "errorWorkflow" not in handler["settings"]

def test_the_link_outcome_is_recorded_and_not_only_carried():
    # The spec asks the run to record that the link content was not used, so the flag lands on
    # the draft row rather than living only in this execution.
    draft = _nodes()["store_draft"]["parameters"]["columns"]["value"]
    assert draft["LINK_USED"] == "={{ $('set_link_flags').item.json.LINK_USED }}"


def test_an_overlapping_trigger_skips_a_fresh_claim_and_recovers_a_stale_one():
    # Two runs must not work the same entry. Nothing can ask n8n whether an execution is alive,
    # so the claim's own UPDATE_DATE is the observable: fresh means someone is on it, stale
    # means the run died and the entry becomes actionable again.
    code = _js("pick_candidate")
    assert "STALE_CLAIM_HOURS" in code
    assert "Date.now() - claimedAt" in code
    assert "return false" in code
