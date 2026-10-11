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
