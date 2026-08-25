"""`argocd_drift()` — ArgoCD application state, read from the CRs.

Read from `Application` custom resources through the Kubernetes API rather than
the ArgoCD REST API, which means this server needs no ArgoCD token: the sync and
health status live in `status.sync.status` and `status.health.status` on the
object itself.

It is also deliberately *not* the resource tree. `argocd_get_application_resource_tree`
returns every object an application owns and accounted for roughly 16 KB on its
own; the run that called it made four calls for 24,126 result bytes and produced
`terminal turn had empty text`, delivering "The run finished but produced no
text" to Slack. Its own run four hours earlier made five calls for 8,483 bytes
and wrote a normal report. So this tool returns one row per application and names
the degraded resources only for applications that are actually degraded.

The consecutive-run count is the other half. "Out of sync for the third day
running" used to require the model to remember; it is computed here against a
stored snapshot, so a persistent drift escalates on its own.
"""

from __future__ import annotations

from mcp_runner import render
from mcp_runner.budget import truncate_lines

from .. import settings

BUDGET = 2560
_SNAPSHOT_KEY = "argocd_drift"

_HEALTHY = "Healthy"
_SYNCED = "Synced"

# Resources named per degraded application. Enough to point at the problem,
# bounded so a badly broken application cannot blow the budget.
_MAX_RESOURCES = 6


def argocd_drift() -> str:
    objects = settings.kube().list("argoproj.io/v1alpha1", "Application")
    if not objects:
        return (
            "unavailable - no ArgoCD Application objects readable. That is an unknown "
            "GitOps state, not a synced one."
        )

    store = settings.snapshots()
    previous = store.load(_SNAPSHOT_KEY) or {}
    previous_streak: dict[str, int] = previous.get("streak") or {}

    rows = []
    streak: dict[str, int] = {}
    problems: list[str] = []

    for obj in objects:
        metadata = obj.get("metadata") or {}
        status = obj.get("status") or {}
        name = metadata.get("name") or "?"
        sync = ((status.get("sync") or {}).get("status")) or "Unknown"
        health = ((status.get("health") or {}).get("status")) or "Unknown"
        unhealthy = sync != _SYNCED or health != _HEALTHY

        if unhealthy:
            streak[name] = previous_streak.get(name, 0) + 1
        run_count = streak.get(name, 0)

        rows.append(
            [
                name,
                sync,
                health,
                str(run_count) if run_count else "-",
            ]
        )

        if unhealthy:
            problems.extend(_degraded_resources(name, status))

    store.save(_SNAPSHOT_KEY, {"streak": streak})

    drifted = [row for row in rows if row[1] != _SYNCED or row[2] != _HEALTHY]
    lines = [
        f"{len(objects)} ArgoCD application(s); {len(drifted)} not Synced+Healthy.",
    ]
    if not previous:
        lines.append(
            "No previous snapshot, so the 'runs' column starts at 1 for anything "
            "drifting now - a first observation, not a one-run-old problem."
        )
    lines += render.table(["application", "sync", "health", "runs drifted"], rows)

    if problems:
        lines.append("")
        lines.append("## Degraded resources")
        lines += problems
    elif drifted:
        lines.append("")
        lines.append(
            "No individual resource is reported unhealthy, so the drift is a "
            "manifest difference rather than a failing object."
        )

    lines.append("")
    lines.append(
        "The 'runs drifted' column counts consecutive runs in this state. It is "
        "computed from a stored snapshot, so it is a measurement, not a recollection."
    )
    lines.append(
        "This is the application summary, not the resource tree. The tree runs to "
        "~16 KB and a result that large ends a run with no report at all."
    )
    return truncate_lines(lines, BUDGET, unit="lines")


def _degraded_resources(app: str, status: dict) -> list[str]:
    """Name the unhealthy resources of one application, bounded."""
    out = []
    for resource in status.get("resources") or []:
        health = (resource.get("health") or {}).get("status")
        sync = resource.get("status")
        if health in (None, _HEALTHY) and sync in (None, _SYNCED):
            continue
        out.append(
            f"{app}: {resource.get('kind', '?')}/{resource.get('name', '?')} "
            f"sync={sync or '-'} health={health or '-'}"
        )
        if len(out) >= _MAX_RESOURCES:
            out.append(f"{app}: ... more resources not listed.")
            break
    return out


SCHEMA = {"type": "object", "properties": {}, "additionalProperties": False}

DESCRIPTION = """
Every ArgoCD application's sync and health state, plus how many consecutive runs
each has been drifting.

Takes no arguments. Degraded resources are named for the applications that have
them. This is the summary, not the resource tree.
"""
