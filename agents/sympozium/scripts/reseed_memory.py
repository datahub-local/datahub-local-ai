#!/usr/bin/env python3
"""Compare each persona's live memory ConfigMap against its YAML, and repair it.

The controller writes `memory.seeds` **once**, at install, into
`ConfigMap/<ensemble>-<persona>-memory` and never reconciles it. Editing the
YAML and syncing updates the Ensemble, the systemPrompt and the toolPolicy while
the run's `## Memory Context` still carries whatever was written at install. The
drift is therefore silent, unbounded in age, and invisible to `kubectl diff`.

Two live examples, both found only because someone happened to look:
`homelab-oracle` carried two seeds that appear nowhere in git, one of them
stating the opposite of the correction the git seeds exist to make;
`db-steward` was missing the three seeds added alongside the newer tools, so it
read those tools with none of the context explaining their readings.

Compares seed *text*, not counts. A matching count with different text is
exactly the case that hid the oracle's drift.

    python3 scripts/reseed_memory.py            # report drift, change nothing
    python3 scripts/reseed_memory.py --apply    # rewrite the drifted ConfigMaps

The ConfigMap has no ownerReferences and nothing reconciles it, so a direct
write sticks. It is read per run, so the next run picks it up with no restart.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

NAMESPACE = "automation"
ROOT = Path(__file__).resolve().parent.parent


def personas() -> list[tuple[str, str, list[str]]]:
    found = []
    for path in sorted(ROOT.glob("projects/*/agents/*.yaml")):
        spec = yaml.safe_load(path.read_text())
        ensemble = path.parent.parent.name
        found.append((ensemble, spec["name"], spec.get("memory", {}).get("seeds") or []))
    return found


def live_seeds(configmap: str) -> list[str] | None:
    result = subprocess.run(
        ["kubectl", "get", "cm", "-n", NAMESPACE, configmap,
         "-o", r"jsonpath={.data.MEMORY\.md}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return [line[2:].strip() for line in result.stdout.split("\n") if line.startswith("- ")]


def render(seeds: list[str]) -> str:
    return "# Memory\n\n" + "\n".join(f"- {seed}" for seed in seeds) + "\n"


def apply(configmap: str, seeds: list[str]) -> None:
    """Replace the whole ConfigMap, so a stale seed is removed and not merged."""
    body = json.dumps({
        "apiVersion": "v1", "kind": "ConfigMap",
        "metadata": {"name": configmap, "namespace": NAMESPACE},
        "data": {"MEMORY.md": render(seeds)},
    })
    subprocess.run(
        ["kubectl", "replace", "-f", "-"],
        input=body, text=True, check=True, capture_output=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the drifted ConfigMaps")
    parser.add_argument("--persona", help="limit to one persona name")
    args = parser.parse_args()

    drifted = []
    for ensemble, name, git in personas():
        if args.persona and name != args.persona:
            continue
        configmap = f"{ensemble}-{name}-memory"
        live = live_seeds(configmap)
        if live is None:
            print(f"{name:22} no ConfigMap (ensemble not installed?)")
            continue
        if [s.strip() for s in git] == live:
            print(f"{name:22} git={len(git):2} live={len(live):2} ok")
            continue
        missing = [s for s in git if s.strip() not in live]
        extra = [s for s in live if s not in [g.strip() for g in git]]
        print(f"{name:22} git={len(git):2} live={len(live):2} DRIFT "
              f"({len(missing)} missing, {len(extra)} not in git)")
        for seed in missing:
            print(f"    missing: {seed[:100]}")
        for seed in extra:
            print(f"    not in git: {seed[:100]}")
        drifted.append((configmap, git, name))

    if not drifted:
        return 0
    if not args.apply:
        print(f"\n{len(drifted)} persona(s) drifted. Re-run with --apply to repair.")
        return 1
    for configmap, seeds, name in drifted:
        apply(configmap, seeds)
        print(f"repaired {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
