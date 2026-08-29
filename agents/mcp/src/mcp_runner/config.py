"""Env-driven configuration. The defaults are the in-cluster addresses."""

from __future__ import annotations

import os


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, default)
    return value if value not in (None, "") else default


def prometheus_url() -> str:
    """Prometheus, queried directly rather than through Grafana.

    Going direct means there is no datasource uid on this path, so none can be
    resolved to the wrong datasource.
    """
    return env(
        "PROMETHEUS_URL",
        "http://datahub-local-core-kube-pr-prometheus.monitoring.svc:9090",
    )


def prometheus_timeout() -> float:
    return float(env("PROMETHEUS_TIMEOUT_SECONDS", "20"))


def loki_url() -> str:
    """Loki, queried directly rather than through Grafana, for the same reason.

    Verified against the cluster: this service answers `/loki/api/v1/*` with no
    auth and no tenant header, and its label set includes `namespace`, `pod` and
    `container`. Going direct means no datasource uid on this path either - the
    value a 4B model resolved to Loki's hex uid and 404'd every query with.
    """
    return env("LOKI_URL", "http://datahub-local-core-loki.monitoring.svc:3100")


def loki_timeout() -> float:
    return float(env("LOKI_TIMEOUT_SECONDS", "20"))


def state_dir() -> str:
    """Where snapshots for the computed diffs live. An emptyDir is enough."""
    return env("MCP_STATE_DIR", "/tmp/mcp-state")


def config_dir() -> str | None:
    """Override for the project's ``config/`` directory (tests use this)."""
    return env("MCP_CONFIG_DIR")
