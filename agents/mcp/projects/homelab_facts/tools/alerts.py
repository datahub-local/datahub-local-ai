"""`alerts_snapshot()` — what is firing, and which of it is actually news.

Two things move out of the model here.

**The diff.** "New vs still firing vs resolved" used to be the model's job:
read the alert list, read your own memory seeds, compare. It is computed here
against a stored snapshot, so it is right or it says it has no baseline.

**The chronic set.** Most alerts in this cluster fire permanently, and a 4B model
cannot deduce which. `KubeSchedulerDown` and `KubeControllerManagerDown` are k3s
artifacts - both components are embedded in the server process with no separate
metrics endpoint, so the scrape target cannot ever come up. `Watchdog` fires by
design. That set lived in memory seeds; it is `config/chronic_alerts.yaml` now,
reviewable in git and asserted by a test.

The classification is deliberately not a filter. A chronic alert still appears,
with its reason, because "the chronic set is unchanged" is a real reading and a
chronic alert that *stops* is worth seeing. `NodeClockNotSynchronising` is the
case that proves the distinction matters: it fires permanently on several nodes
*and* is genuinely broken, so it is listed under `never_suppress` and is never
folded into the chronic set however long it has been firing. Which nodes are
affected comes from the alert's own labels, never from the config file.
"""

from __future__ import annotations

from mcp_runner import render
from mcp_runner.budget import truncate_lines
from mcp_runner.prometheus import PrometheusError
from mcp_runner.state import diff_keys

from .. import settings

BUDGET = 3072
_SNAPSHOT_KEY = "alerts"

# Firing alerts only. A pending alert has not met its `for` duration and is not
# yet a condition; including them made every report longer and none of it news.
_EXPRESSION = 'ALERTS{alertstate="firing"}'


def _identity(metric: dict[str, str]) -> str:
    """A stable key per alert instance, so a diff is not confused by label order."""
    name = metric.get("alertname", "?")
    scope = (
        metric.get("pod")
        or metric.get("persistentvolumeclaim")
        or metric.get("node")
        or metric.get("instance")
        or metric.get("job")
        or metric.get("namespace")
        or "-"
    )
    return f"{name}|{scope}"


def alerts_snapshot() -> str:
    chronic = settings.chronic_alerts()
    protected = settings.never_suppress()

    try:
        series = settings.prometheus().instant(_EXPRESSION)
    except PrometheusError as exc:
        # A fleet check with no metrics is a failed check, not a clean one.
        return (
            f"ERROR: alert query failed: {exc}\n"
            "This is not 'no alerts firing' - the alert state is unknown."
        )

    instances: dict[str, dict[str, str]] = {}
    for item in series:
        metric = item.get("metric") or {}
        instances[_identity(metric)] = metric

    store = settings.snapshots()
    previous = store.load(_SNAPSHOT_KEY)
    previous_keys = set((previous or {}).get("firing") or []) if previous is not None else None
    new, continuing, resolved = diff_keys(set(instances), previous_keys)
    store.save(_SNAPSHOT_KEY, {"firing": sorted(instances)})

    lines: list[str] = []
    if not instances:
        lines.append("Nothing is firing.")
    else:
        lines.append(f"{len(instances)} alert instance(s) firing.")

    if previous is None:
        lines.append(
            "No previous snapshot: everything below is listed as newly SEEN, which "
            "is a first observation and not a fleet-wide incident."
        )

    def rows_for(keys: list[str]) -> list[list[str]]:
        rows = []
        for key in keys:
            metric = instances.get(key, {})
            name = metric.get("alertname") or key.split("|")[0]
            if name in protected:
                kind = "REAL-chronic"
            elif name in chronic:
                kind = "chronic"
            else:
                kind = "-"
            rows.append(
                [
                    name,
                    metric.get("severity", "-"),
                    key.split("|", 1)[1] if "|" in key else "-",
                    kind,
                ]
            )
        return rows

    headers = ["alert", "severity", "scope", "class"]

    def summarise(keys: list[str]) -> list[str]:
        """One line per alert *name* with a count, not one per instance.

        Ten `CPUThrottlingHigh` rows carry no more information than the count
        does, and they crowd out the section a reader actually needs. Compressing
        the repeats is what keeps this answer inside its byte budget - and a tool
        result large enough to matter is one that ends the run with no report.
        """
        grouped: dict[str, list[str]] = {}
        for key in keys:
            name = instances.get(key, {}).get("alertname") or key.split("|")[0]
            grouped.setdefault(name, []).append(
                key.split("|", 1)[1] if "|" in key else "-"
            )
        out = []
        for name, scopes in sorted(grouped.items()):
            if name in protected:
                kind = "REAL-chronic"
            elif name in chronic:
                kind = "chronic"
            else:
                kind = "-"
            if len(scopes) == 1:
                out.append(f"{name} [{kind}] on {scopes[0]}")
            else:
                out.append(f"{name} [{kind}] x{len(scopes)}: {', '.join(sorted(scopes)[:4])}"
                           + (", ..." if len(scopes) > 4 else ""))
        return out

    # Anything not on the chronic list is real news and keeps full per-instance
    # detail: this is the section the run exists to produce.
    fresh = [key for key in new if (instances.get(key, {}).get("alertname")) not in chronic]
    known = [key for key in new if key not in fresh]

    lines.append("")
    lines.append(f"## New since last run ({len(fresh)})")
    lines += render.table(headers, rows_for(fresh)) if fresh else ["(none)"]

    if known:
        lines.append("")
        lines.append(f"## Firing, on the known-chronic list ({len(known)})")
        lines.append("Listed because the baseline was lost, not because anything changed.")
        lines += summarise(known)

    lines.append("")
    lines.append(f"## Still firing ({len(continuing)})")
    lines += summarise(continuing) if continuing else ["(none)"]

    lines.append("")
    lines.append(f"## Resolved since last run ({len(resolved)})")
    lines += summarise(resolved) if resolved else ["(none)"]

    if protected:
        lines.append("")
        lines.append("## How to read the class column")
        lines.append(
            "chronic      = fires permanently for a known reason. Not news: do not "
            "investigate it, just say the chronic set is unchanged."
        )
        lines.append(
            "REAL-chronic = fires permanently AND is genuinely broken. A real "
            "finding every time, however long it has been firing."
        )
        for name, reason in sorted(protected.items()):
            lines.append(f"  {name}: {' '.join(reason.split())}")

    return truncate_lines(lines, BUDGET, unit="lines")


SCHEMA = {"type": "object", "properties": {}, "additionalProperties": False}

DESCRIPTION = """
Every firing alert, already diffed against the previous run and already
classified against the known-chronic set.

Takes no arguments. Sections are New, Still firing, and Resolved; the class
column says whether an alert is a permanent artifact of this cluster or real.
Investigate what is New and what is marked REAL-chronic. Do not re-investigate a
chronic alert, and do not suppress a REAL-chronic one.
"""
