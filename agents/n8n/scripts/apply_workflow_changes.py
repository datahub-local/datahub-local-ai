#!/usr/bin/env python3
"""Apply field changes to live n8n workflows: read live, diff, write on --apply.

Editing an export under ../workflows/ changes nothing in the cluster -- that
directory is a backup the live instance writes to, not a source. This is the
apply step for the other direction, and it exists for the same reason
reseed_memory.py does in agents/sympozium/: a source edit that nothing
reconciles is not done when it is merged.

It never posts a whole exported body. It reads each workflow live, sets only
the named fields on the named nodes, and PUTs name/nodes/connections/settings.

Reachable in-cluster only -- the public host routes /api/ through
oauth2-proxy, which an API key does not satisfy:

    B64=$(base64 -w0 agents/n8n/scripts/apply_workflow_changes.py)
    OV=$(python3 agents/n8n/scripts/apply_workflow_changes.py --print-pod-overrides)
    kubectl -n security run n8n-apply --rm -i --restart=Never \
      --image=python:3.12-alpine --override-type=strategic --overrides="$OV" \
      --command -- sh -c "echo $B64 | base64 -d > /tmp/s.py && python3 /tmp/s.py \
        --workflow 'Some Workflow' --set 'some_node:executeOnce=true'"

Examples:

    # one workflow, inline
    --workflow 'Content Feed Curator' \
      --require-edge 'fetch_candidates>read_legacy_sheet' \
      --set 'read_legacy_sheet:executeOnce=true'

    # wire an error workflow
    --workflow 'Download Content' --set-setting 'errorWorkflow=fejq5nN6LP3F820w'

    # many workflows, or a graph edit: a JSON list of
    #   {"workflow": id-or-name, "requireEdges": [["a","b"]],
    #    "nodes": {"n": {"field": value}}, "settings": {"field": value},
    #    "addNodes": [ {full n8n node object} ],
    #    "connections": {"src": [[{"node": "dst", "type": "main", "index": 0}]]}}
    --changes /tmp/changes.json

Adding a node or rewiring is file-only: a node object does not fit on a command
line, and a graph edit is the kind that wants reviewing before it runs. Both are
idempotent -- an addNodes entry whose name already exists is skipped, and a
connections entry already matching is skipped -- so a spec can be re-run.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

POD_NAME = "n8n-apply"
DEFAULT_URL = "http://datahub-local-core-automation-n8n.automation.svc.cluster.local"


def api(url, key, path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{url.rstrip('/')}{path}",
        data=data,
        method=method,
        headers={"X-N8N-API-KEY": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read() or "{}")
    except urllib.error.HTTPError as exc:
        sys.exit(f"{method} {path} -> {exc.code} {exc.read().decode()[:400]}")


def pod_overrides():
    # The container name must match the pod name, or a strategic-merge override
    # appends a second container instead of patching the generated one.
    return json.dumps(
        {
            "spec": {
                "containers": [
                    {
                        "name": POD_NAME,
                        "image": "python:3.12-alpine",
                        "env": [
                            {
                                "name": "N8N_API_KEY",
                                "valueFrom": {
                                    "secretKeyRef": {"name": "n8n-root", "key": "N8N_API_KEY"}
                                },
                            },
                            {"name": "N8N_URL", "value": DEFAULT_URL},
                        ],
                    }
                ]
            }
        }
    )


def parse_value(raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def parse_set(items):
    """'node:field.path=value' -> {node: {field.path: value}}"""
    out = {}
    for item in items:
        target, _, raw = item.partition("=")
        if not raw and "=" not in item:
            sys.exit(f"--set expects node:field=value, got {item!r}")
        node, sep, field = target.partition(":")
        if not sep or not field:
            sys.exit(f"--set expects node:field=value, got {item!r}")
        out.setdefault(node, {})[field] = parse_value(raw)
    return out


def parse_settings(items):
    out = {}
    for item in items:
        field, _, raw = item.partition("=")
        if not field:
            sys.exit(f"--set-setting expects field=value, got {item!r}")
        out[field] = parse_value(raw)
    return out


def get_path(obj, path):
    for part in path.split("."):
        if not isinstance(obj, dict) or part not in obj:
            return None
        obj = obj[part]
    return obj


def set_path(obj, path, value):
    parts = path.split(".")
    for part in parts[:-1]:
        obj = obj.setdefault(part, {})
    obj[parts[-1]] = value


def find_workflow(url, key, ref):
    """Resolve an id or an exact name to the live workflow."""
    listing = api(url, key, "/api/v1/workflows?limit=250").get("data", [])
    by_id = [w for w in listing if w.get("id") == ref]
    by_name = [w for w in listing if w.get("name") == ref]
    hits = by_id or by_name
    if not hits:
        sys.exit(f"no live workflow with id or name {ref!r}")
    if len(hits) > 1:
        sys.exit(f"{ref!r} matches {len(hits)} workflows; use the id")
    return api(url, key, f"/api/v1/workflows/{hits[0]['id']}")


def summarize_main(main):
    """[[{node: a}], [{node: b}]] -> '0->a | 1->b'"""
    if main is None:
        return "<none>"
    return " | ".join(
        f"{bi}->{','.join(o.get('node', '?') for o in (branch or [])) or '(nothing)'}"
        for bi, branch in enumerate(main)
    )


def outgoing(connections, name):
    return [
        o["node"]
        for branch in connections.get(name, {}).get("main", []) or []
        for o in (branch or [])
    ]


def process(url, key, spec, do_apply):
    wf = find_workflow(url, key, spec["workflow"])
    wid = wf["id"]
    print(f"\n=== {wf['name']} ({wid})  active={wf.get('active')}  nodes={len(wf['nodes'])}")

    # Optional premise guards: assert the live wiring is still what the change
    # was reasoned about. A change argued from a stale graph is a wrong change.
    for src, dst in spec.get("requireEdges", []):
        got = outgoing(wf["connections"], src)
        print(f"  edge {'ok' if dst in got else 'DRIFT'}: {src} -> {got}")
        if dst not in got:
            sys.exit(f"live wiring differs from the change premise ({src} -> {dst}); stopping")

    by_name = {n["name"]: n for n in wf["nodes"]}
    changes = []

    for node in spec.get("addNodes", []):
        if node["name"] in by_name:
            print(f"  node {node['name']!r} already present")
            continue
        wf["nodes"].append(node)
        by_name[node["name"]] = node
        changes.append((node["name"], "<node>", None, f"added ({node['type']})"))

    # Rewiring replaces a source's whole main array, because a connection is a
    # position in a list -- there is no stable id to patch a single edge by.
    for src, main in spec.get("connections", {}).items():
        if src not in by_name:
            sys.exit(f"connection source {src!r} is not a node in the workflow")
        for branch in main:
            for out in branch or []:
                if out["node"] not in by_name:
                    sys.exit(f"connection target {out['node']!r} is not a node in the workflow")
        before = wf["connections"].get(src, {}).get("main")
        if before == main:
            print(f"  connections from {src!r} already as specified")
            continue
        wf["connections"].setdefault(src, {})["main"] = main
        changes.append((src, "<connections>", summarize_main(before), summarize_main(main)))

    for node_name, fields in spec.get("nodes", {}).items():
        if node_name not in by_name:
            sys.exit(f"node {node_name!r} is not in the live workflow")
        node = by_name[node_name]
        for field, value in fields.items():
            before = get_path(node, field)
            if before == value:
                print(f"  {node_name}.{field} already {value!r}")
                continue
            set_path(node, field, value)
            changes.append((node_name, field, before, value))

    settings = wf.get("settings", {})
    for field, value in spec.get("settings", {}).items():
        before = get_path(settings, field)
        if before == value:
            print(f"  settings.{field} already {value!r}")
            continue
        set_path(settings, field, value)
        changes.append(("<settings>", field, before, value))

    if not changes:
        print("  nothing to change")
        return

    print("  plan:")
    for node_name, field, before, after in changes:
        print(f"    {node_name}.{field}: {before!r} -> {after!r}")

    if not do_apply:
        return

    was_active = wf.get("active")
    api(
        url,
        key,
        f"/api/v1/workflows/{wid}",
        method="PUT",
        body={
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": settings,
        },
    )

    after_wf = api(url, key, f"/api/v1/workflows/{wid}")
    after_nodes = {n["name"]: n for n in after_wf["nodes"]}
    for node_name, field, _, want in changes:
        if field == "<node>":
            ok = node_name in after_nodes
            print(f"  wrote node {node_name}: {'present' if ok else 'MISSING'}")
            continue
        if field == "<connections>":
            got = summarize_main(after_wf["connections"].get(node_name, {}).get("main"))
            print(f"  wrote connections {node_name}: {got}{'' if got == want else '  MISMATCH'}")
            continue
        holder = after_wf.get("settings", {}) if node_name == "<settings>" else after_nodes[node_name]
        got = get_path(holder, field)
        print(f"  wrote {node_name}.{field} = {got!r}{'' if got == want else '  MISMATCH'}")

    # PUT carries no `active` field, so a trigger can come back deactivated.
    print(f"  active: {was_active} -> {after_wf.get('active')}")
    if was_active and not after_wf.get("active"):
        api(url, key, f"/api/v1/workflows/{wid}/activate", method="POST")
        again = api(url, key, f"/api/v1/workflows/{wid}")
        print(f"  re-activated: active={again.get('active')}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workflow", help="live workflow id, or exact name")
    ap.add_argument("--set", action="append", default=[], metavar="NODE:FIELD=VALUE")
    ap.add_argument("--set-setting", action="append", default=[], metavar="FIELD=VALUE")
    ap.add_argument("--require-edge", action="append", default=[], metavar="SRC>DST")
    ap.add_argument("--changes", help="JSON file (or - for stdin) of change specs")
    ap.add_argument("--apply", action="store_true", help="write; default is a dry run")
    ap.add_argument("--print-pod-overrides", action="store_true")
    args = ap.parse_args()

    if args.print_pod_overrides:
        print(pod_overrides())
        return

    if args.changes:
        raw = sys.stdin.read() if args.changes == "-" else open(args.changes).read()
        specs = json.loads(raw)
        if isinstance(specs, dict):
            specs = [specs]
    elif args.workflow:
        edges = []
        for edge in args.require_edge:
            src, sep, dst = edge.partition(">")
            if not sep:
                sys.exit(f"--require-edge expects SRC>DST, got {edge!r}")
            edges.append([src.strip(), dst.strip()])
        specs = [
            {
                "workflow": args.workflow,
                "requireEdges": edges,
                "nodes": parse_set(args.set),
                "settings": parse_settings(args.set_setting),
            }
        ]
    else:
        ap.error("pass --workflow or --changes")

    key = os.environ.get("N8N_API_KEY")
    if not key:
        sys.exit("N8N_API_KEY unset -- mount security/n8n-root into the pod")
    url = os.environ.get("N8N_URL", DEFAULT_URL)

    for spec in specs:
        process(url, key, spec, args.apply)

    if not args.apply:
        print("\ndry run -- rerun with --apply to write")


if __name__ == "__main__":
    main()
