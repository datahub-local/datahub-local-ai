"""Guard the finance consent-detection fixes in the n8n exports.

Bugs this locks down, all from the 2026-09-28/29 incidents:

- The daily nudge linked to a form id that no longer exists (the form trigger's
  id changed in commit 8df0f1b), so a renewal link dead-ended. The nudge's form
  id must equal the live form trigger's ``webhookId``.
- The daily check trusted ``GET /sessions/{id}`` alone, which Enable Banking
  documents as inconclusive: it read ``AUTHORIZED`` while every data call failed.
  It later gained a ``GET /accounts/{uid}/balances`` probe, and then gave it up
  again to the watch when the fleet's ~8-fetches-a-day overshoot of the ASPSP's
  ~4/day background limit surfaced; it now nudges on the stored expiry and on a
  session read that is not AUTHORIZED, and the watch owns liveness.
- The watch spent its calls on the session-status read, which reaches neither the
  ASPSP nor the truth. It must probe ``/balances`` every 12 hours: that data fetch
  is what makes Enable Banking renew the ASPSP token internally, and 12h keeps
  the fleet (watch 2 + ingest 2) inside the ASPSP's ~4/day background limit.
  Consent drops have happened since the integration started, at every cadence
  tried, so the watch buys detection, not prevention: it posts on a state change
  *and* on the first observation of a non-OK state, because a transitions-only
  rule silences a consent that was already dead when the watch first looked.
- The daily check must not spend a data-plane call of its own: its balances probe
  was one of the ~8 fetches a day the fleet was making against that ~4 limit. It
  keeps the budget-free ``GET /sessions/{id}`` and nudges only when that read
  disagrees with AUTHORIZED; the watch is the liveness signal.

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
def test_daily_check_spends_no_data_plane_calls(label, nodes):
    # The fleet was making ~8 ASPSP data fetches a day per account against a
    # ~4/day background limit; the 12h watch is the only data-plane prober left
    # and GET /sessions/{id} is budget-free.
    assert not _node(nodes, "Probe Account Data"), (
        f"{label}: the daily check must not spend an ASPSP data fetch"
    )
    for node in nodes or []:
        url = (node.get("parameters") or {}).get("url", "")
        assert "/balances" not in url, f"{label}: {node.get('name')} probes the data plane ({url})"
    evaluate = _node(nodes, "Evaluate Consent")
    assert evaluate, f"{label}: expected the decision node"
    assert "Probe Account Data" not in evaluate["parameters"]["jsCode"], (
        f"{label}: the decision still reads the removed data probe"
    )


@pytest.mark.parametrize("label,connections", _connections(RENEWAL), ids=lambda v: v if isinstance(v, str) else "")
def test_session_status_feeds_the_decision_directly(label, connections):
    assert "Evaluate Consent" in _targets(connections, "Get Session Status"), (
        f"{label}: the budget-free session probe must feed the decision"
    )


def test_watch_workflow_is_twelve_hourly_on_the_data_plane():
    data = json.loads(WATCH.read_text())
    assert (data.get("settings") or {}).get("errorWorkflow"), "the watch is an entry point and must report"
    triggers = [n for n in data["nodes"] if n["type"] == "n8n-nodes-base.scheduleTrigger"]
    assert len(triggers) == 1, "expected exactly one schedule trigger"
    expr = triggers[0]["parameters"]["rule"]["interval"][0]["expression"]
    # 2 watch fetches + the ingest's 2 stay inside the ~4/day background limit;
    # consent drops happened at every cadence tried, so this buys detection.
    assert expr == "0 */12 * * *", f"expected every 12 hours, got {expr!r}"
    probe = _node(data["nodes"], "Probe Balances")
    assert probe, "the watch must probe the data plane to trigger Enable Banking's internal token renewal"
    url = probe["parameters"]["url"]
    assert "/accounts/" in url and "/balances" in url, f"probe is not a balances call ({url})"
    assert not _node(data["nodes"], "Get Session Status"), (
        "session status is not a data fetch, so it neither renews the token nor detects a dead consent"
    )
    watch = _node(data["nodes"], "Watch Transitions")
    assert "$getWorkflowStaticData" in watch["parameters"]["jsCode"], (
        "the watch must persist state to report only transitions"
    )
    assert "first observation" in watch["parameters"]["jsCode"], (
        "a consent already dead on the watch's first observation must still post"
    )
    build = _node(data["nodes"], "Build Probes")
    assert "probes.length === 0" in build["parameters"]["jsCode"], (
        "configured accounts with no probeable session must fail loudly, not report 'unchanged'"
    )
