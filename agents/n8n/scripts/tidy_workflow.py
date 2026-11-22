#!/usr/bin/env python3
"""Lay a workflow export's nodes out on the canonical grid.

An export is a backup, so a position written here is only real once the live
instance has it: --changes emits the apply_workflow_changes.py spec for exactly
the positions written. Editing live is a UI step, and the nightly backup then
reproduces these bytes.

    tidy_workflow.py agents/n8n/workflows/*.workflow.json              # check
    tidy_workflow.py --write --changes /tmp/tidy.json some.workflow.json  # rewrite

The layout is the rule, not a suggestion: without --write the script fails any
file whose positions differ from it, so a hand-dragged node does not reach live.
It is deterministic and idempotent -- a second --write changes nothing.

Shape: connected components stack vertically. Inside one, nodes are layered
left to right by longest path over main connections, with AI sub-node edges
reversed so a model/tool/memory sits right of the agent it serves. Columns are
X_STEP apart, rows Y_STEP, and every node a NODE box. An edge that skips a
column reserves a row in each column it crosses, so it does not run through a
node. Ordering is barycentric over four sweeps, seeded from the file's own
node order, which the editor and the backup both keep stable, so a tidy is
reproducible and never reshuffles a column run to run.
Sticky notes translate with the nodes they cover and grow to keep covering
them; one that covers nothing follows its nearest node.

The grid is n8n's own: GRID_SIZE 16, DEFAULT_NODE_SIZE 96, NODE_X_SPACING 128,
NODE_Y_SPACING 96, so a chain steps 224 x 192 like the editor's Tidy up.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from itertools import pairwise

GRID = 16
NODE = 96
X_STEP = NODE + GRID * 8
Y_STEP = NODE + GRID * 6
COMPONENT_GAP = GRID * 8
STICKY_PADDING = GRID
SWEEPS = 4
VIRTUAL = "\0"


def is_sticky(node):
    return node.get("type", "").endswith("stickyNote")


def layout_edges(workflow):
    """Main edges as written, AI sub-node edges reversed, de-duplicated."""
    nodes = {n["name"]: n for n in workflow["nodes"]}
    edges = []
    for src, by_type in (workflow.get("connections") or {}).items():
        if src not in nodes:
            continue
        for ctype, branches in by_type.items():
            for branch in branches or []:
                for edge in branch or []:
                    dst = (edge or {}).get("node")
                    if dst not in nodes:
                        continue
                    edges.append((src, dst) if ctype == "main" else (dst, src))
    return list(dict.fromkeys(edges))


def components(names, edges):
    """Groups of nodes connected to each other, keyed by their first node."""
    parent = {name: name for name in names}

    def find(name):
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    for a, b in edges:
        parent[find(a)] = find(b)
    groups = defaultdict(list)
    for name in names:
        groups[find(name)].append(name)
    return list(groups.values())


def without_cycles(edges):
    """Edges minus the back edges DFS meets, so longest-path layering converges."""
    adj = defaultdict(list)
    for src, dst in edges:
        adj[src].append(dst)
    state, kept = {}, []
    for root in list(adj):
        if root in state:
            continue
        state[root] = 1
        stack = [(root, iter(adj[root]))]
        while stack:
            name, children = stack[-1]
            for dst in children:
                if state.get(dst) == 1:
                    continue  # closes a loop: keep the loop, drop it from the layering
                kept.append((name, dst))
                if dst not in state:
                    state[dst] = 1
                    stack.append((dst, iter(adj.get(dst, ()))))
                    break
            else:
                state[name] = 2
                stack.pop()
    return kept


def layer_of(names, edges):
    layer = {name: 0 for name in names}
    for _ in range(len(names)):
        moved = False
        for src, dst in edges:
            want = layer[src] + 1
            if layer[dst] < want:
                layer[dst] = want
                moved = True
        if not moved:
            break
    return layer


def chains(edges, layer):
    """An edge as (column, key) steps, one per column it passes through."""
    out = []
    for src, dst in edges:
        keys = [(layer[src], src)]
        keys += [
            (column, f"{VIRTUAL}{src}->{dst}@{column}")
            for column in range(layer[src] + 1, layer[dst])
        ]
        keys.append((layer[dst], dst))
        out.append(keys)
    return out


def ordered_layers(names, edges, seed):
    layer = layer_of(names, without_cycles(edges))
    paths = chains(edges, layer)
    layers = defaultdict(list)
    for name in names:
        layers[layer[name]].append(name)
    for path in paths:
        for column, key in path:
            if key.startswith(VIRTUAL):
                layers[column].append(key)
                seed.setdefault(key, seed[path[0][1]])
    for column in layers:
        layers[column].sort(key=lambda key: (seed[key], key))

    previous, following = defaultdict(list), defaultdict(list)
    for path in paths:
        for (_, a), (_, b) in pairwise(path):
            following[a].append(b)
            previous[b].append(a)

    order = {key: index for column in layers for index, key in enumerate(layers[column])}
    for sweep in range(SWEEPS):
        columns = range(1, len(layers)) if sweep % 2 == 0 else range(len(layers) - 2, -1, -1)
        for column in columns:
            neighbours = previous if sweep % 2 == 0 else following
            entries = layers[column]
            rank = {key: index for index, key in enumerate(entries)}
            scored = []
            for key in entries:
                nearby = [order[n] for n in neighbours.get(key, ()) if n in order]
                barycentre = sum(nearby) / len(nearby) if nearby else len(entries) / 2
                scored.append((barycentre, rank[key], key))
            layers[column] = [key for _, _, key in sorted(scored)]
            for index, key in enumerate(layers[column]):
                order[key] = index
    return [layers[column] for column in range(max(layers) + 1)]


def place(names, edges):
    """Absolute positions for one component, top-left at (0, 0)."""
    seed = {name: rank for rank, name in enumerate(names)}
    layers = ordered_layers(names, edges, seed)
    tallest = max(len(entries) for entries in layers)
    positions = {}
    for column, entries in enumerate(layers):
        offset = (tallest - len(entries)) // 2
        for row, key in enumerate(entries):
            if key.startswith(VIRTUAL):
                continue
            positions[key] = [column * X_STEP, (offset + row) * Y_STEP]
    return positions


def sticky_box(node):
    parameters = node.get("parameters") or {}
    return (
        int(node["position"][0]),
        int(node["position"][1]),
        int(parameters.get("width", GRID * 15)),
        int(parameters.get("height", GRID * 10)),
    )


def covered_by(x, y, width, height, positions):
    return [
        name
        for name, (nx, ny) in positions.items()
        if x <= nx <= x + width and y <= ny <= y + height
    ]


def nearest(corner, positions):
    return min(
        positions,
        key=lambda name: (positions[name][0] - corner[0]) ** 2
        + (positions[name][1] - corner[1]) ** 2,
    )


def place_stickies(workflow, before, after):
    """A sticky wraps the nodes it covers; one that covers none is a header.

    Wrapping keeps the author's size and follows its nodes, growing while a
    node it should cover has slipped outside. A header sits above the node its
    bottom-left corner is nearest to, which is a fixed point: the placed box is
    still nearest to that node next time, so a check holds on what --write left.
    """
    placed = {}
    for sticky in (n for n in workflow["nodes"] if is_sticky(n)):
        x, y, width, height = sticky_box(sticky)
        covered = covered_by(x, y, width, height, before)
        if covered:
            for _ in range(3):
                left = min(before[name][0] for name in covered)
                top = min(before[name][1] for name in covered)
                box_x = x + min(after[name][0] for name in covered) - left
                box_y = y + min(after[name][1] for name in covered) - top
                right = max(after[name][0] for name in covered) + NODE + STICKY_PADDING
                bottom = max(after[name][1] for name in covered) + NODE + STICKY_PADDING
                box_w = max(width, -(-(right - box_x) // GRID) * GRID)
                box_h = max(height, -(-(bottom - box_y) // GRID) * GRID)
                wider = covered_by(box_x, box_y, box_w, box_h, after)
                if set(wider) <= set(covered):
                    break
                covered = wider
            placed[sticky["name"]] = (
                box_x - box_x % GRID,
                box_y - box_y % GRID,
                box_w,
                box_h,
            )
        else:
            anchor = nearest((x, y + height), before)
            box_y = after[anchor][1] - height - STICKY_PADDING
            placed[sticky["name"]] = (
                after[anchor][0],
                box_y - box_y % GRID,
                width,
                height,
            )
    return placed


def canonical(workflow):
    """The layout this file must have: node positions and sticky boxes."""
    real = [n for n in workflow["nodes"] if not is_sticky(n)]
    before = {n["name"]: (int(n["position"][0]), int(n["position"][1])) for n in real}
    edges = layout_edges(workflow)
    names = [n["name"] for n in real]
    groups = components(names, [e for e in edges if e[0] in before and e[1] in before])
    groups.sort(key=lambda g: (min(before[n][1] for n in g), min(before[n][0] for n in g), min(g)))

    positions, stack = {}, 0
    for group in groups:
        inside = set(group)
        block = place(group, [e for e in edges if e[0] in inside and e[1] in inside])
        height = max((row for _, row in block.values()), default=0) + NODE
        for name, (x, y) in block.items():
            positions[name] = (x, y + stack)
        stack += height + COMPONENT_GAP

    left = min(x for x, _ in positions.values())
    top = min(y for _, y in positions.values())
    positions = {name: [x - left, y - top] for name, (x, y) in positions.items()}
    return positions, place_stickies(workflow, before, positions)


def diff(workflow, positions, stickies):
    """Node name -> the field changes the layout asks for, in apply-script paths."""
    changes = {}
    for node in workflow["nodes"]:
        name = node["name"]
        parameters = node.get("parameters") or {}
        got = {"position": [int(v) for v in node["position"]]}
        if is_sticky(node):
            if name not in stickies:
                continue
            x, y, width, height = stickies[name]
            want = {"position": [x, y], "parameters.width": width, "parameters.height": height}
            got["parameters.width"] = int(parameters.get("width", GRID * 15))
            got["parameters.height"] = int(parameters.get("height", GRID * 10))
        else:
            if name not in positions:
                continue
            want = {"position": positions[name]}
        delta = {field: value for field, value in want.items() if got.get(field) != value}
        if delta:
            changes[name] = delta
    return changes


def write(workflow, changes):
    for section in (workflow, workflow.get("activeVersion") or {}):
        for node in section.get("nodes") or []:
            for field, value in changes.get(node["name"], {}).items():
                key, _, leaf = field.partition(".")
                if leaf:
                    node.setdefault(key, {})[leaf] = value
                else:
                    node[key] = value


def read(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save(path, workflow):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(workflow, indent=2, ensure_ascii=False))


def merge_changes(path, specs):
    """Positions join a spec someone already wrote instead of replacing it."""
    try:
        with open(path, encoding="utf-8") as handle:
            existing = json.load(handle)
    except FileNotFoundError:
        existing = []
    if isinstance(existing, dict):
        existing = [existing]
    by_workflow = {spec.get("workflow"): spec for spec in existing}
    for spec in specs:
        target = by_workflow.get(spec["workflow"])
        if target is None:
            target = by_workflow[spec["workflow"]] = {"workflow": spec["workflow"]}
        for name, fields in spec["nodes"].items():
            target.setdefault("nodes", {}).setdefault(name, {}).update(fields)
    return list(by_workflow.values())


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("paths", nargs="+", metavar="WORKFLOW.json")
    parser.add_argument("--write", action="store_true", help="rewrite; default is a check")
    parser.add_argument(
        "--changes",
        metavar="FILE",
        help="merge the positions into an apply_workflow_changes.py spec (created if absent)",
    )
    parser.add_argument("--verbose", action="store_true", help="list every moved node")
    args = parser.parse_args()

    untidy = 0
    specs = []
    for path in args.paths:
        workflow = read(path)
        positions, stickies = canonical(workflow)
        changes = diff(workflow, positions, stickies)
        moved = len(changes)
        untidy += 1 if moved else 0
        print(f"{path}: {moved} node(s) off-layout")
        if changes and args.verbose:
            for name, fields in changes.items():
                print(f"  {name}: {fields}")
        if moved and args.write:
            write(workflow, changes)
            save(path, workflow)
            print("  written")
        if changes:
            specs.append({"workflow": workflow.get("name", path), "nodes": changes})

    if args.changes:
        merged = merge_changes(args.changes, specs)
        with open(args.changes, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(merged, indent=2))
        print(f"{args.changes}: {len(merged)} workflow(s) to apply live")
    if untidy and not (args.write or args.changes):
        sys.exit(f"{untidy} file(s) are not tidy -- run with --write")


if __name__ == "__main__":
    main()
