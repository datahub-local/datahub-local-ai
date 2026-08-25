"""`volume_fill()` — percent USED per PVC, correct by construction.

Three separate mistakes are removed here, all of which reached Slack:

**The inversion.** `available / capacity` is the fraction *free*. The prompt that
asked for fill got the ratio and flagged anything above 80%, so it flagged the
emptiest volumes and could never flag a full one: it called a 2%-used volume
"97.9% full, write operations failing" on every run for days. Because a non-empty
"Filling up" section was itself a change condition, it also forced a Slack post
every time. The expression here is built by `used_percent`, which cannot be
written the other way round.

**The missing join.** All five `nfs` PVCs report the same shared 1.9 TB capacity,
so a per-volume percentage there is the share's fill repeated once per claim. The
`group_left` join onto `kube_persistentvolumeclaim_info` restricts the answer to
the storage classes where a percentage means something.

**The remembered trend.** "Climbed since your last run" used to depend on the
model reading its own memory. It is computed here against a stored snapshot.
"""

from __future__ import annotations

from mcp_runner import render
from mcp_runner.budget import truncate_lines
from mcp_runner.prometheus import PrometheusError, used_percent

from .. import settings

BUDGET = 2560
_SNAPSHOT_KEY = "volume_fill"


def build_expression(storage_classes: list[str]) -> str:
    """The one expression this tool sends, assembled from the pieces.

    Kept separate so a test can assert its shape without a Prometheus: the
    inversion and the join are the two things that must never regress.
    """
    pattern = "|".join(storage_classes)
    return (
        used_percent("kubelet_volume_stats_available_bytes", "kubelet_volume_stats_capacity_bytes")
        + " * on(namespace, persistentvolumeclaim) group_left(storageclass)"
        + f' (kube_persistentvolumeclaim_info{{storageclass=~"{pattern}"}} > 0)'
    )


def volume_fill() -> str:
    limits = settings.thresholds("volumes")
    classes = limits.get("storage_classes") or ["longhorn", "longhorn-no-replica"]
    warn = float(limits.get("warn_percent", 70))
    critical = float(limits.get("critical_percent", 80))

    expression = build_expression(classes)
    try:
        series = settings.prometheus().instant(expression)
    except PrometheusError as exc:
        return f"ERROR: volume query failed: {exc}"

    current: dict[str, float] = {}
    for item in series:
        metric = item.get("metric") or {}
        namespace = metric.get("namespace")
        claim = metric.get("persistentvolumeclaim")
        if not namespace or not claim:
            continue
        try:
            current[f"{namespace}/{claim}"] = float(item["value"][1])
        except (KeyError, IndexError, TypeError, ValueError):
            continue

    if not current:
        return (
            "No volumes matched. Storage classes queried: "
            + ", ".join(classes)
            + "\nThis is an empty result, not a fleet with no storage - treat it as "
            "unavailable rather than as healthy."
        )

    store = settings.snapshots()
    previous = store.load(_SNAPSHOT_KEY)
    previous_values: dict[str, float] = (previous or {}).get("values") or {}

    rows = []
    findings = 0
    for name in sorted(current, key=lambda key: -current[key]):
        percent = current[name]
        was = previous_values.get(name)
        delta = render.number(percent - was, 1, "pp") if was is not None else "first"
        if percent >= critical:
            state = "CRITICAL"
            findings += 1
        elif percent >= warn:
            state = "warn"
            findings += 1
        else:
            state = "ok"
        rows.append([name, render.number(percent, 1, "%"), delta, state])

    store.save(_SNAPSHOT_KEY, {"values": current})

    lines = [
        f"Volume fill, percent USED, {len(current)} claims on "
        + "/".join(classes)
        + f". warn>={warn:.0f}% critical>={critical:.0f}%.",
    ]
    if previous is None:
        lines.append(
            "No previous snapshot, so the change column reads 'first' - this is a "
            "first observation, not a fleet that has not moved."
        )
    lines.append(
        f"{findings} claim(s) at or above the warn threshold."
        if findings
        else "No claim is at or above the warn threshold."
    )
    lines += render.table(["claim", "used", "change", "state"], rows)
    lines.append(
        "Storage classes outside the list above are excluded on purpose: the nfs "
        "claims all report one shared capacity, so a per-volume percentage there "
        "is the share's fill repeated once per claim."
    )
    return truncate_lines(lines, BUDGET, unit="claims")


SCHEMA = {"type": "object", "properties": {}, "additionalProperties": False}

DESCRIPTION = """
Percent USED for every PersistentVolumeClaim worth measuring, with how much each
moved since the last run.

Takes no arguments. The percentage is already the used fraction, already joined
to the storage class, and already restricted to the classes where a per-volume
percentage is meaningful. Report the numbers as given - there is nothing to
invert, divide or filter.
"""
