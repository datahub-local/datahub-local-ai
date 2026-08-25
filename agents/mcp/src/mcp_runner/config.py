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


def state_dir() -> str:
    """Where snapshots for the computed diffs live. An emptyDir is enough."""
    return env("MCP_STATE_DIR", "/tmp/mcp-state")


def config_dir() -> str | None:
    """Override for the project's ``config/`` directory (tests use this)."""
    return env("MCP_CONFIG_DIR")
