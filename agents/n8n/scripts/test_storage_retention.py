"""Guard the n8n storage bounds.

A rendered artifact must not reach an execution payload or n8n's binary store, because
n8n persists binaries as well as JSON: measured on 2026-10-14, ``binary_data`` held
249 MB across 903 rows and ``execution_data`` 1060 MB across 1405 rows in a 1335 MB
database. Two mechanisms keep that true, and both are asserted here offline against the
committed exports:

  * the studio no longer carries the render at all - the temp-bucket MCP server fetches
    it from the session and stores it, so the studio records its runs and the asset
    reaches object storage exactly once,
  * every workflow whose payload *is* still the bytes - or a row carrying them - keeps
    ``saveDataSuccessExecution: none``,

and around those:

  * the rendered asset is pruned on a short window and ``TemporalFiles`` with it,
  * nothing writes a run row any more,
  * the dead workflows stay deleted.

Both copies of each export are checked -- the exports carry their nodes twice, at the
top level and inside ``activeVersion``, and a fix applied to one copy is a live bug.
"""

import json
import re
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"
PRUNE = WORKFLOWS / "visual_studio_prune.workflow.json"
STUDIO = WORKFLOWS / "visual_studio.workflow.json"
ERROR_WF = WORKFLOWS / "visual_studio_error.workflow.json"

# The workflows whose node output still carries a rendered artifact, or a row holding
# one, so their successful executions are the ones that filled execution_data: measured
# 511 MB for Visual Studio Test, 96 MB for LinkedIn Post Sharing, 44 MB for the Prune
# (deleteRows returns the rows it deleted). Visual Studio is deliberately absent - it
# holds an object key now, which is what lets it record - and the still-image path keeps
# its own small data URL, so a still run does cost its asset's bytes here.
ARTIFACT_WORKFLOWS = [
    "visual_studio_test",
    "linked_in_post_sharing",
    "visual_studio_prune",
]

# The workflows that may record a successful run. Recording is safe only while the graph
# carries no bytes, which the test below this one holds.
RECORDING_WORKFLOWS = ["visual_studio"]

# Inactive and referenced by nothing, checked across every export's executeWorkflow
# workflowId and settings.errorWorkflow.
DEAD_WORKFLOWS = [
    "my_workflow_668",
    "test_form",
    "zz_daily_check_probe_temp",
    "zz_probe_assets_dbg",
]

WINDOW_RE = re.compile(r"new Date\(Date\.now\(\) - (\d+) \* 24 \* 60 \* 60 \* 1000\)")


def _copies(path):
    doc = json.loads(path.read_text())
    yield "top level", doc
    yield "activeVersion", doc.get("activeVersion") or {"nodes": [], "connections": {}}


def _nodes(document):
    return {node["name"]: node for node in document["nodes"]}


def _targets(document, source, output=0):
    return [edge["node"] for edge in document["connections"][source]["main"][output]]


@pytest.mark.parametrize("label,document", list(_copies(PRUNE)))
def test_temporal_files_are_pruned_with_the_webhooks_own_rule(label, document):
    # File Webhook's own cleanup only runs when the webhook is called, so a quiet week
    # leaves its rows behind; the daily prune applies the same one-hour rule.
    node = _nodes(document)["delete_expired_files"]
    params = node["parameters"]
    assert params["operation"] == "deleteRows"
    assert params["dataTableId"]["value"] == "TemporalFiles"
    condition = params["filters"]["conditions"][0]
    assert condition["keyName"] == "updatedAt"
    assert "hours: 1" in condition["keyValue"], condition["keyValue"]


@pytest.mark.parametrize("label,document", list(_copies(PRUNE)))
def test_the_prune_cleans_files_then_the_bucket(label, document):
    assert _targets(document, "schedule_trigger", 0) == ["delete_expired_files"]
    assert _targets(document, "delete_expired_files", 0) == ["list_assets"]


@pytest.mark.parametrize("name", ARTIFACT_WORKFLOWS)
def test_artifact_workflows_do_not_persist_successful_payloads(name):
    settings = json.loads((WORKFLOWS / f"{name}.workflow.json").read_text())["settings"]
    assert settings.get("saveDataSuccessExecution") == "none", (
        f"{name}: a successful execution would persist a multi-megabyte artifact payload"
    )
    # The failure path is the one that needs the payload.
    assert settings.get("saveDataErrorExecution", "all") != "none", f"{name}: errors must still be recorded"


@pytest.mark.parametrize("name", RECORDING_WORKFLOWS)
def test_the_studio_records_its_runs_because_it_carries_no_bytes(name):
    settings = json.loads((WORKFLOWS / f"{name}.workflow.json").read_text())["settings"]
    assert settings.get("saveDataSuccessExecution") == "all", (
        f"{name}: the point of moving the bytes out was to be able to record a run"
    )
    assert settings.get("saveDataErrorExecution", "all") != "none", f"{name}: errors must still be recorded"


