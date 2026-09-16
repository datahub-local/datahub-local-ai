"""Pipeline-specific configuration for the finance dlt pipelines.

Shared infrastructure (Trino, Polaris, DuckDB paths, S3, target validation)
lives in ``dlt_runner.config`` and is re-exported here so callers use a single
import, exactly like ``bodega.config``.

Two Secrets feed the provider (spec 005 §4.7):

- ``finance-enablebanking`` (stable)  -> ``ENABLEBANKING_ACCOUNTS``
- ``finance-enablebanking-token`` (dynamic, renewal-owned) -> ``ENABLEBANKING_TOKENS``
"""

from __future__ import annotations

import json
import os
from datetime import datetime

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

from .providers.enablebanking import AccountConfig, EnableBankingProvider, TokenConfig

ENABLEBANKING_BASE_URL_DEFAULT = "https://api.enablebanking.com"


def enablebanking_base_url() -> str:
    return env("ENABLEBANKING_BASE_URL", ENABLEBANKING_BASE_URL_DEFAULT)


def enablebanking_private_key() -> str:
    """The shared RSA private key: ``ENABLEBANKING_PRIVATE_KEY`` (PEM text) or
    ``ENABLEBANKING_PRIVATE_KEY_FILE`` (path), the latter matching what the
    Control Panel hands the operator at registration."""
    pem = env("ENABLEBANKING_PRIVATE_KEY")
    if pem:
        return pem
    path = os.environ["ENABLEBANKING_PRIVATE_KEY_FILE"]
    with open(path) as handle:
        return handle.read().strip()


def enablebanking_accounts() -> list[AccountConfig]:
    """Stable bindings from ``ENABLEBANKING_ACCOUNTS`` (JSON).

    Shape — the ``accounts.json`` key of the ``finance-enablebanking`` secret::

        {"alias": {"iban": ..., "app_id": ..., "institution_id": ...}}
    """
    return [
        AccountConfig(
            alias=alias,
            iban=config["iban"],
            app_id=config["app_id"],
            institution_id=config.get("institution_id"),
        )
        for alias, config in json.loads(os.environ["ENABLEBANKING_ACCOUNTS"]).items()
    ]


def enablebanking_tokens() -> list[TokenConfig]:
    """Session tokens from ``ENABLEBANKING_TOKENS`` (JSON, optional).

    Shape — the ``tokens.json`` key of ``finance-enablebanking-token``::

        {"alias": {"uid": ..., "valid_until": ...}}

    The Secret is maintained **dynamically** by the n8n renewal workflow (spec
    005 §4.2.1) and may legitimately be absent: a missing or empty value means
    "no tokens yet", which the provider reports per account as a loud, named
    ``TokenMissingError`` — never as a silent zero-row success.
    """
    raw = env("ENABLEBANKING_TOKENS")
    if not raw:
        return []
    return [
        TokenConfig(
            alias=alias,
            uid=config["uid"],
            valid_until=_parse_valid_until(config.get("valid_until")),
        )
        for alias, config in json.loads(raw).items()
    ]


def _parse_valid_until(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def enablebanking_provider() -> EnableBankingProvider:
    return EnableBankingProvider(
        private_key=enablebanking_private_key(),
        accounts=enablebanking_accounts(),
        tokens=enablebanking_tokens(),
        base_url=enablebanking_base_url(),
        strategy=fetch_strategy(),
    )


def fetch_strategy() -> str:
    """``longest`` on a backfill run, ``default`` for the daily window (§4.1)."""
    return env("FINANCE_FETCH_STRATEGY", "default")


def payee_language() -> str:
    """Language of the raw payee text fed to the enrich LLM prompt."""
    return env("FINANCE_PAYEE_LANGUAGE", "Spanish")


def ingest_from_date() -> str | None:
    """Start (inclusive) of the transaction window, if scoped."""
    return env("FINANCE_FROM_DATE")


def ingest_to_date() -> str | None:
    """End (inclusive) of the transaction window, if scoped."""
    return env("FINANCE_TO_DATE")
