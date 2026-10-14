"""Pipeline-specific configuration for the example_db dlt pipelines.

Shared infrastructure (Trino, Polaris, DuckDB paths, S3, target validation) lives in
``dlt_runner.config`` and is re-exported here so callers use a single import.
"""

from __future__ import annotations

import os

from dlt_runner.config import (
    VALID_TARGETS,
    configure_iceberg_env,
    duckdb_path,
    env,
    polaris_uri,
    s3_credentials,
    s3_endpoint,
    temp_bucket,
    trino_url,
    validate_target,
)

__all__ = [
    "VALID_TARGETS",
    "configure_iceberg_env",
    "duckdb_path",
    "env",
    "polaris_uri",
    "s3_credentials",
    "s3_endpoint",
    "temp_bucket",
    "trino_url",
    "validate_target",
]

# Medallion catalog -> Apache Polaris catalog name (matches the dbt Trino catalogs).
CATALOG_WAREHOUSES = {
    "bronze": "bronze",
    "silver": "silver",
    "gold": "gold",
    "test": "test",
}

# dbt-built tables exported to Postgres: (catalog, schema, table) -> target table name.
EXPORTS = {
    ("silver", "example_db", "automotive_raw"): "automotive_raw",
    ("gold", "example_db", "automotive_make_price_summary"): "automotive_make_price_summary",
    ("gold", "example_db", "automotive_fuel_body_mpg_summary"): "automotive_fuel_body_mpg_summary",
}

SOURCE_DEFAULT_URL = (
    "https://raw.githubusercontent.com/Opensourcefordatascience/"
    "Data-sets/refs/heads/master/automotive_data.csv"
)


def source_url() -> str:
    return env("EXAMPLE_DB_SOURCE_URL", SOURCE_DEFAULT_URL)


def export_duckdb_path() -> str:
    """Local stand-in for the Postgres export target."""
    default_dir = env("DBT_DUCKDB_DIR", "/tmp/duckdb")
    return env("DLT_EXPORT_DUCKDB_PATH", f"{default_dir}/export.duckdb")


def export_schema() -> str:
    return env("EXAMPLE_DB_SCHEMA", "public")


def postgres_dsn() -> str:
    """Build a SQLAlchemy/dlt Postgres DSN from the EXAMPLE_DB_* secrets.

    Accepts a ready DSN in ``EXAMPLE_DB_DSN`` or derives one from a JDBC ``EXAMPLE_DB_URL``
    (``jdbc:postgresql://host:port/db``) plus user/password.
    """
    dsn = env("EXAMPLE_DB_DSN")
    if dsn:
        return dsn

    url = os.environ["EXAMPLE_DB_URL"]
    user = os.environ["EXAMPLE_DB_USER"]
    password = env("EXAMPLE_DB_PASSWORD", "")
    host_db = url.split("//", 1)[1] if "//" in url else url
    return f"postgresql://{user}:{password}@{host_db}"
