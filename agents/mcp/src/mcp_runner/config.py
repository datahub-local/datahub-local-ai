"""Env-driven configuration. Defaults are the in-cluster addresses.

Verified reachable from `automation` on 2026-08-25: the Prometheus service
answers `/api/v1/query?query=up` with HTTP 200 and `monitoring` has no
NetworkPolicies.
"""

from __future__ import annotations

import os


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, default)
    return value if value not in (None, "") else default


def prometheus_url() -> str:
    """Prometheus, queried directly rather than through Grafana.

    Going direct deletes an entire failure class. Through Grafana every query
    needed a `datasourceUid`, and this Grafana serves three datasources whose
    uids are `prometheus`, an Alertmanager, and Loki's `P8E80F9AEF21F6940`. A 4B
    model reads the hex string as the real identifier and the bare word as a
    placeholder to resolve, so every PromQL query went to Loki and answered
    `404 page not found` — against a prompt that stated the right value two
    paragraphs above. No uid exists on this path, so none can be chosen wrongly.
    """
    return env(
        "PROMETHEUS_URL",
        "http://datahub-local-core-kube-pr-prometheus.monitoring.svc:9090",
    )


def prometheus_timeout() -> float:
    return float(env("PROMETHEUS_TIMEOUT_SECONDS", "20"))


def state_dir() -> str:
    """Where snapshots for the computed diffs live.

    An emptyDir is enough: a lost snapshot degrades a diff to "first run", which
    the tools state explicitly, rather than producing a wrong one.
    """
    return env("MCP_STATE_DIR", "/tmp/mcp-state")


def config_dir() -> str | None:
    """Override for the project's ``config/`` directory (tests use this)."""
    return env("MCP_CONFIG_DIR")
