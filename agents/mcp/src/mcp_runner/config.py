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


def garage_admin_url() -> str:
    """Garage's admin API, which is the only place per-bucket usage exists.

    Prometheus carries no bucket label and no stored-bytes gauge, so bucket size
    and object count are reachable only here. Unlike Prometheus and Loki this
    endpoint needs a bearer token, so it is the one optional dependency in the
    server: without a token the bucket section reports itself unavailable and
    every other reading is unaffected.
    """
    return env("GARAGE_ADMIN_URL", "http://datahub-local-core-data-garage.data.svc:3903")


def garage_admin_token() -> str | None:
    """The bearer token, or ``None`` when the server is deliberately without one.

    ``None`` is the default and a supported state, not a misconfiguration.
    """
    return env("GARAGE_ADMIN_TOKEN")


def garage_timeout() -> float:
    return float(env("GARAGE_TIMEOUT_SECONDS", "10"))
