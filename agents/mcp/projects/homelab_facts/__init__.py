"""homelab_facts — deterministic readings of this homelab, one call per section.

The point of this project is that **code gathers and the model writes**. Every
failure in the fleet this replaces was a tool-loop failure: a 4B model was made a
careful API client, asked to assemble `100*(1-avail/cap)` with a `group_left`
join, to remember that `increase(m[1h])` is not `m[1h]`, to diff alerts against
its own memory, and to know that orpi-0's kernel is not drift. Each incident
added a paragraph to a prompt and a regex to a validator, and it did not
converge.

The tools here are "fat" in calls and thin in bytes: one call per report section,
each answer bounded and truncated in code, each absence stated as `unavailable`
rather than left for a mandatory report format to fill with an invented number.

They do not replace reach. Every persona keeps the raw `k8s_*` and Prometheus
tools for following up on whatever these surface. The win is budget
reallocation - the mandatory readings drop from eight-plus calls to one or two,
leaving the iteration budget for real investigation, which is exactly where the
last run before teardown ran out and drifted.
"""

from __future__ import annotations

from mcp_runner.server import Registry

from .tools import alerts, databases, gitops, lifecycle, nodes, raw, volumes


def register(registry: Registry) -> None:
    registry.add(
        "alerts_snapshot",
        alerts.DESCRIPTION,
        alerts.alerts_snapshot,
        schema=alerts.SCHEMA,
        budget=alerts.BUDGET,
    )
    registry.add(
        "node_fleet",
        nodes.DESCRIPTION,
        nodes.node_fleet,
        schema=nodes.SCHEMA,
        budget=nodes.BUDGET,
    )
    registry.add(
        "volume_fill",
        volumes.DESCRIPTION,
        volumes.volume_fill,
        schema=volumes.SCHEMA,
        budget=volumes.BUDGET,
    )
    registry.add(
        "postgres_health",
        databases.POSTGRES_DESCRIPTION,
        databases.postgres_health,
        schema=databases.POSTGRES_SCHEMA,
        budget=databases.BUDGET,
    )
    registry.add(
        "cache_health",
        databases.CACHE_DESCRIPTION,
        databases.cache_health,
        schema=databases.CACHE_SCHEMA,
        budget=databases.BUDGET,
    )
    registry.add(
        "cert_expiry",
        lifecycle.CERT_DESCRIPTION,
        lifecycle.cert_expiry,
        schema=lifecycle.CERT_SCHEMA,
        budget=lifecycle.BUDGET,
    )
    registry.add(
        "backup_freshness",
        lifecycle.BACKUP_DESCRIPTION,
        lifecycle.backup_freshness,
        schema=lifecycle.BACKUP_SCHEMA,
        budget=lifecycle.BUDGET,
    )
    registry.add(
        "argocd_drift",
        gitops.DESCRIPTION,
        gitops.argocd_drift,
        schema=gitops.SCHEMA,
        budget=gitops.BUDGET,
    )
    registry.add(
        "promql",
        raw.DESCRIPTION,
        raw.promql,
        schema=raw.SCHEMA,
        budget=raw.BUDGET,
    )
