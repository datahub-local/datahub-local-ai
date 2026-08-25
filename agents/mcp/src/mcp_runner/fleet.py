"""Deriving the fleet's shape from the fleet, rather than from a config file.

An earlier version of this server carried a `hardware_classes.yaml` naming all
seven machines, which class each belonged to, and which of them had SMART, EDAC
and a UPS. That was a second copy of the cluster: rename a node, add one, or move
a disk and the file goes stale silently -- and a stale node list produces exactly
the failure this server exists to prevent, a row of `unavailable` for a machine
whose figures were available all along.

Everything that file held is readable from the cluster:

- **Class** is the kernel *flavour* plus the architecture, and that is not an
  approximation of the rule -- it **is** the rule. Kernels are comparable only
  where they come from the same tree, so "same flavour" and "comparable" are the
  same predicate. A numeric difference inside one flavour is real drift; a
  different flavour is different silicon and can never converge.
- **Sensor coverage** is whether the sensor answered. `smartmon_device_smart_available`
  is `0` on a node whose devices cannot report health, and a node with no EDAC or
  no UPS has no series at all.
- **The node inventory** is the Kubernetes node list, which is authoritative in a
  way a checked-in list never is.

So nothing here needs maintaining when the homelab changes.
"""

from __future__ import annotations

import re

# A kernel release is a numeric version followed by a distributor/tree suffix:
#   6.12.96+deb13-amd64        -> deb13-amd64
#   6.1.115-vendor-rk35xx      -> vendor-rk35xx
#   7.1.2-edge-rockchip64      -> edge-rockchip64
#   6.12.15-production+truenas -> production+truenas
# The leading dotted numbers are the part that legitimately differs between two
# machines of the same kind; everything after it is what makes them the same kind.
_VERSION_HEAD = re.compile(r"^\d+(?:\.\d+)*")


def kernel_flavour(release: str) -> str:
    """The part of a kernel release that identifies its tree, not its version.

    Returns ``"unversioned"`` when a release carries no numeric head, so an
    unexpected string still groups with its identical twins instead of raising.
    """
    if not release:
        return "unknown"
    stripped = _VERSION_HEAD.sub("", release, count=1).lstrip("+-.")
    return stripped or "unversioned"


def kernel_version(release: str) -> str:
    """The numeric head of a kernel release, i.e. what differs within a flavour."""
    match = _VERSION_HEAD.match(release or "")
    return match.group(0) if match else ""


def version_key(release: str) -> tuple[int, ...]:
    """Sortable form of the numeric head, so 6.12.101 orders above 6.12.96.

    String comparison gets this backwards -- "6.12.96" > "6.12.101" -- which
    would name the wrong node as the one trailing its class.
    """
    return tuple(int(part) for part in kernel_version(release).split(".") if part.isdigit())


def class_name(release: str, machine: str) -> str:
    """The comparability group: kernel tree plus architecture."""
    return f"{kernel_flavour(release)}/{machine or 'unknown-arch'}"


def common_prefix(names: list[str]) -> str:
    """Longest shared prefix of ``names``, trimmed to a separator.

    Node names in a homelab usually share a cluster prefix that costs table width
    and tells the reader nothing. Deriving it beats hardcoding one, which would
    be another copy of the cluster's naming scheme.
    """
    if len(names) < 2:
        return ""
    first, last = min(names), max(names)
    limit = 0
    while limit < len(first) and limit < len(last) and first[limit] == last[limit]:
        limit += 1
    prefix = first[:limit]
    cut = max(prefix.rfind("-"), prefix.rfind("."), prefix.rfind("_"))
    return prefix[: cut + 1] if cut >= 0 else ""


def shorten(name: str, prefix: str) -> str:
    """Drop ``prefix`` from ``name``, keeping the full name if that would empty it."""
    if prefix and name.startswith(prefix) and len(name) > len(prefix):
        return name[len(prefix) :]
    return name


def group_by_class(kernels: dict[str, str], machines: dict[str, str]) -> dict[str, list[str]]:
    """``{class: [node, ...]}`` for every node with a known kernel."""
    grouped: dict[str, list[str]] = {}
    for node, release in kernels.items():
        grouped.setdefault(class_name(release, machines.get(node, "")), []).append(node)
    return {key: sorted(value) for key, value in sorted(grouped.items())}


def kernel_drift(
    kernels: dict[str, str], machines: dict[str, str]
) -> list[tuple[str, list[str], list[str]]]:
    """Per class, return ``(class, members, nodes_behind)``.

    ``nodes_behind`` is empty unless the class holds more than one distinct
    numeric version, and a class of one is therefore never a finding: it has
    nothing to compare against. orpi-0 was reported as kernel drift against
    orpi-1/2/3 every run for days on exactly that mistake -- different SoC
    families on different trees, so the finding could never be actioned and never
    cleared, while a non-empty findings section forced a Slack post each time.
    """
    out = []
    for group, members in group_by_class(kernels, machines).items():
        versions = {node: kernels[node] for node in members}
        if len(members) < 2 or len(set(versions.values())) < 2:
            out.append((group, members, []))
            continue
        newest = max(version_key(release) for release in versions.values())
        behind = sorted(
            node for node, release in versions.items() if version_key(release) < newest
        )
        out.append((group, members, behind))
    return out
