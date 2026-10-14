"""Pipeline-specific configuration for the bodega dlt pipelines.

Shared infrastructure (Trino, Polaris, DuckDB paths, S3, target validation) lives in
``dlt_runner.config`` and is re-exported here so callers use a single import.
"""

from __future__ import annotations

import os

from dlt_runner.config import (
    VALID_TARGETS,
    bronze_bucket,
    configure_iceberg_env,
    duckdb_path,
    env,
    litellm_api_key,
    litellm_base_url,
    litellm_model,
    llm_provider,
    llm_settings,
    llm_timeout,
    ollama_base_url,
    ollama_model,
    polaris_uri,
    s3_credentials,
    s3_endpoint,
    silver_bucket,
    trino_url,
    validate_target,
)

__all__ = [
    "VALID_TARGETS",
    "bronze_bucket",
    "configure_iceberg_env",
    "duckdb_path",
    "env",
    "litellm_api_key",
    "litellm_base_url",
    "litellm_model",
    "llm_provider",
    "llm_settings",
    "llm_timeout",
    "ollama_base_url",
    "ollama_model",
    "polaris_uri",
    "s3_credentials",
    "s3_endpoint",
    "silver_bucket",
    "trino_url",
    "validate_target",
]

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
