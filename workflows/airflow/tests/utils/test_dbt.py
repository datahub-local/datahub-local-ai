import pytest
from airflow.exceptions import AirflowException

from utils.dbt import (
    ConfigMapEnvVarRef,
    DbtTaskConfig,
    SecretEnvVarRef,
    build_dbt_arguments,
    build_dbt_container_resources,
    build_dbt_env_vars,
    create_dbt_task,
)


def test_build_dbt_arguments_defaults():
    task_config = DbtTaskConfig(task_id="dbt_pi", project="pi")

    assert build_dbt_arguments(task_config) == ["--project", "pi", "--target", "homelab"]


def test_build_dbt_arguments_includes_select_model():
    task_config = DbtTaskConfig(task_id="dbt_pi", project="pi", select_model="pi_estimate")

    assert build_dbt_arguments(task_config) == [
        "--project", "pi", "--target", "homelab", "--select", "pi_estimate",
    ]


def test_build_dbt_arguments_full_refresh():
    task_config = DbtTaskConfig(task_id="dbt_example_db", project="example_db", full_refresh=True)

    assert build_dbt_arguments(task_config) == [
        "--project", "example_db", "--target", "homelab", "--full-refresh",
    ]


def test_build_dbt_arguments_supports_custom_target():
    task_config = DbtTaskConfig(task_id="dbt_pi", project="pi", target="local")

    assert build_dbt_arguments(task_config) == ["--project", "pi", "--target", "local"]


def test_build_dbt_env_vars_include_values_and_secrets():
    task_config = DbtTaskConfig(
        task_id="dbt_example_db",
        project="example_db",
        env_vars={"TRINO_HOST": "trino"},
        secret_env_vars=(
            SecretEnvVarRef(secret_name="s3-credentials", secret_key="accessKey", env_name="S3_ACCESS_KEY"),
        ),
    )

    env_var_map = {env_var.name: env_var for env_var in build_dbt_env_vars(task_config)}

    assert env_var_map["TRINO_HOST"].value == "trino"
    assert env_var_map["S3_ACCESS_KEY"].value_from.secret_key_ref.name == "s3-credentials"


def test_build_dbt_env_vars_only_explicit_refs():
    task_config = DbtTaskConfig(task_id="dbt_example_db", project="example_db")

    env_var_names = {env_var.name for env_var in build_dbt_env_vars(task_config)}

    # Nothing is auto-injected; only the env/secret/configmap refs on the config are emitted.
    assert env_var_names == set()


def test_build_dbt_env_vars_support_configmap_with_renamed_env_var():
    task_config = DbtTaskConfig(
        task_id="dbt_example_db",
        project="example_db",
        configmap_env_vars=(
            ConfigMapEnvVarRef(
                configmap_name="dbt-config", configmap_key="TRINO_PORT", env_name="TRINO_PORT"
            ),
        ),
    )

    env_var_map = {env_var.name: env_var for env_var in build_dbt_env_vars(task_config)}

    assert env_var_map["TRINO_PORT"].value_from.config_map_key_ref.name == "dbt-config"


def test_build_dbt_container_resources_use_cpu_memory():
    task_config = DbtTaskConfig(task_id="dbt_pi", project="pi", cpu="1", memory="2G")

    resources = build_dbt_container_resources(task_config)

    assert resources is not None
    assert resources.requests == {"cpu": "1", "memory": "2G"}
    assert resources.limits == {"cpu": "1", "memory": "2G"}


def test_build_dbt_container_resources_none_when_unset():
    assert build_dbt_container_resources(DbtTaskConfig(task_id="dbt_pi", project="pi")) is None


def test_create_dbt_task_applies_arguments_and_image():
    task_config = DbtTaskConfig(
        task_id="dbt_pi",
        project="pi",
        secret_env_vars=(
            SecretEnvVarRef(secret_name="s3-credentials", secret_key="accessKey", env_name="S3_ACCESS_KEY"),
        ),
    )

    task = create_dbt_task(task_config)
    env_var_map = {env_var.name: env_var for env_var in task.env_vars}

    assert task.arguments == ["--project", "pi", "--target", "homelab"]
    assert env_var_map["S3_ACCESS_KEY"].value_from.secret_key_ref.name == "s3-credentials"
    assert task.image_pull_policy == "Always"
    assert not task.env_from
    assert not task.volumes


def test_create_dbt_task_applies_trigger_rule():
    task = create_dbt_task(
        DbtTaskConfig(task_id="dbt_silver", project="finance", trigger_rule="none_failed_min_one_success")
    )

    assert task.trigger_rule == "none_failed_min_one_success"


def test_validate_task_config_does_not_require_local_project_files():
    task_config = DbtTaskConfig(task_id="dbt_missing", project="missing-project")

    assert build_dbt_arguments(task_config) == [
        "--project", "missing-project", "--target", "homelab",
    ]


def test_validate_task_config_rejects_invalid_target():
    task_config = DbtTaskConfig(task_id="dbt_pi", project="pi", target="home/lab")

    with pytest.raises(AirflowException, match="target"):
        build_dbt_arguments(task_config)
