"""Loading of this project's ``config/*.yaml``, and the shared client handles."""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml

from mcp_runner import config as runner_config
from mcp_runner.garage import Garage
from mcp_runner.kube import Kube
from mcp_runner.loki import Loki
from mcp_runner.prometheus import Prometheus
from mcp_runner.state import Snapshots

_HERE = Path(__file__).resolve().parent


def config_dir() -> Path:
    override = runner_config.config_dir()
    return Path(override) if override else _HERE / "config"


@functools.cache
def load(name: str) -> dict[str, Any]:
    """Load and cache one config file. A missing file is an empty mapping.

    Empty rather than fatal: an unclassified snapshot is a worse report, but a
    true one.
    """
    path = config_dir() / name
    try:
        return yaml.safe_load(path.read_text()) or {}
    except FileNotFoundError:
        return {}


def thresholds(section: str) -> dict[str, Any]:
    return load("thresholds.yaml").get(section) or {}


# Nothing here describes the fleet's shape - node names, hardware classes and
# sensor coverage are all derived at query time; see `mcp_runner.fleet`.


def chronic_alerts() -> dict[str, str]:
    return {
        entry["name"]: entry.get("reason", "")
        for entry in load("chronic_alerts.yaml").get("chronic") or []
        if entry.get("name")
    }


def never_suppress() -> dict[str, str]:
    return {
        entry["name"]: entry.get("reason", "")
        for entry in load("chronic_alerts.yaml").get("never_suppress") or []
        if entry.get("name")
    }


# Client handles are lazy and cached: building a Kubernetes client costs a
# credential load, and a tool that never touches Kubernetes should not pay it.


@functools.lru_cache(maxsize=1)
def prometheus() -> Prometheus:
    return Prometheus()


@functools.lru_cache(maxsize=1)
def kube() -> Kube:
    return Kube()


@functools.lru_cache(maxsize=1)
def garage() -> Garage:
    return Garage()


@functools.lru_cache(maxsize=1)
def loki() -> Loki:
    return Loki()


@functools.lru_cache(maxsize=1)
def snapshots() -> Snapshots:
    return Snapshots()
