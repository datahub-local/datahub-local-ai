from datetime import UTC, datetime, timedelta

from airflow import DAG
from utils.dbt import DbtTaskConfig, SecretEnvVarRef, create_dbt_task
from utils.dlt import DltTaskConfig, create_dlt_task

S3_SECRET_ENV_VARS = (
    SecretEnvVarRef(secret_name="s3-credentials", secret_key="accessKey", env_name="S3_ACCESS_KEY"),
    SecretEnvVarRef(secret_name="s3-credentials", secret_key="secretKey", env_name="S3_SECRET_KEY"),
)
POSTGRES_SECRET_ENV_VARS = (
    SecretEnvVarRef(secret_name="postgresql-admin-credentials", secret_key="user", env_name="EXAMPLE_DB_USER"),
    SecretEnvVarRef(secret_name="postgresql-admin-credentials", secret_key="password", env_name="EXAMPLE_DB_PASSWORD"),
)
EXAMPLE_DB_ENV_VARS = {
    "EXAMPLE_DB_URL": "jdbc:postgresql://datahub-local-core-data-postgresql.data.svc.cluster.local:5432/dbt",
    "EXAMPLE_DB_SCHEMA": "dbt_example_db",
}

default_args = {
    "owner": "datahub-local",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="example_db",
    default_args=default_args,
    description="example_db pipeline: dlt ingest → dbt build → dlt export (Trino + Postgres)",
    schedule=None,
    start_date=datetime(2025, 1, 1, tzinfo=UTC),
    catchup=False,
    tags=["dbt", "dlt"],
) as dag:
    dlt_ingest = create_dlt_task(
        DltTaskConfig(
            task_id="dlt_ingest_example_db",
            project="example_db",
            pipeline="ingest",
            secret_env_vars=S3_SECRET_ENV_VARS,
        )
    )

    dbt_build = create_dbt_task(
        DbtTaskConfig(task_id="dbt_example_db", project="example_db", full_refresh=True)
    )

    dlt_export = create_dlt_task(
        DltTaskConfig(
            task_id="dlt_export_example_db",
            project="example_db",
            pipeline="export",
            env_vars=EXAMPLE_DB_ENV_VARS,
            secret_env_vars=(*S3_SECRET_ENV_VARS, *POSTGRES_SECRET_ENV_VARS),
        )
    )

    dlt_ingest >> dbt_build >> dlt_export
