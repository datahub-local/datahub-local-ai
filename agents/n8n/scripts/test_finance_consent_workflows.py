"""Guard the finance consent-detection fixes in the n8n exports.

Two bugs this locks down, both from the 2026-09-28 incident:

- The daily nudge linked to a form id that no longer exists (the form trigger's
  id changed in commit 8df0f1b), so a renewal link dead-ended. The nudge's form
  id must equal the live form trigger's ``webhookId``.
- The daily check trusted ``GET /sessions/{id}`` alone, which Enable Banking
  documents as inconclusive: it read ``AUTHORIZED`` while every data call failed.
  The check must probe a data endpoint (``GET /accounts/{uid}/balances``), and
  the hourly watch must use only the budget-free session endpoint.

The network is not involved; these run on the committed export files.
"""

import json
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"
RENEWAL = WORKFLOWS / "enable_banking_token_renewal.workflow.json"
WATCH = WORKFLOWS / "enable_banking_consent_watch.workflow.json"


def _copies(path):
    data = json.loads(path.read_text())
    return ("nodes", data.get("nodes")), (
        "activeVersion.nodes",
        (data.get("activeVersion") or {}).get("nodes"),
    )


def _connections(path):
    data = json.loads(path.read_text())
    return ("connections", data.get("connections")), (
        "activeVersion.connections",
        (data.get("activeVersion") or {}).get("connections"),
    )


def _node(nodes, name):
    for node in nodes or []:
        if node.get("name") == name:
            return node
    return None


def _main(connections, name):
    return ((connections or {}).get(name) or {}).get("main")


def _targets(connections, name):
    return [
        out.get("node")
        for branch in (_main(connections, name) or [])
        for out in (branch or [])
    ]


@pytest.mark.parametrize("label,nodes", _copies(RENEWAL), ids=lambda v: v if isinstance(v, str) else "")
def test_nudge_link_points_at_the_live_form(label, nodes):
    form = _node(nodes, "Form: Start Renewal")
    evaluate = _node(nodes, "Evaluate Consent")
    assert form and evaluate, f"{label}: expected both form and check nodes"
    form_id = form["webhookId"]
    assert f"/form/{form_id}" in evaluate["parameters"]["jsCode"], (
        f"{label}: the nudge link does not target the live form id {form_id}"
    )


@pytest.mark.parametrize("label,nodes", _copies(RENEWAL), ids=lambda v: v if isinstance(v, str) else "")
def test_daily_check_has_a_data_plane_probe(label, nodes):
    probe = _node(nodes, "Probe Account Data")
    assert probe, f"{label}: no data-plane probe node"
    url = probe["parameters"]["url"]
    assert "/accounts/" in url and "/balances" in url, f"{label}: probe is not a balances call ({url})"


@pytest.mark.parametrize("label,connections", _connections(RENEWAL), ids=lambda v: v if isinstance(v, str) else "")
def test_data_plane_probe_feeds_the_decision(label, connections):
    assert "Probe Account Data" in _targets(connections, "Get Session Status"), (
        f"{label}: the session-status node does not feed the data probe"
    )
    assert "Evaluate Consent" in _targets(connections, "Probe Account Data"), (
        f"{label}: the data probe does not feed the decision"
    )


def test_watch_workflow_is_hourly_budget_free_and_wired():
    data = json.loads(WATCH.read_text())
    assert (data.get("settings") or {}).get("errorWorkflow"), "the watch is an entry point and must report"
    triggers = [n for n in data["nodes"] if n["type"] == "n8n-nodes-base.scheduleTrigger"]
    assert len(triggers) == 1, "expected exactly one hourly trigger"
    expr = triggers[0]["parameters"]["rule"]["interval"][0]["expression"]
    assert expr == "0 * * * *", f"expected hourly, got {expr!r}"
    status = _node(data["nodes"], "Get Session Status")
    assert status and "/sessions/" in status["parameters"]["url"], "the watch must use the budget-free endpoint"
    watch = _node(data["nodes"], "Watch Transitions")
    assert "$getWorkflowStaticData" in watch["parameters"]["jsCode"], (
        "the watch must persist state to report only transitions"
    )
