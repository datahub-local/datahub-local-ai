from datetime import datetime, timedelta

from airflow import DAG
from airflow.sdk import Param

from utils.dbt import DbtTaskConfig, SecretEnvVarRef, create_dbt_task
from utils.dlt import DltTaskConfig, create_dlt_task
from utils.n8n import N8nTaskConfig, create_n8n_task

S3_SECRET_ENV_VARS = (
    SecretEnvVarRef(secret_name="s3-credentials", secret_key="accessKey", env_name="S3_ACCESS_KEY"),
    SecretEnvVarRef(secret_name="s3-credentials", secret_key="secretKey", env_name="S3_SECRET_KEY"),
)
ICEBERG_SECRET_ENV_VARS = S3_SECRET_ENV_VARS + (
    SecretEnvVarRef(secret_name="polaris-auth-credentials", secret_key="user", env_name="POLARIS_CLIENT_ID"),
    SecretEnvVarRef(secret_name="polaris-auth-credentials", secret_key="password", env_name="POLARIS_CLIENT_SECRET"),
)
LITELLM_SECRET_ENV_VARS = (
    SecretEnvVarRef(secret_name="litellm-auth-credentials", secret_key="api_key", env_name="LITELLM_API_KEY"),
)
N8N_DOWNLOAD_INVOICES_WORKFLOW_NAME = "DownloadInvoicesFromGmail"

BODEGA_ENV_VARS = {
    "KAFKA_BOOTSTRAP_SERVERS": "".join(
        f"datahub-local-core-data-redpanda-{i}.datahub-local-core-data-redpanda.data.svc.cluster.local:9093,"
        for i in range(3)
    ),
    "KAFKA_TOPIC_BODEGA": "bodega_invoices",
}

default_args = {
    "owner": "datahub-local",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}



# Defaults are computed via Jinja/macros at task render time (wall-clock "now"), not
# with datetime.now() in the DAG constructor — the latter re-evaluates on every
# DAG-file parse and bumps the DAG version on no real change.
FROM_DATE_EXPR = "{{ params.from_date or macros.ds_add(macros.datetime.now() | ds, -7) }}"
TO_DATE_EXPR = "{{ params.to_date or macros.ds_add(macros.datetime.now() | ds, 1) }}"

# Airflow's logical run timestamp (stable across every task in the same DagRun), used to
# tag n8n's Kafka messages and let dlt_ingest tell "refreshed this run" apart from stale
# leftovers when reconciling the [from_date, to_date] window.
BATCH_TIMESTAMP_EXPR = "{{ ts }}"

with DAG(
    dag_id="bodega_daily",
    default_args=default_args,
    description="bodega pipeline: dlt ingest → dbt silver → dlt enrich → dbt gold",
    schedule="0 8 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["dbt", "dlt", "n8n"],
    params={
        "from_date": Param(
            default=None,
            type=["string", "null"],
            format="date",
            description="Start date (YYYY-MM-DD). Defaults to 7 days before today (run's wall-clock date).",
        ),
        "to_date": Param(
            default=None,
            type=["string", "null"],
            format="date",
            description="End date (YYYY-MM-DD). Defaults to today (run's wall-clock date).",
        ),
    },
) as dag:
    n8n_download_invoices = create_n8n_task(
        N8nTaskConfig(
            task_id="n8n_download_invoices",
            workflow_name=N8N_DOWNLOAD_INVOICES_WORKFLOW_NAME,
            params={
                "FROM_DATE": FROM_DATE_EXPR,
                "TO_DATE": TO_DATE_EXPR,
                "BATCH_TIMESTAMP": BATCH_TIMESTAMP_EXPR,
            },
        )
    )

    dlt_ingest = create_dlt_task(
        DltTaskConfig(
            task_id="dlt_ingest_bodega",
            project="bodega",
            pipeline="ingest",
            env_vars={
                **BODEGA_ENV_VARS,
                "BODEGA_FROM_DATE": FROM_DATE_EXPR,
                "BODEGA_TO_DATE": TO_DATE_EXPR,
                "BODEGA_BATCH_TIMESTAMP": BATCH_TIMESTAMP_EXPR,
            },
            secret_env_vars=ICEBERG_SECRET_ENV_VARS,
        )
    )

    dbt_silver = create_dbt_task(
        DbtTaskConfig(
            task_id="dbt_silver_bodega",
            project="bodega",
            select_model="silver.*",
        )
    )

    dlt_enrich = create_dlt_task(
        DltTaskConfig(
            task_id="dlt_enrich_bodega",
            project="bodega",
            pipeline="enrich",
            secret_env_vars=ICEBERG_SECRET_ENV_VARS + LITELLM_SECRET_ENV_VARS,
        )
    )

    dbt_gold = create_dbt_task(
        DbtTaskConfig(
            task_id="dbt_gold_bodega",
            project="bodega",
            select_model="gold.*",
        )
    )

    n8n_download_invoices >> dlt_ingest >> dbt_silver >> dlt_enrich >> dbt_gold
