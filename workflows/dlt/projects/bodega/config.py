"""Pipeline-specific configuration for the bodega dlt pipelines.

Shared infrastructure (Trino, Polaris, DuckDB paths, S3, target validation) lives in
``dlt_runner.config`` and is re-exported here so callers use a single import.
"""

from __future__ import annotations

import os

from dlt_runner.config import VALID_TARGETS as VALID_TARGETS
from dlt_runner.config import bronze_bucket as bronze_bucket
from dlt_runner.config import configure_iceberg_env as configure_iceberg_env
from dlt_runner.config import duckdb_path as duckdb_path
from dlt_runner.config import env as env
from dlt_runner.config import litellm_api_key as litellm_api_key
from dlt_runner.config import litellm_base_url as litellm_base_url
from dlt_runner.config import litellm_model as litellm_model
from dlt_runner.config import llm_provider as llm_provider
from dlt_runner.config import llm_settings as llm_settings
from dlt_runner.config import llm_timeout as llm_timeout
from dlt_runner.config import ollama_base_url as ollama_base_url
from dlt_runner.config import ollama_model as ollama_model
from dlt_runner.config import polaris_uri as polaris_uri
from dlt_runner.config import s3_credentials as s3_credentials
from dlt_runner.config import s3_endpoint as s3_endpoint
from dlt_runner.config import silver_bucket as silver_bucket
from dlt_runner.config import trino_url as trino_url
from dlt_runner.config import validate_target as validate_target

KAFKA_BOOTSTRAP_SERVERS_DEFAULT = (
    "datahub-local-core-data-redpanda-0.datahub-local-core-data-redpanda.data.svc.cluster.local:9093,"
    "datahub-local-core-data-redpanda-1.datahub-local-core-data-redpanda.data.svc.cluster.local:9093,"
    "datahub-local-core-data-redpanda-2.datahub-local-core-data-redpanda.data.svc.cluster.local:9093"
)


def kafka_bootstrap_servers() -> str:
    return os.environ["KAFKA_BOOTSTRAP_SERVERS"]


def kafka_topic() -> str:
    return env("KAFKA_TOPIC_BODEGA", "bodega_invoices")


def ingest_from_date() -> str | None:
    """Start (inclusive) of the invoice_date reconciliation window, if scoped."""
    return env("BODEGA_FROM_DATE")


def ingest_to_date() -> str | None:
    """End (inclusive) of the invoice_date reconciliation window, if scoped."""
    return env("BODEGA_TO_DATE")


def ingest_batch_timestamp() -> str | None:
    """DAG-run-stable timestamp n8n stamps on Kafka messages, used to tell rows
    refreshed by the current reconciliation run apart from stale leftovers."""
    return env("BODEGA_BATCH_TIMESTAMP")


def product_language() -> str:
    """Language of the raw product descriptions fed to the enrich LLM prompt."""
    return env("BODEGA_PRODUCT_LANGUAGE", "Spanish")
