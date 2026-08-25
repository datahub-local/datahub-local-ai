"""`node_fleet()` — the whole node table, with machine identity attached in code.

**No `node_*` series in this Prometheus carries a machine name.** They are keyed
by `instance` (an IP and a port); the only hostname anywhere is the `nodename`
label on `node_uname_info`. The old prompt demanded a per-node table and never
said how to bridge that, so the model improvised - it wrote
`node_apt_security_upgrades_pending by (node)`, which is neither valid PromQL nor
an existing label, on four different metrics, and elsewhere queried the bare
metric and guessed the IP mapping. The 2026-08-24 13:25 table was wrong in five
ways at once: four rows read `unavailable` when every figure was available, the
NAS was given amd-1's disk percentage, orpi-1 got roughly orpi-3's, every uptime
was wrong by two orders of magnitude, three ARM nodes with 5 pending security
updates were reported as having none, and the single finding named amd-1's CPU
pressure at 52.7% against a real 0.47%.

Every expression below carries the join, built by `by_nodename` so it cannot be
dropped. Three further rules are enforced here rather than asked for.

**Nothing about this homelab is written down.** The node inventory is the
Kubernetes node list, hardware classes are derived from the kernel tree and
architecture, and which node has SMART, EDAC or a UPS is decided by whether the
sensor answered. Adding, renaming or re-disking a machine needs no change here.
See `mcp_runner.fleet`.

**`unavailable` and `n/a` mean different things.** `unavailable` is *the query
gave no value for this node although it should have*; `n/a` is *this node has no
such sensor*. Absence needs a definition or it absorbs every bug - `unavailable`
was introduced so a missing metric could be stated rather than invented, which
was right, and it then silently absorbed a broken join.

**Versions compare within a hardware class only.** A class of one is never the
odd one out. orpi-0 was reported as kernel drift against orpi-1/2/3 every run for
days: different SoC families cannot converge, so the finding could never be
actioned and never cleared, and because a non-empty findings section was itself a
change condition it forced a Slack post each time.
"""

from __future__ import annotations

import logging

from mcp_runner import fleet, render
from mcp_runner.budget import truncate_lines
from mcp_runner.prometheus import (
    UNAVAILABLE,
    Reading,
    by_nodename,
    increase_,
    rate_percent,
    used_percent,
)

from .. import settings

logger = logging.getLogger(__name__)

BUDGET = 3584
_NOT_APPLICABLE = "n/a"

# Every reading, with the join already applied. Verified against this Prometheus
# on 2026-08-25.
_QUERIES: dict[str, str] = {
    "disk_pct": by_nodename(
        used_percent(
            "node_filesystem_avail_bytes",
            "node_filesystem_size_bytes",
            '{fstype!~"tmpfs|overlay|ramfs"}',
        )
    ),
    "io_stall_pct": by_nodename(rate_percent("node_pressure_io_stalled_seconds_total")),
    "cpu_stall_pct": by_nodename(rate_percent("node_pressure_cpu_waiting_seconds_total")),
    "mem_stall_pct": by_nodename(rate_percent("node_pressure_memory_stalled_seconds_total")),
    "io_busy_pct": by_nodename(rate_percent("node_disk_io_time_seconds_total")),
    # node_hwmon_temp_celsius covers every node; smartmon_temperature_celcius
    # covers only those with reporting drives. The old prompt named both without
    # saying which was the Temp column, so the table inherited SMART's coverage
    # gap for no reason.
    "temp_c": by_nodename("node_hwmon_temp_celsius"),
    "temp_crit": by_nodename("node_hwmon_temp_crit_alarm_celsius"),
    "uptime_d": by_nodename("(time() - node_boot_time_seconds) / 86400"),
    "apt_security": by_nodename("node_apt_security_upgrades_pending"),
    "apt_total": by_nodename("node_apt_upgrades_pending"),
    "reboot_required": by_nodename("node_reboot_required"),
    "apt_cache_age_d": by_nodename("(time() - node_apt_package_cache_timestamp_seconds) / 86400"),
    "systemd_ok": by_nodename("node_systemd_system_running"),
}

