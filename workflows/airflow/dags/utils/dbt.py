from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from airflow.providers.cncf.kubernetes.operators.job import KubernetesJobOperator
from kubernetes.client import V1EnvVar, V1PodSecurityContext, V1ResourceRequirements

from utils import (
    DEFAULT_STARTUP_TIMEOUT_SECONDS,
    DEFAULT_TARGET,
    DBT_IMAGE,
    IMAGE_PULL_POLICY,
    NAMESPACE,
    SERVICE_ACCOUNT_NAME,
    SecretEnvVarRef,
    ConfigMapEnvVarRef,
    _validate_name,
    _on_task_start,
    _on_task_end,
    _on_task_failure,
    build_pod_env_vars,
    build_pod_resources,
)


@dataclass(frozen=True)
class DbtTaskConfig:
    task_id: str
    project: str
    target: str = DEFAULT_TARGET
    select_model: str = ""
    full_refresh: bool = False
    env_vars: Mapping[str, Any] = field(default_factory=dict)
    secret_env_vars: tuple[SecretEnvVarRef, ...] = field(default_factory=tuple)
    configmap_env_vars: tuple[ConfigMapEnvVarRef, ...] = field(default_factory=tuple)
    cpu: str | None = None
    memory: str | None = None
    trigger_rule: str | None = None
    startup_timeout_seconds: int = DEFAULT_STARTUP_TIMEOUT_SECONDS


def validate_task_config(task_config: DbtTaskConfig) -> None:
    _validate_name("project", task_config.project)
    _validate_name("target", task_config.target)


def build_dbt_arguments(task_config: DbtTaskConfig) -> list[str]:
    validate_task_config(task_config)
    arguments = ["--project", task_config.project, "--target", task_config.target]
    if task_config.select_model:
        arguments.extend(["--select", task_config.select_model])
    if task_config.full_refresh:
        arguments.append("--full-refresh")
    return arguments


def build_dbt_env_vars(task_config: DbtTaskConfig) -> list[V1EnvVar]:
    validate_task_config(task_config)
    return build_pod_env_vars(
        task_config.env_vars, task_config.secret_env_vars, task_config.configmap_env_vars
    )


def build_dbt_container_resources(task_config: DbtTaskConfig) -> V1ResourceRequirements | None:
    validate_task_config(task_config)
    return build_pod_resources(task_config.cpu, task_config.memory)


def create_dbt_task(task_config: DbtTaskConfig) -> KubernetesJobOperator:
    operator_kwargs = (
        {"trigger_rule": task_config.trigger_rule} if task_config.trigger_rule else {}
    )
    return KubernetesJobOperator(
        task_id=task_config.task_id,
        name=task_config.task_id.replace("_", "-"),
        namespace=NAMESPACE,
        image=DBT_IMAGE,
        image_pull_policy=IMAGE_PULL_POLICY,
        arguments=build_dbt_arguments(task_config),
        env_vars=build_dbt_env_vars(task_config),
        container_resources=build_dbt_container_resources(task_config),
        ttl_seconds_after_finished=86400,
        wait_until_job_complete=True,
        backoff_limit=0,
        get_logs=True,
        log_events_on_failure=True,
        log_pod_spec_on_failure=True,
        do_xcom_push=False,
        service_account_name=SERVICE_ACCOUNT_NAME,
        security_context=V1PodSecurityContext(run_as_non_root=False),
        startup_timeout_seconds=task_config.startup_timeout_seconds,
        on_execute_callback=_on_task_start,
        on_success_callback=_on_task_end,
        on_failure_callback=_on_task_failure,
        **operator_kwargs,
    )
