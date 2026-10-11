"""Tidy-up invariants for every n8n export.

A workflow edit is not done until the graph is tidy. Most of that is judgement -- node
names, grouping, how it reads in the editor -- but these are objective, and each one has
bitten: the two copies of a graph drifting apart, a node nothing connects, a reference
left behind by a rename, a call to a workflow that is not in the repository.

Parametrized over every export, like ``test_workflow_exports.py`` and
``test_workflow_expressions.py``, so it holds for the next workflow too rather than for
the one that prompted it. Offline: it reads the committed exports, no cluster.

Not asserted here, deliberately:

  * overlapping node boxes. They pass today at 100x60, but box size is a layout choice and
    a fixed guess would fail a legitimate layout. Only exact-duplicate positions are an
    error; spacing and alignment stay review.
  * whether an unreferenced workflow should still exist. A scheduled or webhook workflow
    has no inbound reference by design, so nothing offline separates it from an abandoned
    probe. That stays a judgement call, recorded in AGENTS.md.
"""

import json
import re
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"
EXPORTS = sorted(WORKFLOWS.glob("*.workflow.json"))

# `$('Node Name')` or `$("Node Name")`, the n8n idiom for reading another node's output.
REF_RE = re.compile(r"\$\(\s*['\"]([^'\"]+)['\"]\s*\)")


def _ids():
    """Every workflow id the repository declares, so a call can be resolved."""
    ids = {}
    for path in EXPORTS:
        data = json.loads(path.read_text())
        if data.get("id"):
            ids[data["id"]] = path.name
    return ids


IDS = _ids()


def _copies(path):
    """(label, nodes, connections) for both copies of an export.

    An export carries its nodes twice, at the top level and inside ``activeVersion``; a
    fix applied to one copy is a live bug, so each is checked.
    """
    data = json.loads(path.read_text())
    yield "top level", data.get("nodes") or [], data.get("connections") or {}
    active = data.get("activeVersion") or {}
    if active.get("nodes"):
        yield "activeVersion", active["nodes"], active.get("connections") or {}


def _document(path):
    return json.loads(path.read_text())


@pytest.mark.parametrize("path", EXPORTS, ids=lambda p: p.name)
def test_both_copies_of_the_graph_agree(path):
    """A version bump that touched only one copy would run a different graph than it shows."""
    data = _document(path)
    active = data.get("activeVersion") or {}
    if not active.get("nodes"):
        pytest.skip("no published copy in this export")
    assert [n["name"] for n in data["nodes"]] == [n["name"] for n in active["nodes"]], (
        "the top-level nodes and activeVersion.nodes differ; applying a change to one copy only"
    )


@pytest.mark.parametrize("path", EXPORTS, ids=lambda p: p.name)
def test_node_names_are_unique_and_non_empty(path):
    for label, nodes, _ in _copies(path):
        names = [n["name"] for n in nodes]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        assert not duplicates, f"{label}: duplicate node names {duplicates}"
        assert all(n.strip() for n in names), f"{label}: a node has a blank name"


@pytest.mark.parametrize("path", EXPORTS, ids=lambda p: p.name)
def test_no_node_is_left_unconnected(path):
    """A node with no edge in either direction is dead weight in the editor and the graph."""
    for label, nodes, connections in _copies(path):
        touched = set()
        for source, types in connections.items():
            touched.add(source)
            for branches in types.values():
                for branch in branches or []:
                    for edge in branch or []:
                        touched.add(edge["node"])
        isolated = [
            n["name"]
            for n in nodes
            if n["name"] not in touched and "stickyNote" not in n["type"]
        ]
        assert not isolated, f"{label}: nodes nothing connects: {isolated}"


@pytest.mark.parametrize("path", EXPORTS, ids=lambda p: p.name)
def test_no_two_nodes_share_a_position(path):
    for label, nodes, _ in _copies(path):
        by_position = {}
        for node in nodes:
            by_position.setdefault(tuple(node.get("position") or [0, 0]), []).append(node["name"])
        stacked = {pos: who for pos, who in by_position.items() if len(who) > 1}
        assert not stacked, f"{label}: nodes stacked on one position: {stacked}"


@pytest.mark.parametrize("path", EXPORTS, ids=lambda p: p.name)
def test_every_node_reference_resolves(path):
    """A rename that leaves a `$('old name')` behind throws at run time, on that branch only."""
    for label, nodes, _ in _copies(path):
        names = {n["name"] for n in nodes}
        broken = []
        for node in nodes:
            for reference in sorted(set(REF_RE.findall(json.dumps(node.get("parameters") or {})))):
                if reference not in names:
                    broken.append(f"{node['name']} -> $('{reference}')")
        assert not broken, f"{label}: reference to a node that does not exist: {broken}"


@pytest.mark.parametrize("path", EXPORTS, ids=lambda p: p.name)
def test_every_called_workflow_exists_in_the_repository(path):
    """A sub-workflow or error handler that is not committed is one the backup cannot restore."""
    data = _document(path)
    targets = []
    for label, nodes, _ in _copies(path):
        for node in nodes:
            target = (node.get("parameters") or {}).get("workflowId")
            # A dynamic id (`={{ $workflow.id }}`) is a loop over workflows, not a call.
            if isinstance(target, dict) and isinstance(target.get("value"), str) and not target["value"].startswith("="):
                targets.append((label, node["name"], target["value"]))
    error_handler = (data.get("settings") or {}).get("errorWorkflow")
    if error_handler:
        targets.append(("settings", "errorWorkflow", error_handler))
    missing = [
        f"{label}: {where} -> {wid}"
        for label, where, wid in targets
        if wid not in IDS
    ]
    assert not missing, f"references a workflow the repository does not have: {missing}"