# Readings that exist only where the hardware does. Each is paired with the probe
# that decides, per node, whether the sensor is there at all — so a gap is `n/a`
# rather than a finding, without a list of which machines have what.
_SCOPED: dict[str, tuple[str, str, str]] = {
    # (expression, capability probe, aggregator)
    "smart_healthy": (
        by_nodename("smartmon_device_smart_healthy", "min"),
        # 0 means the device cannot report health at all. A node whose drives all
        # report 0 gets no health verdict, because that is the hardware.
        by_nodename("smartmon_device_smart_available", "max"),
        "min",
    ),
    "smart_temp_c": (
        by_nodename("smartmon_temperature_celcius"),
        by_nodename("smartmon_device_smart_available", "max"),
        "max",
    ),
    "edac_corr": (
        by_nodename(increase_("node_edac_correctable_errors_total", "24h")),
        by_nodename("node_edac_correctable_errors_total"),
        "max",
    ),
    "edac_uncorr": (
        by_nodename(increase_("node_edac_uncorrectable_errors_total", "24h")),
        by_nodename("node_edac_uncorrectable_errors_total"),
        "max",
    ),
}

_UPS_QUERIES = {
    "charge": by_nodename("network_ups_tools_battery_charge"),
    "runtime_s": by_nodename("network_ups_tools_battery_runtime"),
    "input_v": by_nodename("network_ups_tools_input_voltage"),
}


def node_fleet() -> str:
    prometheus = settings.prometheus()
    limits = settings.thresholds("nodes")

    readings: dict[str, Reading] = {
        key: prometheus.reading(expression, "nodename") for key, expression in _QUERIES.items()
    }

    scoped: dict[str, tuple[Reading, set[str]]] = {}
    for key, (expression, probe, _aggregator) in _SCOPED.items():
        value = prometheus.reading(expression, "nodename")
        capability = prometheus.reading(probe, "nodename")
        # Capable = the probe answered a non-zero value for that node. A zero is
        # an explicit "this device cannot report", not a missing series.
        capable = {node for node, level in capability.values.items() if level and level > 0}
        scoped[key] = (value, capable)

    kernels, machines = _identity(prometheus)

    # Kubernetes is the authority on which machines exist; Prometheus says which
    # answered. The difference is what makes a dropped join legible.
    try:
        expected = settings.kube().node_names()
    except Exception as exc:  # noqa: BLE001 - unreachable API must not lose metrics
        logger.warning("node list unavailable, expected set is empty: %s", exc)
        expected = []

    observed: set[str] = set(kernels)
    for reading in readings.values():
        observed |= reading.covered()
    nodes = sorted(set(expected) | observed)
    if not nodes:
        return (
            "ERROR: no node answered any query and the Kubernetes node list was "
            "unreadable. This is an unknown fleet, not a healthy one."
        )

    prefix = fleet.common_prefix(nodes)

    def cell(key: str, node: str, digits: int = 1, suffix: str = "") -> str:
        reading = readings[key]
        if not reading.ok:
            return UNAVAILABLE
        return render.number(reading.values.get(node), digits, suffix)

    def scoped_cell(key: str, node: str, digits: int = 1, suffix: str = "") -> str:
        reading, capable = scoped[key]
        if not reading.ok:
            return UNAVAILABLE
        if node not in capable:
            return _NOT_APPLICABLE
        return render.number(reading.values.get(node), digits, suffix)

    rows = []
    for node in nodes:
        release = kernels.get(node, "")
        rows.append(
            [
                fleet.shorten(node, prefix),
                fleet.kernel_flavour(release) if release else UNAVAILABLE,
                cell("disk_pct", node, 1, "%"),
                cell("io_stall_pct", node, 2, "%"),
                cell("cpu_stall_pct", node, 2, "%"),
                cell("temp_c", node, 1),
                scoped_cell("smart_temp_c", node, 1),
                cell("uptime_d", node, 1, "d"),
                cell("apt_security", node, 0),
                cell("apt_total", node, 0),
                fleet.kernel_version(release) or UNAVAILABLE,
            ]
        )

    lines = [
        (
            f"Node fleet, {len(nodes)} nodes. Every figure is joined to the machine "
            "name in the query; no column is borrowed from another metric."
        ),
        (
            "'unavailable' = the query gave no value for this node. 'n/a' = this node "
            "has no such sensor, which is the hardware and not a finding."
        ),
        "",
    ]
    lines += render.table(
        [
            "node",
            "class",
            "disk",
            "iostall",
            "cpustall",
            "temp",
            "smart",
            "uptime",
            "sec-upd",
            "upd",
            "kernel",
        ],
        rows,
    )

    missing_from_metrics = [node for node in expected if node not in observed]
    if missing_from_metrics:
        lines.append(
            "In the Kubernetes node list but absent from every metric: "
            + ", ".join(fleet.shorten(node, prefix) for node in missing_from_metrics)
            + ". Either node-exporter is not running there or the join is broken - "
            "scattered absences almost always mean the join, not the hardware."
        )

    lines.append("")
    lines.append("## Readings that need a note")
    lines += _notes(readings, scoped, nodes, limits, prefix)

    lines.append("")
    lines.append("## Power")
    lines += _power(prometheus, prefix)

    lines.append("")
    lines.append("## Kernel comparison, within hardware class only")
    lines += _kernel_drift(kernels, machines, prefix)

    return truncate_lines(lines, BUDGET, unit="lines")


