"""`postgres_health()` and `cache_health()` — the stateful services.

`postgres_health()` exists because of one number read the wrong way.
`cnpg_pg_stat_archiver_failed_count` was called "the most important number you
look at" and never described as a counter, so a lifetime total of 2 - two
failures 5.4 days old, against a successful archive 95 seconds old and
`increase(...[24h]) = 0` - paged CRITICAL "recovery is silently broken" on every
run, twice into Slack. The window is now in the expression, built by
`increase_`, and the tool states both the increase and the age of the last
success so the two cannot be confused.

The suffix is no guide and never was: `cnpg_backends_total` and
`cnpg_backends_waiting_total` are **gauges** despite `_total`, while
`cnpg_pg_stat_archiver_failed_count` is a **counter** despite `_count`. A
suffix-based rule gets both wrong, which is why `CUMULATIVE_COUNTERS` below is an
explicit set, sourced from Prometheus's metadata API and asserted by a test.

`cache_health()` reports used bytes and evictions and computes no percentage.
This Valkey has **no ceiling**: `maxmemory` is unset, which the exporter
publishes as `redis_memory_max_bytes` = 0, and the container has no memory limit
either. Dividing by that zero produced "unable to determine" every run, forever.
There is nothing to determine, so the tool says so once instead.
"""

from __future__ import annotations

from mcp_runner import render
from mcp_runner.budget import truncate_lines
from mcp_runner.prometheus import PrometheusError, increase_

from .. import settings

BUDGET = 3072

# Read from Prometheus's metadata API on 2026-08-25, not inferred from names.
# Anything here must be read through a window; anything absent is a gauge.
CUMULATIVE_COUNTERS = frozenset(
    {
        "cnpg_pg_stat_archiver_failed_count",
        "redis_evicted_keys_total",
        "node_edac_correctable_errors_total",
        "node_edac_uncorrectable_errors_total",
        "node_pressure_io_stalled_seconds_total",
        "node_pressure_cpu_waiting_seconds_total",
        "node_pressure_memory_stalled_seconds_total",
        "node_disk_io_time_seconds_total",
    }
)

# Gauges whose `_total` suffix invites exactly the wrong reading.
GAUGES_LOOKING_LIKE_COUNTERS = frozenset({"cnpg_backends_total", "cnpg_backends_waiting_total"})


def postgres_health() -> str:
    prometheus = settings.prometheus()
    limits = settings.thresholds("postgres")

    archiver_window = "1h"
    failed = prometheus.try_scalar_by(
        increase_("cnpg_pg_stat_archiver_failed_count", archiver_window), "namespace"
    )
    last_archive_age = prometheus.try_scalar_by(
        "time() - cnpg_pg_stat_archiver_last_archived_time", "namespace"
    )
    backends = prometheus.try_scalar_by("sum by (namespace) (cnpg_backends_total)", "namespace")
    waiting = prometheus.try_scalar_by(
        "sum by (namespace) (cnpg_backends_waiting_total)", "namespace"
    )

    lines: list[str] = ["## WAL archiving"]

    if not failed and not last_archive_age:
        lines.append(
            "unavailable - the cnpg archiver metrics answered nothing. That is an "
            "unknown archiving state, not a healthy one."
        )
    else:
        stale_warn = float(limits.get("archiver_stale_warn_seconds", 3600))
        fail_warn = float(limits.get("archiver_failure_increase_warn", 1))
        for namespace in sorted(set(failed) | set(last_archive_age)):
            increase = failed.get(namespace)
            age = last_archive_age.get(namespace)
            verdict = _archiver_verdict(increase, age, fail_warn, stale_warn)
            lines.append(
                f"{namespace}: {render.number(increase, 0)} failed attempt(s) in the last "
                f"{archiver_window}; last success "
                f"{render.number(age / 60 if age is not None else None, 1, 'm')} ago. {verdict}"
            )
        lines.append(
            "The figure above is an INCREASE over a window, not a lifetime total. A "
            "non-zero lifetime count with a zero increase is healthy: the counter "
            "only ever rises and never describes the state now."
        )

    lines.append("")
    lines.append("## Connections")
    if not backends:
        lines.append("unavailable - cnpg_backends_total answered nothing.")
    else:
        rows = [
            [
                namespace,
                render.number(backends.get(namespace), 0),
                render.number(waiting.get(namespace), 0),
            ]
            for namespace in sorted(backends)
        ]
        lines += render.table(["namespace", "backends", "waiting"], rows)
        lines.append(
            "Both are gauges - current counts - despite the _total suffix. Do not "
            "take a rate or an increase of them."
        )

    lines.append("")
    lines.append("## Database sizes")
    try:
        sizes = prometheus.instant("cnpg_pg_database_size_bytes")
    except PrometheusError as exc:
        sizes = []
        lines.append(f"unavailable - {exc}")
    if sizes:
        rows = []
        for item in sizes:
            metric = item.get("metric") or {}
            try:
                value = float(item["value"][1])
            except (KeyError, IndexError, TypeError, ValueError):
                continue
            rows.append(
                [
                    metric.get("namespace", "-"),
                    metric.get("datname") or metric.get("database", "-"),
                    render.bytes_human(value),
                ]
            )
        rows.sort(key=lambda row: row[1])
        lines += render.table(["namespace", "database", "size"], rows)
    elif not sizes:
        lines.append("(no rows)")

    lines.append("")
    lines.append("## Cluster objects")
    lines += _cnpg_clusters()

    lines.append("")
    lines.append(
        "Query-level analysis - index health, bloat, vacuum state, slow queries - "
        "is not here. Use the postgres MCP tools for that; this tool reports only "
        "what the operator exports, which needs no database credential."
    )
    return truncate_lines(lines, BUDGET, unit="lines")


