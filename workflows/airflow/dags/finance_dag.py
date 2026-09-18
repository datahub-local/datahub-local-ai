from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.sdk import Param

from utils.dbt import DbtTaskConfig, create_dbt_task
from utils.dlt import DltTaskConfig, SecretEnvVarRef, create_dlt_task

# Spot the one secret split: stable Enable Banking credential material vs the
# dynamically renewed session tokens (spec 005 §4.2.1/§4.7).
ENABLEBANKING_SECRET_ENV_VARS = (
    SecretEnvVarRef(secret_name="finance-enablebanking", secret_key="private_key", env_name="ENABLEBANKING_PRIVATE_KEY"),
    SecretEnvVarRef(secret_name="finance-enablebanking", secret_key="accounts.json", env_name="ENABLEBANKING_ACCOUNTS"),
    SecretEnvVarRef(secret_name="finance-enablebanking-token", secret_key="tokens.json", env_name="ENABLEBANKING_TOKENS"),
)
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
# The Actual Budget server address lives in the secret too, so core owns it
# alongside the password: the service name is decided when the release lands
# (INFRA-1), and a guessed host would reach nothing.
ACTUAL_SECRET_ENV_VARS = (
    SecretEnvVarRef(secret_name="finance-actual", secret_key="base_url", env_name="FINANCE_ACTUAL_BASE_URL"),
    SecretEnvVarRef(secret_name="finance-actual", secret_key="password", env_name="FINANCE_ACTUAL_PASSWORD"),
    SecretEnvVarRef(secret_name="finance-actual", secret_key="file", env_name="FINANCE_ACTUAL_FILE"),
    SecretEnvVarRef(secret_name="finance-actual", secret_key="accounts.json", env_name="FINANCE_ACTUAL_ACCOUNTS"),
)

default_args = {
    "owner": "datahub-local",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# Defaults are computed via Jinja/macros at task render time (wall-clock "now"), not
# with datetime.now() in the DAG constructor — the latter re-evaluates on every
# DAG-file parse and bumps the DAG version on no real change. Ingest defaults to
# FINANCE_FETCH_STRATEGY=longest, which ignores this window; it applies only when
# that env is set to `default` (14 days rather than bodega's 7 because banks post
# settlements late, spec 005 §4.3).
FROM_DATE_EXPR = "{{ params.from_date or macros.ds_add(macros.datetime.now() | ds, -14) }}"
TO_DATE_EXPR = "{{ params.to_date or macros.ds_add(macros.datetime.now() | ds, 1) }}"

FINANCE_ENV_VARS = {
    "FINANCE_FROM_DATE": FROM_DATE_EXPR,
    "FINANCE_TO_DATE": TO_DATE_EXPR,
}

# The ordered chain is spec 005 §4.8: ingest → silver → enrich → gold → sync.
with DAG(
    dag_id="finance_daily",
    default_args=default_args,
    description="finance pipeline: Enable Banking → dlt ingest → dbt silver → dlt enrich → dbt gold → Actual sync",
    schedule="0 6 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["dlt"],
    params={
        "from_date": Param(
            default=None,
            type=["string", "null"],
            format="date",
            description="Start date (YYYY-MM-DD). Defaults to 14 days before today (run's wall-clock date).",
        ),
        "to_date": Param(
            default=None,
            type=["string", "null"],
            format="date",
            description="End date (YYYY-MM-DD). Defaults to today (run's wall-clock date).",
        ),
    },
) as dag:
    dlt_ingest_finance = create_dlt_task(
        DltTaskConfig(
            task_id="dlt_ingest_finance",
            project="finance",
            pipeline="ingest",
            env_vars=FINANCE_ENV_VARS,
            secret_env_vars=ICEBERG_SECRET_ENV_VARS + ENABLEBANKING_SECRET_ENV_VARS,
        )
    )

    dbt_silver_finance = create_dbt_task(
        DbtTaskConfig(
            task_id="dbt_silver_finance",
            project="finance",
            select_model="silver.*",
        )
    )

    dlt_enrich_finance = create_dlt_task(
        DltTaskConfig(
            task_id="dlt_enrich_finance",
            project="finance",
            pipeline="enrich",
            secret_env_vars=ICEBERG_SECRET_ENV_VARS + LITELLM_SECRET_ENV_VARS,
        )
    )

    dbt_gold_finance = create_dbt_task(
        DbtTaskConfig(
            task_id="dbt_gold_finance",
            project="finance",
            select_model="gold.*",
        )
    )

    dlt_sync_actual = create_dlt_task(
        DltTaskConfig(
            task_id="dlt_sync_actual",
            project="finance",
            pipeline="sync",
            secret_env_vars=ACTUAL_SECRET_ENV_VARS,
        )
    )

    dlt_ingest_finance >> dbt_silver_finance >> dlt_enrich_finance >> dbt_gold_finance >> dlt_sync_actual
