from datetime import UTC, datetime, timedelta

from airflow import DAG
from utils.dbt import DbtTaskConfig, create_dbt_task

default_args = {
    "owner": "datahub-local",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="pi",
    default_args=default_args,
    description="Monte Carlo π estimate via dbt (Trino) — pure compute, no ingest/export",
    schedule=None,
    start_date=datetime(2025, 1, 1, tzinfo=UTC),
    catchup=False,
    tags=["dbt"],
) as dag:
    create_dbt_task(DbtTaskConfig(task_id="dbt_pi", project="pi", full_refresh=True))
