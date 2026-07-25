"""Shared, env-driven configuration for all dlt pipelines.

The two targets mirror the dbt project:
- ``homelab`` — Iceberg tables over Apache Polaris REST + S3 (Garage); Postgres for export.
- ``local``   — DuckDB files (shared with the dbt local target).
"""

from __future__ import annotations

import os

# DuckDB file per catalog for the local target (same env vars the dbt local profile uses).
_DUCKDB_ENV = {
    "bronze": "DBT_DUCKDB_PATH",
    "silver": "DBT_DUCKDB_SILVER_PATH",
    "gold": "DBT_DUCKDB_GOLD_PATH",
    "test": "DBT_DUCKDB_PI_PATH",
}

VALID_TARGETS = ("homelab", "local")


def validate_target(target: str) -> None:
    if target not in VALID_TARGETS:
        raise ValueError(f"unknown target: {target!r}")


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, default)
    return value if value not in (None, "") else default


def temp_bucket() -> str:
    """S3 bucket dlt stages temporal (parquet) datasets in before the Iceberg commit."""
    return env("DLT_TEMP_BUCKET", "datahub-local-temp")


def bronze_bucket() -> str:
    """S3 bucket for the bronze medallion layer (must match Polaris allowed locations)."""
    return env("DLT_BRONZE_BUCKET", "datahub-local-bronze")


def silver_bucket() -> str:
    """S3 bucket for the silver medallion layer (must match Polaris allowed locations)."""
    return env("DLT_SILVER_BUCKET", "datahub-local-silver")


def duckdb_path(catalog: str) -> str:
    default_dir = env("DBT_DUCKDB_DIR", "/tmp/duckdb")
    return env(_DUCKDB_ENV[catalog], f"{default_dir}/{catalog}.duckdb")


def polaris_uri() -> str:
    return env("ICEBERG_CATALOG_URI", "http://datahub-local-core-data-polaris:8181/api/catalog")


def s3_endpoint() -> str:
    return env("S3_ENDPOINT", "http://datahub-local-core-data-garage:3900")


def s3_credentials() -> dict:
    """AWS credentials dict for dlt's filesystem destination (maps S3_ACCESS_KEY/S3_SECRET_KEY)."""
    return {
        "aws_access_key_id": env("S3_ACCESS_KEY", ""),
        "aws_secret_access_key": env("S3_SECRET_KEY", ""),
        "endpoint_url": s3_endpoint(),
    }


def configure_iceberg_env(catalog: str, warehouse: str | None = None) -> None:
    """Wire pyiceberg's REST catalog + S3 config (read by dlt's filesystem-iceberg path).

    pyiceberg resolves a catalog named ``catalog`` from ``PYICEBERG_CATALOG__<name>__*``
    env vars (see https://py.iceberg.apache.org/configuration/). ``warehouse`` is the
    Apache Polaris catalog name; defaults to ``catalog`` when they share the same name.

    Auth (required by Apache Polaris): set ``POLARIS_CREDENTIAL`` (``client_id:client_secret``
    for OAuth2 client-credentials flow) or ``POLARIS_TOKEN`` (pre-fetched bearer token).
    """
    if warehouse is None:
        warehouse = catalog
    # dlt's filesystem-iceberg path resolves the catalog name from the ``iceberg_catalog``
    # config section (default ``"default"``). Point it at the per-layer name so it loads the
    # PYICEBERG_CATALOG__<CATALOG>__* vars below instead of looking for a "default" catalog.
    os.environ.setdefault("ICEBERG_CATALOG__ICEBERG_CATALOG_NAME", catalog)
    prefix = f"PYICEBERG_CATALOG__{catalog.upper()}__"
    defaults = {
        f"{prefix}TYPE": "rest",
        f"{prefix}URI": polaris_uri(),
        f"{prefix}WAREHOUSE": warehouse,
        f"{prefix}S3__ENDPOINT": s3_endpoint(),
        f"{prefix}S3__ACCESS_KEY_ID": env("S3_ACCESS_KEY", ""),
        f"{prefix}S3__SECRET_ACCESS_KEY": env("S3_SECRET_KEY", ""),
        f"{prefix}S3__PATH_STYLE_ACCESS": "true",
        f"{prefix}S3__REMOTE_SIGNING_ENABLED": "false",
        # pyiceberg's REST catalog always requests vended credentials by default
        # (see pyiceberg.catalog.rest.RestCatalog._config_headers). Polaris can't vend
        # credentials for a self-hosted S3-compatible store like Garage, so disable the
        # request and let pyiceberg fall back to the static S3 creds configured above.
        f"{prefix}HEADER__X-ICEBERG-ACCESS-DELEGATION": "",
    }
    defaults[f"{prefix}SCOPE"] = "PRINCIPAL_ROLE:ALL"
    client_id = env("POLARIS_CLIENT_ID")
    client_secret = env("POLARIS_CLIENT_SECRET")
    credential = env("POLARIS_CREDENTIAL") or (
        f"{client_id}:{client_secret}" if client_id and client_secret else None
    )
    if credential:
        defaults[f"{prefix}CREDENTIAL"] = credential
    elif token := env("POLARIS_TOKEN"):
        defaults[f"{prefix}TOKEN"] = token
    for key, value in defaults.items():
        os.environ.setdefault(key, value)


def trino_url() -> str:
    host = env("TRINO_HOST", "datahub-local-core-data-trino-trino")
    port = env("TRINO_PORT", "8080")
    user = env("TRINO_USER", "dbt")
    return f"trino://{user}@{host}:{port}"


def llm_provider() -> str:
    """LLM provider to use for enrichment. Values: 'openrouter' or 'ollama' (default)."""
    return env("LLM_PROVIDER", "openrouter")


def openrouter_api_key() -> str:
    return os.environ["OPENROUTER_API_KEY"]


def openrouter_model() -> str:
    return env("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash:nitro")


def ollama_base_url() -> str:
    return env("OLLAMA_BASE_URL", "http://datahub-local-core-data-ollama:11434/v1")


def ollama_model() -> str:
    return env("OLLAMA_MODEL", "gemma3:4b-it-qat")


def llm_settings() -> tuple[str, str, str]:
    """Return (base_url, api_key, model_id) for the configured LLM provider."""
    provider = llm_provider()
    if provider == "ollama":
        return ollama_base_url(), "", ollama_model()
    return "https://openrouter.ai/api/v1", openrouter_api_key(), openrouter_model()


def llm_timeout() -> float:
    """Timeout in seconds for LLM chat-completion requests."""
    return float(env("LLM_TIMEOUT_SECONDS", "300"))
