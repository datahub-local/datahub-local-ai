"""Guard the n8n storage bounds.

The studio's rendered artifact travels as a base64 data URL, so the same bytes are
persisted in the run row, in the execution payload and in n8n's binary store. These
assert, offline against the committed exports, that the bounds that keep that from
growing without limit are still in place:

  * ``visual_studio_table`` is pruned on a short window and ``TemporalFiles`` with it,
  * the workflows whose payload *is* the artifact do not persist successful payloads,
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

# The workflows whose node output carries a rendered artifact (a base64 data URL), so
# their successful executions are the ones that filled execution_data: measured
# 511 MB for Visual Studio Test, 377 MB for Visual Studio, 96 MB for LinkedIn Post
# Sharing, 44 MB for the Prune (deleteRows returns the rows it deleted).
ARTIFACT_WORKFLOWS = [
    "visual_studio",
    "visual_studio_test",
    "linked_in_post_sharing",
    "visual_studio_prune",
]

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
def test_the_run_row_window_is_two_days(label, document):
    node = _nodes(document)["delete_expired"]
    params = node["parameters"]
    assert params["operation"] == "deleteRows"
    assert params["dataTableId"]["value"] == "visual_studio_table"
    condition = params["filters"]["conditions"][0]
    assert condition["keyName"] == "createdAt"
    match = WINDOW_RE.search(condition["keyValue"])
    assert match, f"the prune window is not a day count: {condition['keyValue']!r}"
    assert int(match.group(1)) <= 2, "the run row must not be kept for a week"


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
def test_the_prune_runs_after_the_run_row_delete(label, document):
    assert _nodes(document)["delete_expired"]["name"] == "delete_expired"
    assert "delete_expired_files" in [
        edge["node"] for branch in document["connections"]["delete_expired"]["main"] for edge in branch
    ]


@pytest.mark.parametrize("name", ARTIFACT_WORKFLOWS)
def test_artifact_workflows_do_not_persist_successful_payloads(name):
    settings = json.loads((WORKFLOWS / f"{name}.workflow.json").read_text())["settings"]
    assert settings.get("saveDataSuccessExecution") == "none", (
        f"{name}: a successful execution would persist a multi-megabyte artifact payload"
    )
    # The failure path is the one that needs the payload.
    assert settings.get("saveDataErrorExecution", "all") != "none", f"{name}: errors must still be recorded"


@pytest.mark.parametrize("name", DEAD_WORKFLOWS)
def test_the_dead_workflows_stay_deleted(name):
    assert not (WORKFLOWS / f"{name}.workflow.json").exists(), (
        f"{name} was inactive and referenced by nothing; re-adding it re-adds a live workflow"
    )


# --- the asset lives in Garage, the row names it -------------------------------------
#
# visual_studio_table hit its 200 MB cap on 2026-10-13 with only 12 rows, four of them
# 32-34 MB, because RESULT carried each asset as a base64 data URL. Run 13256 authored,
# rendered and fetched its asset and then failed at record_run. The bytes now go to the
# bucket and the row carries the key.


@pytest.mark.parametrize("label,document", list(_copies(STUDIO)))
def test_the_run_row_carries_the_object_key_and_not_the_bytes(label, document):
    nodes = _nodes(document)
    code = nodes["run_record"]["parameters"]["jsCode"]
    assert "S3_KEY" in code, "the row does not name the stored object"
    assert "JSON.stringify(items)" not in code, "the row still serialises the assets whole"
    assert "IMAGE: ''" in code, "the row still carries the base64 data URL"

    upload = nodes["upload_assets"]
    assert upload["type"] == "n8n-nodes-base.s3"
    assert upload["parameters"]["operation"] == "upload"
    assert upload["parameters"]["bucketName"] == "datahub-local-temp"
    assert upload["parameters"]["binaryData"] is True
    # continueRegularOutput forwards the input unchanged, so a failed upload would still
    # hand run_record a key for an object that was never written. Let it fail the run.
    assert "onError" not in upload, "a failed upload would be recorded as a stored object"

    assert _targets(document, "merge_branches", 0) == ["prepare_uploads"]
    assert _targets(document, "prepare_uploads", 0) == ["upload_assets"]
    assert _targets(document, "upload_assets", 0) == ["run_record"]
    assert _targets(document, "run_record", 0) == ["record_run"]


@pytest.mark.parametrize("label,document", list(_copies(STUDIO)))
def test_the_response_still_carries_the_asset(label, document):
    # record_run is not terminal: set_result builds the response from merge_branches, so
    # shrinking the row cannot change what the caller receives. LinkedIn Post Sharing
    # reads ASSETS[].IMAGE and throws without a data URL.
    code = _nodes(document)["set_result"]["parameters"]["jsCode"]
    assert "merge_branches" in code and "ASSETS" in code
    assert _targets(document, "record_run", 0) == ["set_result"]


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
    assert int(match.group(1)) <= 2, "an object must not outlive its run row"

    assert _targets(document, "delete_expired_files", 0) == ["list_assets"]
    assert _targets(document, "list_assets", 0) == ["filter_old_assets"]
    assert _targets(document, "filter_old_assets", 0) == ["delete_assets"]


def test_the_failed_row_is_not_swallowed():
    # On 2026-10-13 record_failed's onError: continueRegularOutput hid its own failure:
    # the write hit the same size limit, the error workflow reported success, and no
    # FAILED row existed for run 13256. Stated explicitly, because the API rejects a
    # null and a merely absent key is indistinguishable from one never set.
    for label, document in _copies(ERROR_WF):
        node = _nodes(document)["record_failed"]
        assert node.get("onError") != "continueRegularOutput", (
            f"{label}: a FAILED row that cannot be written would report success"
        )
        assert node.get("onError") == "stopWorkflow", (
            f"{label}: the failure path must stop the workflow, not leave it to a default"
        )