def _archiver_verdict(
    increase: float | None, age_seconds: float | None, fail_warn: float, stale_warn: float
) -> str:
    """The whole point of this tool, in one function a test can pin.

    A non-zero *increase* is the failure. A stale last-success is the other
    failure. A lifetime total is neither, and cannot reach this function.
    """
    if increase is None and age_seconds is None:
        return "unavailable."
    if increase is not None and increase >= fail_warn:
        return "CRITICAL: archiving is failing now."
    if age_seconds is not None and age_seconds >= stale_warn:
        return f"WARN: no successful archive for {age_seconds / 3600:.1f}h."
    return "Healthy."


def _cnpg_clusters() -> list[str]:
    objects = settings.kube().list("postgresql.cnpg.io/v1", "Cluster")
    if not objects:
        return ["unavailable - no CloudNativePG Cluster objects readable."]
    rows = []
    for obj in objects:
        metadata = obj.get("metadata") or {}
        status = obj.get("status") or {}
        rows.append(
            [
                f"{metadata.get('namespace')}/{metadata.get('name')}",
                str((obj.get("spec") or {}).get("instances", "-")),
                str(status.get("readyInstances", "-")),
                str(status.get("phase", "-")),
            ]
        )
    return render.table(["cluster", "want", "ready", "phase"], rows)


def cache_health() -> str:
    prometheus = settings.prometheus()
    limits = settings.thresholds("cache")

    used = prometheus.try_scalar_by("sum by (job) (redis_memory_used_bytes)", "job")
    maximum = prometheus.try_scalar_by("sum by (job) (redis_memory_max_bytes)", "job")
    evicted = prometheus.try_scalar_by(
        f"sum by (job) ({increase_('redis_evicted_keys_total', '1h')})", "job"
    )
    up = prometheus.try_scalar_by("sum by (job) (redis_up)", "job")

    if not used and not up:
        return (
            "unavailable - no redis_* series answered. Valkey is scraped by a redis "
            "exporter, so its metrics are named redis_* and never valkey_*; an empty "
            "answer here is an unknown state, not a healthy one."
        )

    eviction_warn = float(limits.get("eviction_increase_warn", 1))
    lines = ["## Valkey (scraped by a redis exporter, so the metrics are redis_*)"]
    rows = []
    for job in sorted(set(used) | set(up)):
        rows.append(
            [
                job,
                "up" if (up.get(job) or 0) >= 1 else "DOWN",
                render.bytes_human(used.get(job)),
                render.number(evicted.get(job), 0),
            ]
        )
    lines += render.table(["job", "state", "used", "evicted/1h"], rows)

    ceiling = next((value for value in maximum.values() if value), None)
    if ceiling:
        lines.append(f"maxmemory is set to {render.bytes_human(ceiling)}.")
    else:
        lines.append(
            "maxmemory is UNSET (redis_memory_max_bytes = 0) and the container has no "
            "memory limit, so there is no percentage to compute and none should be "
            "reported. Evictions are the direct measurement of what a ceiling would "
            "have told you."
        )
        lines.append(
            "That an unbounded cache grows until the node runs out of memory is worth "
            "saying once as a suggestion to set maxmemory. It is not a daily finding "
            "and is never CRITICAL on its own."
        )

    hot = [job for job, value in evicted.items() if value >= eviction_warn]
    lines.append(
        f"Evictions in the last hour on: {', '.join(sorted(hot))} - a cache dropping "
        "data now, which is a correctness problem for whatever depends on it."
        if hot
        else "No evictions in the last hour. A non-zero lifetime total with a zero "
        "increase is not a finding."
    )
    return truncate_lines(lines, BUDGET, unit="lines")


POSTGRES_SCHEMA = {"type": "object", "properties": {}, "additionalProperties": False}
CACHE_SCHEMA = {"type": "object", "properties": {}, "additionalProperties": False}

POSTGRES_DESCRIPTION = """
PostgreSQL operational state from the CloudNativePG operator: WAL archiving,
connections, database sizes and cluster objects.

Takes no arguments. The archiver figure is already an increase over a window and
already carries its verdict - a non-zero lifetime total with a zero increase is
healthy, and this tool will not show you the lifetime total to misread.
"""

CACHE_DESCRIPTION = """
Valkey state: whether it is up, how much memory it is using, and evictions in the
last hour.

Takes no arguments. There is no memory ceiling configured on this instance, so
there is no percentage to report - do not compute one.
"""
