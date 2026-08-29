"""`find_object()` - turn the word a person used into the exact names it means.

Every `k8s_*` tool takes exact values, and nobody types one. Asked why
`grafana-setup-job` failed, a run guessed `app=grafana`, then
`app-inclusive=grafana`, then `kube-prometheus-stack` as a namespace - eight
calls, none of which matched, against a cluster where the real label is
`app.kubernetes.io/name=grafana`, the namespace is `monitoring`, and no object is
called `grafana-setup-job` at all. It then reported that grafana does not exist.

Telling a 4B model not to guess a selector asks it to tell a correct label key
from an invented one, which is knowing the answer. So the search happens here:
substring, then every-word, over the kinds a question is ever about. See
../../README.md.
"""

from __future__ import annotations

import re

from mcp_runner import kube, render
from mcp_runner.budget import truncate_lines

from .. import settings

BUDGET = 3072

# Per kind, so one noisy kind cannot crowd out the kind that answers. Rows are
# newest first: for a repeating Job the recent run is the one being asked about.
_PER_KIND = 6

# Services whose endpoints are worth a second call. A Service with no ready
# endpoint is exactly what `curl: (7) could not connect` means, and it is the
# finding that incident needed.
_MAX_ENDPOINT_CHECKS = 4

# Searched in the order a question tends to name them. Secrets and ConfigMaps are
# absent deliberately: `kube.list` strips a Secret's payload, but a name search
# over them is a way to enumerate credentials and answers no question here.
_KINDS: tuple[tuple[str, str], ...] = (
    ("v1", "Service"),
    ("traefik.io/v1alpha1", "IngressRoute"),
    ("networking.k8s.io/v1", "Ingress"),
    ("apps/v1", "Deployment"),
    ("apps/v1", "StatefulSet"),
    ("apps/v1", "DaemonSet"),
    ("batch/v1", "CronJob"),
    ("v1", "PersistentVolumeClaim"),
    ("argoproj.io/v1alpha1", "Application"),
    ("v1", "Namespace"),
    ("v1", "Node"),
    ("batch/v1", "Job"),
    ("v1", "Pod"),
)