def _identity(prometheus) -> tuple[dict[str, str], dict[str, str]]:
    """``({node: kernel release}, {node: architecture})`` from the identity metric."""
    kernels: dict[str, str] = {}
    machines: dict[str, str] = {}
    try:
        for item in prometheus.instant("node_uname_info"):
            metric = item.get("metric") or {}
            name = metric.get("nodename")
            if name:
                kernels[name] = metric.get("release", "")
                machines[name] = metric.get("machine", "")
    except Exception as exc:  # noqa: BLE001 - any client error means no identity
        # Not silent: without identity every row loses its class and kernel, and a
        # reader needs to know that happened rather than seeing a blank column.
        logger.warning("node identity query failed, classes unavailable: %s", exc)
    return kernels, machines


def _notes(readings, scoped, nodes, limits, prefix) -> list[str]:
    """Only the readings outside a threshold, or missing where they should not be."""
    notes: list[str] = []

    disk_crit = float(limits.get("disk_critical_percent", 85))
    disk_warn = float(limits.get("disk_warn_percent", 70))
    io_warn = float(limits.get("io_stall_warn_percent", 10))
    cpu_warn = float(limits.get("cpu_stall_warn_percent", 40))
    temp_warn = float(limits.get("temperature_warn_celsius", 75))
    cache_stale = float(limits.get("apt_cache_stale_days", 7))

    def value(key: str, node: str) -> float | None:
        reading = readings[key]
        return reading.values.get(node) if reading.ok else None

    for node in nodes:
        short = fleet.shorten(node, prefix)

        disk = value("disk_pct", node)
        if disk is not None and disk >= disk_warn:
            level = "CRITICAL" if disk >= disk_crit else "warn"
            notes.append(f"{short}: disk {disk:.1f}% used ({level}, threshold {disk_warn:.0f}%).")
        io = value("io_stall_pct", node)
        if io is not None and io >= io_warn:
            notes.append(
                f"{short}: IO stall {io:.2f}% of the last 5m (threshold {io_warn:.0f}%). "
                "Sustained IO stall is the classic overloaded-or-dying-disk symptom."
            )
        cpu = value("cpu_stall_pct", node)
        if cpu is not None and cpu >= cpu_warn:
            notes.append(
                f"{short}: CPU stall {cpu:.2f}% of the last 5m (threshold {cpu_warn:.0f}%)."
            )
        temp = value("temp_c", node)
        if temp is not None and temp >= temp_warn:
            notes.append(f"{short}: {temp:.1f}C (threshold {temp_warn:.0f}C).")
        if value("temp_crit", node):
            notes.append(f"{short}: hwmon critical temperature alarm is SET.")
        if value("reboot_required", node):
            notes.append(
                f"{short}: reboot required - a patch is installed but not running, "
                "which is the worst of both states."
            )
        cache_age = value("apt_cache_age_d", node)
        if cache_age is not None and cache_age >= cache_stale:
            notes.append(
                f"{short}: apt cache is {cache_age:.0f}d old, so its update counts are "
                "stale - a 0 there is meaningless rather than good."
            )
        running = value("systemd_ok", node)
        if running is not None and running < 1:
            notes.append(f"{short}: systemd reports the system degraded.")

        healthy, smart_capable = scoped["smart_healthy"]
        if healthy.ok and node in smart_capable:
            level = healthy.values.get(node)
            if level is not None and level < 1:
                notes.append(f"{short}: SMART reports a drive FAILING.")
        uncorr, edac_capable = scoped["edac_uncorr"]
        if uncorr.ok and node in edac_capable and uncorr.values.get(node):
            notes.append(
                f"{short}: {uncorr.values[node]:.0f} uncorrectable memory error(s) in "
                "24h - serious immediately."
            )
        corr, corr_capable = scoped["edac_corr"]
        if corr.ok and node in corr_capable and corr.values.get(node):
            notes.append(
                f"{short}: {corr.values[node]:.0f} correctable memory error(s) in 24h - "
                "failing RAM announcing itself early."
            )

    broken = sorted(key for key, reading in readings.items() if not reading.ok)
    if broken:
        notes.append(
            "Queries that FAILED, so those columns are unknown fleet-wide: "
            + ", ".join(broken)
            + ". A fleet check with no metrics is a failed check, not a clean one."
        )

    return notes or ["Nothing outside a threshold."]


