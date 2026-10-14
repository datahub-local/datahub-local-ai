"""Shared utilities for Airflow Kubernetes pod tasks."""

import json
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("airflow.task")
SEP = "#" * 60


def _on_task_start(context: dict) -> None:
    ti = context["task_instance"]
    log.info(SEP)
    log.info("# dag=%s  task=%s  run=%s", ti.dag_id, ti.task_id, ti.run_id)
    log.info(SEP)


def _on_task_end(context: dict) -> None:
    ti = context["task_instance"]
    log.info(SEP)
    log.info("# DONE  dag=%s  task=%s", ti.dag_id, ti.task_id)
    log.info(SEP)


def _on_task_failure(context: dict) -> None:
    ti = context["task_instance"]
    log.info(SEP)
    log.info("# FAILED  dag=%s  task=%s", ti.dag_id, ti.task_id)
    log.info(SEP)

from kubernetes.client import (
    V1ConfigMapKeySelector,
    V1EnvVar,
    V1EnvVarSource,
    V1ResourceRequirements,
    V1SecretKeySelector,
)

_NAMESPACE_FILE = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"


def _current_namespace() -> str:
    try:
        return open(_NAMESPACE_FILE).read().strip()
    except OSError:
        return "default"


# Constants
NAMESPACE = _current_namespace()
IMAGE_PULL_POLICY = "Always"
SERVICE_ACCOUNT_NAME = "datahub-local-core-data-airflow-task"
DEFAULT_STARTUP_TIMEOUT_SECONDS = 300
DBT_IMAGE = "ghcr.io/datahub-local/datahub-local-ai-dbt:main"
DLT_IMAGE = "ghcr.io/datahub-local/datahub-local-ai-dlt:main"
DEFAULT_TARGET = "homelab"
DEFAULT_GATEWAY = "homelab"
DEFAULT_ENVIRONMENT = "prod"


@dataclass(frozen=True)
class SecretEnvVarRef:
    secret_name: str
    secret_key: str
    env_name: str | None = None


@dataclass(frozen=True)
class ConfigMapEnvVarRef:
    configmap_name: str
    configmap_key: str
    env_name: str | None = None


_NAME_RE = re.compile(r"[A-Za-z0-9_.-]+")


def _stringify_env_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _validate_name(label: str, value: str) -> None:
    if not _NAME_RE.fullmatch(value):
        from airflow.exceptions import AirflowException

        raise AirflowException(
            f"{label} must contain only letters, numbers, dots, underscores, and hyphens"
        )


def build_pod_env_vars(
    env_vars: Mapping[str, Any],
    secret_env_vars: tuple[SecretEnvVarRef, ...],
    configmap_env_vars: tuple[ConfigMapEnvVarRef, ...],
) -> list[V1EnvVar]:
    """Build the K8s env var list shared by the dbt, dlt, and other pod tasks."""
    result = [
        V1EnvVar(name=key, value=_stringify_env_value(value))
        for key, value in sorted(env_vars.items())
        if value not in (None, "")
    ]
    result.extend(
        V1EnvVar(
            name=ref.env_name or ref.secret_key,
            value_from=V1EnvVarSource(
                secret_key_ref=V1SecretKeySelector(name=ref.secret_name, key=ref.secret_key)
            ),
        )
        for ref in secret_env_vars
    )
    result.extend(
        V1EnvVar(
            name=ref.env_name or ref.configmap_key,
            value_from=V1EnvVarSource(
                config_map_key_ref=V1ConfigMapKeySelector(
                    name=ref.configmap_name, key=ref.configmap_key
                )
            ),
        )
        for ref in configmap_env_vars
    )
    return result


def build_pod_resources(cpu: str | None, memory: str | None) -> V1ResourceRequirements | None:
    requests: dict[str, str] = {}
    if cpu:
        requests["cpu"] = cpu
    if memory:
        requests["memory"] = memory
    if not requests:
        return None
    return V1ResourceRequirements(requests=requests, limits=dict(requests))


# Submodule imports come after the definitions above so that dbt.py / dlt.py
# can do `from utils import ...` without hitting a circular-import issue.
from utils.dbt import (
    DbtTaskConfig,
    build_dbt_arguments,
    build_dbt_container_resources,
    build_dbt_env_vars,
    create_dbt_task,
)
from utils.dlt import (
    DltTaskConfig,
    build_dlt_arguments,
    build_dlt_container_resources,
    build_dlt_env_vars,
    create_dlt_task,
)
from utils.n8n import (
    N8nTaskConfig,
    create_n8n_task,
)

__all__ = [
    "DBT_IMAGE",
    "DEFAULT_ENVIRONMENT",
    "DEFAULT_GATEWAY",
    "DEFAULT_STARTUP_TIMEOUT_SECONDS",
    "DEFAULT_TARGET",
    "DLT_IMAGE",
    "IMAGE_PULL_POLICY",
    "NAMESPACE",
    "SERVICE_ACCOUNT_NAME",
    "ConfigMapEnvVarRef",
    "DbtTaskConfig",
    "DltTaskConfig",
    "N8nTaskConfig",
    "SecretEnvVarRef",
    "build_dbt_arguments",
    "build_dbt_container_resources",
    "build_dbt_env_vars",
    "build_dlt_arguments",
    "build_dlt_container_resources",
    "build_dlt_env_vars",
    "build_pod_env_vars",
    "build_pod_resources",
    "create_dbt_task",
    "create_dlt_task",
    "create_n8n_task",
]
