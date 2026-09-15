import pytest
from airflow.exceptions import AirflowException

from utils.dlt import (
    DLT_IMAGE,
    DltTaskConfig,
    build_dlt_arguments,
    build_dlt_env_vars,
    create_dlt_task,
)
from utils.dbt import SecretEnvVarRef


def test_build_dlt_arguments():
    task_config = DltTaskConfig(task_id="dlt_ingest", project="example_db", pipeline="ingest")

    assert build_dlt_arguments(task_config) == [
        "--pipeline", "ingest", "--project", "example_db", "--target", "homelab",
    ]


def test_build_dlt_arguments_export_custom_target():
    task_config = DltTaskConfig(
        task_id="dlt_export", project="example_db", pipeline="export", target="local"
    )

    assert build_dlt_arguments(task_config) == [
        "--pipeline", "export", "--project", "example_db", "--target", "local",
    ]


def test_invalid_pipeline_rejected():
    task_config = DltTaskConfig(task_id="dlt_bad", project="example_db", pipeline="bogus")

    with pytest.raises(AirflowException, match="pipeline"):
        build_dlt_arguments(task_config)


def test_build_dlt_env_vars_with_secrets():
    task_config = DltTaskConfig(
        task_id="dlt_export",
        project="example_db",
        pipeline="export",
        env_vars={"EXAMPLE_DB_SCHEMA": "dbt_example_db"},
        secret_env_vars=(
            SecretEnvVarRef(secret_name="postgresql-admin-credentials", secret_key="user", env_name="EXAMPLE_DB_USER"),
        ),
    )

    env_var_map = {env_var.name: env_var for env_var in build_dlt_env_vars(task_config)}

    assert env_var_map["EXAMPLE_DB_SCHEMA"].value == "dbt_example_db"
    assert env_var_map["EXAMPLE_DB_USER"].value_from.secret_key_ref.name == "postgresql-admin-credentials"


def test_create_dlt_task_uses_dlt_image():
    task = create_dlt_task(
        DltTaskConfig(task_id="dlt_ingest", project="example_db", pipeline="ingest")
    )

    assert task.image == DLT_IMAGE
    assert task.arguments == [
        "--pipeline", "ingest", "--project", "example_db", "--target", "homelab",
    ]


def test_sync_pipeline_is_valid():
    # spec 005 gate 9: VALID_PIPELINES grows by one for the Actual Budget push
    task_config = DltTaskConfig(task_id="dlt_sync", project="example_db", pipeline="sync")
    assert build_dlt_arguments(task_config) == [
        "--pipeline", "sync", "--project", "example_db", "--target", task_config.target,
    ]