def _power(prometheus, prefix: str) -> list[str]:
    """UPS state, on whichever node has one. No UPS anywhere is not a finding."""
    readings = {
        key: prometheus.reading(expression, "nodename")
        for key, expression in _UPS_QUERIES.items()
    }
    if any(not reading.ok for reading in readings.values()):
        return ["unavailable - a UPS query failed, so power state is unknown."]

    hosts = sorted(set().union(*(reading.covered() for reading in readings.values())))
    if not hosts:
        return [
            (
                "No UPS is reported anywhere in this fleet. network_ups_tools_* has no "
                "series, so no monitored UPS is present - not that one is failing."
            )
        ]

    lines = []
    for host in hosts:
        charge = readings["charge"].values.get(host)
        runtime = readings["runtime_s"].values.get(host)
        volts = readings["input_v"].values.get(host)
        state = "on mains" if volts and volts > 0 else "ON BATTERY or input lost"
        lines.append(
            f"{fleet.shorten(host, prefix)}: charge {render.number(charge, 0, '%')}, "
            f"runtime {render.number(runtime / 60 if runtime is not None else None, 0, 'm')}, "
            f"input {render.number(volts, 1, 'V')} - {state}."
        )
    lines.append(
        "A UPS on battery, or a runtime estimate that has collapsed, matters more "
        "than anything else in this report."
    )
    return lines


def _kernel_drift(kernels: dict[str, str], machines: dict[str, str], prefix: str) -> list[str]:
    """Report a node trailing its own class. A class of one is never a finding."""
    if not kernels:
        return [f"Kernel versions {UNAVAILABLE} - node_uname_info answered nothing."]

    lines: list[str] = []
    for group, members, behind in fleet.kernel_drift(kernels, machines):
        names = ", ".join(fleet.shorten(node, prefix) for node in members)
        if len(members) == 1:
            lines.append(
                f"{group}: one node ({names}) on {fleet.kernel_version(kernels[members[0]])} - "
                "a class of one has nothing to compare and is never drift."
            )
        elif not behind:
            lines.append(
                f"{group}: all {len(members)} nodes ({names}) on "
                f"{fleet.kernel_version(kernels[members[0]])} - no drift."
            )
        else:
            detail = ", ".join(
                f"{fleet.shorten(node, prefix)}={fleet.kernel_version(kernels[node])}"
                for node in sorted(members)
            )
            lines.append(
                f"{group}: DRIFT within class - "
                f"{', '.join(fleet.shorten(node, prefix) for node in behind)} behind. {detail}."
            )
    lines.append(
        "A class is one kernel tree on one architecture, derived from the running "
        "kernels rather than configured. Nodes in different classes run different "
        "silicon and can never converge, so a version difference between them is "
        "not drift and can never be actioned."
    )
    return lines


SCHEMA = {"type": "object", "properties": {}, "additionalProperties": False}

DESCRIPTION = """
The whole node hardware table in one call: disk fill, stall percentages,
temperature, SMART, uptime, pending updates, kernel and UPS state, per machine.

Takes no arguments. Every figure is already joined to the machine name and comes
from the metric named for it. 'unavailable' means the query gave no value;
'n/a' means the node has no such sensor and is not a finding. Kernel drift is
already computed within hardware class - report only what it names.
"""