def _tokens(term: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", term.lower()) if token]


def _matches(name: str, namespace: str, term: str, tokens: list[str]) -> str:
    """`exact`, `contains`, `words`, or `` for no match.

    `words` is what makes a name nobody typed findable: `grafana-setup-job`
    appears nowhere, while `e-monitoring-grafana-job-setup...-postsync-...`
    contains all three words. A person names the parts, not the string.
    """
    haystack = f"{namespace}/{name}".lower()
    if name.lower() == term.lower().strip():
        return "exact"
    if term.lower().strip() and term.lower().strip() in haystack:
        return "contains"
    if tokens and all(token in haystack for token in tokens):
        return "words"
    return ""


def _status(kind: str, obj: dict) -> str:
    """One column of whatever this kind's state actually is."""
    status = obj.get("status") or {}
    spec = obj.get("spec") or {}
    if kind == "Pod":
        containers = status.get("containerStatuses") or []
        ready = sum(1 for item in containers if item.get("ready"))
        restarts = sum(int(item.get("restartCount") or 0) for item in containers)
        phase = status.get("phase") or "unknown"
        return f"{phase} {ready}/{len(containers)} ready, {restarts} restarts"
    if kind == "Service":
        ports = ",".join(str(port.get("port")) for port in (spec.get("ports") or []))
        return f"{spec.get('type') or 'ClusterIP'} {spec.get('clusterIP') or '-'}:{ports or '-'}"
    if kind in {"Deployment", "StatefulSet"}:
        return f"{status.get('readyReplicas') or 0}/{spec.get('replicas') or 0} ready"
    if kind == "DaemonSet":
        return f"{status.get('numberReady') or 0}/{status.get('desiredNumberScheduled') or 0} ready"
    if kind == "Job":
        succeeded = int(status.get("succeeded") or 0)
        failed = int(status.get("failed") or 0)
        finished = render.age(status.get("completionTime")) if status.get("completionTime") else "-"
        return f"{succeeded} succeeded, {failed} FAILED, finished {finished}"
    if kind == "CronJob":
        suspended = " SUSPENDED" if spec.get("suspend") else ""
        return f"{spec.get('schedule') or '-'}{suspended}, last {render.age(status.get('lastScheduleTime'))}"
    if kind == "PersistentVolumeClaim":
        capacity = (status.get("capacity") or {}).get("storage") or "-"
        return f"{status.get('phase') or 'unknown'}, {capacity}"
    if kind == "IngressRoute":
        # The hostname is the answer to "what serves X", so it is the column.
        # A Host(`...`) match is the only part worth returning; the rest of a
        # rule is middleware wiring nobody asked about.
        hosts: list[str] = []
        for route in spec.get("routes") or []:
            for match in re.findall(r"Host\(`([^`]+)`\)", route.get("match") or ""):
                if match not in hosts:
                    hosts.append(match)
        entry = ",".join(spec.get("entryPoints") or []) or "-"
        return f"{entry} -> {', '.join(hosts[:3]) or 'no Host() rule'}"
    if kind == "Application":
        return (
            f"{((status.get('sync') or {}).get('status')) or 'unknown'}/"
            f"{((status.get('health') or {}).get('status')) or 'unknown'}"
        )
    if kind == "Namespace":
        return status.get("phase") or "-"
    if kind == "Node":
        conditions = {item.get("type"): item.get("status") for item in (status.get("conditions") or [])}
        return "Ready" if conditions.get("Ready") == "True" else "NOT Ready"
    return "-"


def find_object(term: str) -> str:
    """Find every object whose name contains ``term``, or all of its words."""
    term = (term or "").strip()
    if not term:
        return "ERROR: term is required. Example: term=grafana"

    tokens = _tokens(term)
    client = settings.kube()

    lines: list[str] = [
        (
            f"Objects matching '{term}'. Names here are exact and can be passed to any "
            "k8s_* tool; the namespace column is the `namespace` argument."
        ),
        "",
    ]
    found = 0
    services: list[tuple[str, str]] = []
    unreadable: list[str] = []

    for api_version, kind in _KINDS:
        try:
            objects = client.list(api_version, kind)
        except kube.KubeForbidden:
            # Never counted as searched. A kind this server may not list is a
            # blind spot, and reporting it as "no match" is how a running
            # grafana was declared absent.
            unreadable.append(kind)
            continue
        except kube.KubeError as exc:
            lines.append(f"{kind}: ERROR - {exc}")
            continue
        hits = []
        for obj in objects:
            metadata = obj.get("metadata") or {}
            name = metadata.get("name") or ""
            namespace = metadata.get("namespace") or "-"
            how = _matches(name, namespace, term, tokens)
            if how:
                hits.append((metadata.get("creationTimestamp") or "", namespace, name, how, obj))
        if not hits:
            continue
        # Newest first: a repeating Job leaves dozens of finished pods and the
        # question is always about a recent one.
        hits.sort(key=lambda hit: hit[0], reverse=True)
        found += len(hits)
        lines.append(f"## {kind} ({len(hits)})")
        rows = [
            [namespace, name, how, _status(kind, obj), render.age(created)]
            for created, namespace, name, how, obj in hits[:_PER_KIND]
        ]
        lines += render.table(["namespace", "name", "match", "state", "age"], rows)
        if len(hits) > _PER_KIND:
            lines.append(
                f"({len(hits) - _PER_KIND} more {kind}s match and are not listed; "
                "the newest are shown.)"
            )
        if kind == "Service":
            services = [(namespace, name) for _, namespace, name, _, _ in hits[:_MAX_ENDPOINT_CHECKS]]
            lines += _endpoints(client, services)
        lines.append("")

    if unreadable:
        lines.append(
            "## NOT SEARCHED - this server may not list: " + ", ".join(unreadable)
        )
        lines.append(
            "These kinds were not looked at. Nothing below or above says anything "
            "about them, and their absence from this result is a permission gap "
            "rather than a fact about the cluster."
        )
        lines.append("")

    if not found:
        searched = [kind for _, kind in _KINDS if kind not in unreadable]
        if not searched:
            return (
                f"ERROR: nothing could be searched for '{term}'. This server is not "
                f"permitted to list any of: {', '.join(unreadable)}.\n"
                f"This is a permission failure, not an empty cluster. Do not report "
                f"that anything is missing."
            )
        message = (
            f"No {', '.join(searched)} has a name containing '{term}' or all of its "
            f"words.\n"
            f"This is a searched-and-not-matched result for those kinds only. It is "
            f"not proof that nothing related exists: try a shorter term, or a single "
            f"word."
        )
        if unreadable:
            message += (
                f"\nNOT SEARCHED, because this server may not list them: "
                f"{', '.join(unreadable)}. A match there would not have been seen."
            )
        return message

    return truncate_lines(lines, BUDGET, unit="lines")


def _endpoints(client, services: list[tuple[str, str]]) -> list[str]:
    """Ready addresses behind each matched Service.

    `curl: (7) could not connect` on a name that resolves is a Service with no
    ready endpoint, not a missing Service. Stating the count makes that finding
    reachable in the same call that found the name.
    """
    lines = []
    for namespace, name in services:
        objects = client.list(
            "v1", "Endpoints", namespace=namespace, field_selector=f"metadata.name={name}"
        )
        if not objects:
            lines.append(
                f"{namespace}/{name}: no Endpoints object. The Service exists and has "
                "nothing behind it - a connection to it is refused."
            )
            continue
        ready = 0
        not_ready = 0
        for subset in (objects[0].get("subsets") or []):
            ready += len(subset.get("addresses") or [])
            not_ready += len(subset.get("notReadyAddresses") or [])
        verdict = (
            "connections succeed" if ready else "NO ready endpoint - connections are refused"
        )
        lines.append(f"{namespace}/{name}: {ready} ready, {not_ready} not ready - {verdict}.")
    return lines


SCHEMA = {
    "type": "object",
    "properties": {
        "term": {
            "type": "string",
            "description": "The word a person used, e.g. grafana, or several words "
            "such as grafana setup job. Case and punctuation are ignored and no "
            "part of the name has to be exact.",
        }
    },
    "required": ["term"],
    "additionalProperties": False,
}

DESCRIPTION = """
Find the exact namespace and name of anything, from the word a person used.

Call this FIRST for any question naming a service, pod, job, app or volume, and
take every namespace and name you use afterwards from its output. Matching is by
substring and then by every word, so 'grafana', 'grafana setup job' and a full
generated pod name all work, and nothing has to be exact.

Searches Pods, Services, Deployments, StatefulSets, DaemonSets, Jobs, CronJobs,
PVCs, Ingresses, Traefik IngressRoutes, ArgoCD Applications, Namespaces and
Nodes, newest first, with each one's state. An IngressRoute reports the
hostnames it serves, which is what answers "what URL is X on". For a matched Service it also reports how many ready endpoints
are behind it. No match is reported as searched-and-not-matched, which is never
proof that a thing does not exist.
"""