@pytest.mark.parametrize("label,document", list(_copies(STUDIO)))
def test_the_studio_carries_no_artifact_bytes(label, document):
    """What makes recording safe: nothing on this graph holds the render.

    Every path that once did is gone - the fetch that pulled the file into the
    execution, the base64 data URL in the asset, the upload that read it back. If any
    returns, ``saveDataSuccessExecution: all`` above turns a 60 MB asset into 60 MB of
    execution_data per run, which is the failure this whole change exists to remove.
    """
    nodes = _nodes(document)
    for gone in ("fetch_artifact", "fetch_paired_artifact"):
        assert gone not in nodes, f"{label}: {gone} is back, and it carries the bytes"
    code = nodes["agent_result"]["parameters"]["jsCode"]
    assert "S3_KEY" in code and "S3_BYTES" in code
    assert "getBinaryDataBuffer" not in code and "data:'" not in code
    for name in ("store_artifact", "store_paired_artifact"):
        params = nodes[name]["parameters"]
        assert nodes[name]["type"] == "n8n-nodes-base.httpRequest", f"{label}: {name} is not the store call"
        assert "temp_store" in params["jsonBody"], f"{label}: {name} does not call temp_store"
        assert params["options"]["timeout"] > 0, f"{label}: {name} has no timeout for a 60 MB transfer"


@pytest.mark.parametrize("name", DEAD_WORKFLOWS)
def test_the_dead_workflows_stay_deleted(name):
    assert not (WORKFLOWS / f"{name}.workflow.json").exists(), (
        f"{name} was inactive and referenced by nothing; re-adding it re-adds a live workflow"
    )


# --- the asset lives in Garage, and nothing writes a run row -------------------------
#
# visual_studio_table hit its 200 MB cap on 2026-10-13 with only 12 rows, four of them
# 32-34 MB, because RESULT carried each asset as a base64 data URL. Run 13256 authored,
# rendered and fetched its asset and then failed at record_run. The bytes now go to the
# bucket, the key travels in the response, and the table is gone: nothing ever read a
# row, so the three nodes that wrote one were the whole of its use.


@pytest.mark.parametrize("label,document", list(_copies(STUDIO)))
def test_the_studio_writes_no_run_row(label, document):
    tables = [n["name"] for n in document["nodes"] if n["type"] == "n8n-nodes-base.dataTable"]
    assert tables == [], f"{label}: the studio writes a DataTable again: {tables}"
    for gone in ("run_record", "record_run"):
        assert gone not in _nodes(document), f"{label}: {gone} is back"

    upload = _nodes(document)["upload_assets"]
    assert upload["type"] == "n8n-nodes-base.s3"
    assert upload["parameters"]["operation"] == "upload"
    assert upload["parameters"]["bucketName"] == "datahub-local-temp"
    assert upload["parameters"]["binaryData"] is True
    # continueRegularOutput forwards the input unchanged, so a failed upload would still
    # hand the response a key for an object that was never written. Let it fail the run.
    assert "onError" not in upload, "a failed upload would be reported as a stored object"

    assert _targets(document, "merge_branches", 0) == ["prepare_uploads"]
    assert _targets(document, "prepare_uploads", 0) == ["upload_assets"]
    assert _targets(document, "upload_assets", 0) == ["set_result"]


@pytest.mark.parametrize("label,document", list(_copies(STUDIO)))
def test_the_response_carries_the_asset_and_its_key(label, document):
    # LinkedIn Post Sharing reads ASSETS[].IMAGE and throws without a data URL; the row
    # that used to name the object is gone, so the key travels in the response too.
    code = _nodes(document)["set_result"]["parameters"]["jsCode"]
    assert "const items = $('merge_branches').all()" in code
    assert "ASSETS: assets" in code
    assert "S3_KEY" in code and "S3_BYTES" in code
    assert "SESSION_ID: sessionId" in code, "a caller cannot learn the resolved session"


@pytest.mark.parametrize("label,document", list(_copies(PRUNE)))
def test_the_bucket_is_pruned_on_the_run_row_window(label, document):
    nodes = _nodes(document)
    listing = nodes["list_assets"]["parameters"]
    assert nodes["list_assets"]["type"] == "n8n-nodes-base.s3"
    assert listing["operation"] == "getAll"
    assert listing["bucketName"] == "datahub-local-temp"
    # file:getAll sets a '/' delimiter, so the prefix must itself end in one: with
    # 'visual-studio' the key's own slash makes it a CommonPrefix and the object is
    # never listed. Measured against the live node: folderKey 'visual-studio' returned
    # 0 items where 'visual-studio/' returned the 2 objects.
    assert listing["options"]["folderKey"] == "visual-studio/"

    delete = nodes["delete_assets"]["parameters"]
    assert nodes["delete_assets"]["type"] == "n8n-nodes-base.s3"
    assert delete["operation"] == "delete"
    assert delete["bucketName"] == "datahub-local-temp"
    assert "Key" in delete["fileKey"], delete["fileKey"]

    match = WINDOW_RE.search(nodes["filter_old_assets"]["parameters"]["jsCode"])
    assert match, "the object window is not a day count"
    assert int(match.group(1)) <= 2, "the bucket must not grow without limit"

    assert _targets(document, "delete_expired_files", 0) == ["list_assets"]
    assert _targets(document, "list_assets", 0) == ["filter_old_assets"]
    assert _targets(document, "filter_old_assets", 0) == ["delete_assets"]


def test_the_error_workflow_writes_no_row_and_still_notifies():
    # record_failed carried onError: continueRegularOutput, which hid its own failure on
    # 2026-10-13: the write hit the table's size limit, the error workflow reported
    # success, and no FAILED row existed for the run. The write is gone, and the failure
    # is still reported by the Slack notification, which must not sit behind a node that
    # can swallow its own error.
    for label, document in _copies(ERROR_WF):
        nodes = _nodes(document)
        assert "record_failed" not in nodes, f"{label}: the row write is back"
        assert [n for n in document["nodes"] if n["type"] == "n8n-nodes-base.dataTable"] == []
        assert _targets(document, "error_trigger", 0) == ["cleanup_run"]
        assert _targets(document, "cleanup_run", 0) == ["notify_failed"]
