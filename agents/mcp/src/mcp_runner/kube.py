"""Kubernetes reads. List-shaped, and never an object's contents.

`list` is the only verb exposed and `_strip` drops a Secret's payload at the
boundary, so no code path here can return one. Narrow the *request* too where you
can. See ../README.md.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Never emitted, whatever a caller asks for. The last-applied annotation is a
# full copy of the object and has carried inlined credentials before.
_REDACTED_FIELDS = frozenset({"data", "stringData"})
_REDACTED_ANNOTATIONS = frozenset({"kubectl.kubernetes.io/last-applied-configuration"})


class KubeError(RuntimeError):
    pass


class Kube:
    """Thin wrapper over the dynamic client, in-cluster or via a local kubeconfig."""

    def __init__(self) -> None:
        self._client = None

    def _dynamic(self):
        if self._client is not None:
            return self._client
        try:
            from kubernetes import client
            from kubernetes import config as kube_config
            from kubernetes.dynamic import DynamicClient
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise KubeError(f"kubernetes client unavailable: {exc}") from exc

        # In-cluster first, then a local kubeconfig, so the same code runs in a pod
        # and against the cluster from a laptop. The client raises a wide range of
        # unrelated types for "no credentials", so both arms are deliberately broad.
        try:
            kube_config.load_incluster_config()
        except Exception:  # noqa: BLE001 - not in a pod; fall back to a kubeconfig
            try:
                kube_config.load_kube_config()
            except Exception as exc:
                raise KubeError(f"no usable Kubernetes credentials: {exc}") from exc

        self._client = DynamicClient(client.ApiClient())
        return self._client

    def node_names(self) -> list[str]:
        """The authoritative node inventory.

        Kubernetes says which machines exist; Prometheus says which answered.
        The difference is what makes a dropped join visible.
        """
        return sorted(
            name
            for node in self.list("v1", "Node")
            if (name := (node.get("metadata") or {}).get("name"))
        )

    def list(
        self,
        api_version: str,
        kind: str,
        namespace: str | None = None,
        *,
        field_selector: str | None = None,
    ) -> list[dict[str, Any]]:
        """List objects of one kind. A missing CRD is an empty list, not an error.

        An absent API group is normal - any of these subsystems may be
        uninstalled - and the caller renders that as `unavailable`.
        """
        try:
            resource = self._dynamic().resources.get(api_version=api_version, kind=kind)
        except Exception as exc:  # noqa: BLE001 - an absent CRD degrades, never raises
            logger.warning("no such resource %s/%s: %s", api_version, kind, exc)
            return []
        kwargs: dict[str, Any] = {}
        if namespace:
            kwargs["namespace"] = namespace
        if field_selector:
            kwargs["field_selector"] = field_selector
        try:
            response = resource.get(**kwargs)
        except Exception as exc:  # noqa: BLE001 - a failed list is reported as absent
            logger.warning("listing %s/%s failed: %s", api_version, kind, exc)
            return []
        items = getattr(response, "items", None) or []
        return [
            _strip(item.to_dict() if hasattr(item, "to_dict") else dict(item)) for item in items
        ]


def _strip(obj: dict[str, Any]) -> dict[str, Any]:
    """Drop a Secret's payload before it reaches any caller.

    Belt and braces with `summarise`, so a caller reading raw objects still never
    sees `data`. Narrow the *request* too: an unfiltered cluster-wide Secret list
    transfers every value in every namespace.
    """
    for field in _REDACTED_FIELDS:
        obj.pop(field, None)
    annotations = ((obj.get("metadata") or {}).get("annotations")) or {}
    for annotation in _REDACTED_ANNOTATIONS:
        annotations.pop(annotation, None)
    return obj


def summarise(obj: dict[str, Any], fields: dict[str, tuple[str, ...]]) -> dict[str, Any]:
    """Project ``obj`` down to name, namespace and the named ``fields``.

    ``fields`` maps an output key to a path, e.g. ``{"phase": ("status", "phase")}``.
    An unresolvable path yields ``None``: a half-populated status is the normal
    state of a freshly created object.
    """
    metadata = obj.get("metadata") or {}
    out: dict[str, Any] = {
        "name": metadata.get("name"),
        "namespace": metadata.get("namespace"),
        "creationTimestamp": metadata.get("creationTimestamp"),
    }
    for key, path in fields.items():
        if key in _REDACTED_FIELDS or path[0] in _REDACTED_FIELDS:
            continue
        cursor: Any = obj
        for step in path:
            if not isinstance(cursor, dict):
                cursor = None
                break
            cursor = cursor.get(step)
        if key == "annotations" and isinstance(cursor, dict):
            cursor = {k: v for k, v in cursor.items() if k not in _REDACTED_ANNOTATIONS}
        out[key] = cursor
    return out
