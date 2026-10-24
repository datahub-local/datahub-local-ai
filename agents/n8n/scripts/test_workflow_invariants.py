"""Tidy-up invariants for every n8n export.

A workflow edit is not done until the graph is tidy. Most of that is judgement -- node
names, grouping, how it reads in the editor -- but these are objective, and each one has
bitten: the two copies of a graph drifting apart, a node nothing connects, a reference
left behind by a rename, a call to a workflow that is not in the repository, a failure
nothing reports (or one reported twice because a sub-workflow notified as well as its
caller).

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

# Node types that make a workflow an entry point, and the one that makes it an error handler.
# `manualTrigger` is deliberately absent: n8n does not invoke `settings.errorWorkflow` for a
# manual execution, so a manual run is not something an error workflow can report.
ENTRY_TRIGGERS = {
    "n8n-nodes-base.scheduleTrigger",
    "n8n-nodes-base.webhook",
    "n8n-nodes-base.formTrigger",
}
ERROR_TRIGGER = "n8n-nodes-base.errorTrigger"


def _triggers(data):
    return {node["type"] for node in data.get("nodes") or []}


def _callers():
    """Workflow id -> the workflows whose nodes call it, so a sub-workflow is distinguishable."""
    callers = {}
    for path in EXPORTS:
        data = json.loads(path.read_text())
        for node in data.get("nodes") or []:
            target = (node.get("parameters") or {}).get("workflowId")
            # A dynamic id (`={{ $workflow.id }}`) is a loop over workflows, not a call.
            if isinstance(target, dict) and isinstance(target.get("value"), str) and not target["value"].startswith("="):
                callers.setdefault(target["value"], set()).add(data.get("name"))
    return callers


CALLERS = _callers()


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
def test_every_node_is_reachable_from_a_trigger(path):
    """A chain whose entry edge was replaced is invisible to the isolation check.

    `test_no_node_is_left_unconnected` counts a node as touched when it has an edge in *either*
    direction, so a successor that kept its own outgoing edges looks connected while nothing
    reaches it: execution 14382 (2026-10-19) improved its draft, ended at `select_final_draft`
    as `success`, and stored nothing because the new chain replaced
    `check_draft_error -> derive_slug` and nothing wired the convergence node to it. Walk every
    connection type, not only `main`, because a model or tool sub-node is reached over
    `ai_languageModel` / `ai_tool`.
    """
    for label, nodes, connections in _copies(path):
        triggers = [
            n["name"]
            for n in nodes
            if "trigger" in n["type"].lower() or n["type"].endswith("webhook")
        ]
        assert triggers, f"{label}: no trigger node at all"
        # A model or tool sub-node is reached *from* its consumer over `ai_*`, so walking
        # forward never arrives at it. It is attached by definition once it feeds something.
        subnodes = {
            source
            for source, kinds in connections.items()
            for ctype, branches in kinds.items()
            if ctype != "main" and any(branch for branch in branches or [])
        }
        seen, queue = set(triggers), list(triggers)
        while queue:
            for kinds in (connections.get(queue.pop()) or {}).values():
                for branch in kinds or []:
                    for edge in branch or []:
                        if edge["node"] not in seen:
                            seen.add(edge["node"])
                            queue.append(edge["node"])
        unreachable = [
            n["name"]
            for n in nodes
            if n["name"] not in seen
            and n["name"] not in subnodes
            and "stickyNote" not in n["type"]
        ]
        assert not unreachable, f"{label}: nodes no path reaches from a trigger: {unreachable}"


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


# The only node types in these exports that declare more than one input, and so may
# legitimately be addressed on an index above 0. An export carries no input count per
# node, so this is the one place the test has to know a node type rather than read one.
#
# It matters because n8n pads the inputs a node was not given with `[]`: an edge to an
# input the target does not have still runs, the node executes reading input 0, and the
# data is unreachable -- no error, no output. That is how `if_raster`'s second output was
# wired to `ready_pass` at index 2 (a one-input `noOp`), which made the studio's
# unresolvable-type branch return no items at all: the caller's `execute_visual_studio`
# emitted nothing, its guard never ran and the run ended `success` (2026-10-15).
MULTI_INPUT_TYPES = frozenset({
    "n8n-nodes-base.merge",
    "n8n-nodes-base.compareDatasets",
})


@pytest.mark.parametrize("path", EXPORTS, ids=lambda p: p.name)
def test_no_edge_targets_an_input_the_node_does_not_have(path):
    """A `main` edge onto an input index above 0 is legal only for a multi-input node.

    `ai_*` edges are left alone: a sub-node slot is addressed on an index above 0 by
    design (a chain node's model input is its second input), and enumerating every
    LangChain type to say so would be a list that drifts for no gain.
    """
    for label, nodes, connections in _copies(path):
        types = {n["name"]: n["type"] for n in nodes}
        misplaced = [
            f"{source} -> {edge['node']} ({types.get(edge['node'], '?')}) index={edge.get('index')}"
            for source, kinds in connections.items()
            for branch in kinds.get("main") or []
            for edge in branch or []
            if edge.get("index") and types.get(edge["node"]) not in MULTI_INPUT_TYPES
        ]
        assert not misplaced, f"{label}: edge onto an input the target does not have: {misplaced}"


@pytest.mark.parametrize("path", EXPORTS, ids=lambda p: p.name)
def test_every_tool_attached_to_an_agent_can_be_executed(path):
    """An agent's tool must implement ``execute``, not only ``supplyData``.

    The v3 agent hands a tool call to the workflow engine, which runs the node through its
    own executor and needs an ``execute`` method. A tool node with only ``supplyData`` still
    connects, still shows in the editor's own catalog, and fails on every call with
    ``has a "supplyData" method but no "execute" method`` -- measured 2026-10-16, where two
    ``toolHttpRequest`` tools were wired into ``Article Creator``, the model called them,
    every call died, the agent's final output was empty and the draft returned ``EMPTY_DRAFT``.
    The list is read off the installed image, not the catalog:

        grep -L "async execute" n8n-nodes-langchain/dist/nodes/tools/*/*.node.js
    """
    executable = {
        "@n8n/n8n-nodes-langchain.toolWorkflow",
        "@n8n/n8n-nodes-langchain.toolWikipedia",
        "@n8n/n8n-nodes-langchain.toolSearXng",
        "@n8n/n8n-nodes-langchain.toolSerpApi",
        "@n8n/n8n-nodes-langchain.toolWolframAlpha",
        "@n8n/n8n-nodes-langchain.toolCode",
        "@n8n/n8n-nodes-langchain.toolThink",
        "@n8n/n8n-nodes-langchain.toolVectorStore",
    }
    for label, nodes, connections in _copies(path):
        types = {n["name"]: n["type"] for n in nodes}
        unusable = [
            f"{source} ({types.get(source, '?')}) -> {edge['node']}"
            for source, kinds in connections.items()
            for branch in kinds.get("ai_tool") or []
            for edge in branch or []
            # For an `ai_tool` edge the tool is the source and the agent is the target.
            if types.get(source) not in executable
        ]
        assert not unusable, f"{label}: tool node cannot be executed by the agent: {unusable}"


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


@pytest.mark.parametrize("path", EXPORTS, ids=lambda p: p.name)
def test_a_failing_workflow_reports_exactly_once(path):
    """An entry point notifies, a sub-workflow raises, and an error handler never reports itself.

    A workflow with no error handling fails silently in Slack, in the logs and in Prometheus at
    once, and the other direction is no better: an error workflow set on both a sub-workflow and
    its caller posts the same failure twice.
    """
    data = _document(path)
    triggers = _triggers(data)
    handler = (data.get("settings") or {}).get("errorWorkflow")
    if ERROR_TRIGGER in triggers:
        assert not handler, "an error handler must not carry settings.errorWorkflow"
    elif triggers & ENTRY_TRIGGERS:
        assert handler, "an entry point without settings.errorWorkflow fails silently"
    else:
        assert not handler or data.get("id") not in CALLERS, (
            "a sub-workflow propagates to its caller; its own settings.errorWorkflow would report twice"
        )


@pytest.mark.parametrize("path", EXPORTS, ids=lambda p: p.name)
def test_an_error_handler_is_active_and_is_a_handler(path):
    """A handler that is inactive, or not a handler, reports nothing while looking wired.

    Hit 2026-09-28: the target existed, was named, and was deactivated, so n8n answered "is not
    active and cannot be executed" and the failure went unreported.
    """
    data = _document(path)
    handler = (data.get("settings") or {}).get("errorWorkflow")
    if not handler:
        return
    assert handler != data.get("id"), "a workflow cannot be its own error handler"
    filename = IDS.get(handler)
    assert filename, f"settings.errorWorkflow -> {handler} is not a workflow in the repository"
    target = json.loads((WORKFLOWS / filename).read_text())
    assert target.get("active"), f"{target.get('name')} is inactive, so its failures are not reported"
    assert ERROR_TRIGGER in _triggers(target), f"{target.get('name')} carries no error trigger"

