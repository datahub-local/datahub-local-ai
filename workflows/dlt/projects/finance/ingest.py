"""Ingest step: land Enable Banking account data into the bronze medallion layer.

Calls the Enable Banking provider adapter (the only wire-format-aware code) and
lands three tables in ``bronze.finance`` (spec 005 §4.3):

- ``raw_transactions`` — merge on ``(provider, account_id, stable_id)``; only
  booked rows (the adapter filters), no stale-row deletion: a transaction that
  vanishes from the bank stays in bronze, the lake is the longer memory.
- ``raw_accounts`` — merge on ``(provider, account_id)``.
- ``raw_balances`` — merge on ``(account_id, balance_type, reference_date)``,
  where a NULL ``reference_date`` falls back to the ingestion date: one snapshot
  per balance type per day, so a re-run rewrites rather than appends.

The default fetch strategy is ``longest`` (spec 005 §4.1): each run re-reads the
full history the ASPSP will return, and every table merges on its stable key, so
re-fetching is idempotent and a run adds no duplicates.

- ``local``   → DuckDB file (the same ``bronze.duckdb`` the dbt local target reads).
- ``homelab`` → Iceberg table via Apache Polaris REST + S3.

Failure contract (goal 6): a missing/expired session token fails the run
**before any data call**, naming the alias and the renewal path — never a
silent zero-row success.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

import dlt

from finance.providers.base import (
    AccessExpiredError,
    BankDataProvider,
    TokenMissingError,
)

from . import config

PIPELINE_NAME = "finance_ingest"
DATASET_NAME = "finance"
PROVIDER = "enablebanking"
TABLE_TRANSACTIONS = "raw_transactions"
TABLE_ACCOUNTS = "raw_accounts"
TABLE_BALANCES = "raw_balances"
DEFAULT_LOOKBACK_DAYS = 14

logger = logging.getLogger(__name__)


def _window() -> tuple[date, date]:
    """``[from_date, to_date]`` inclusive; defaults to a 14-day lookback (§4.3)."""
    from_date = config.ingest_from_date()
    to_date = config.ingest_to_date()
    if from_date is None:
        from_date = (datetime.now(UTC).date() - timedelta(days=DEFAULT_LOOKBACK_DAYS - 1)).isoformat()
    if to_date is None:
        to_date = datetime.now(UTC).date().isoformat()
    return date.fromisoformat(from_date), date.fromisoformat(to_date)


def _fetch_window(strategy: str) -> tuple[date | None, date | None]:
    """Dates sent to the provider for ``strategy``.

    ``longest`` sends none: ``date_to`` is ignored and ``date_from`` is only a
    lower border, so any window would cap the history instead of extending it
    (spec 005 §4.1). The explicit window is for the ``default`` strategy.
    """
    if strategy == "longest":
        return None, None
    return _window()


def _preflight(provider: BankDataProvider) -> None:
    """Fail before any data call when a session is unusable (goal 6).

    A configured account without a token is the same failure class as an
    expired one: the renewal workflow may not have created the token Secret
    yet, and running against a partial fleet would silently drop an account.
    """
    for alias, token in provider.tokens.items():
        if token.consent_expired():
            raise AccessExpiredError(
                f"{alias}: consent for {provider.accounts[alias].institution_id or alias} "
                f"expired at {token.valid_until.isoformat()}; "
                "renew via the n8n workflow or finance.onboard"
            )
    untokenized = sorted(set(provider.accounts) - set(provider.tokens))
    if untokenized:
        raise TokenMissingError(
            f"{', '.join(untokenized)}: no session token in finance-enablebanking-token "
            "(the Secret may not exist yet); renew via the n8n workflow or finance.onboard session"
        )


def _transaction_row(txn, institution_id: str, ingested_at: str) -> dict:
    return {
        "provider": PROVIDER,
        "account_id": txn.account_id,
        "stable_id": txn.stable_id,
        "booking_date": txn.booking_date.isoformat(),
        "value_date": txn.value_date.isoformat() if txn.value_date else None,
        "amount": txn.amount,
        "currency": txn.currency,
        "remittance_info": txn.remittance_info,
        "creditor_name": txn.creditor_name,
        "debtor_name": txn.debtor_name,
        "creditor_iban": txn.creditor_iban,
        "debtor_iban": txn.debtor_iban,
        "bank_transaction_code": txn.bank_transaction_code,
        "institution_id": institution_id,
        "payload_json": txn.payload_json,
        "_ingested_at": ingested_at,
    }


def _account_row(account, ingested_at: str) -> dict:
    return {
        "provider": PROVIDER,
        "account_id": account.account_id,
        "institution_id": account.institution_id,
        "iban": account.iban,
        "currency": account.currency,
        "owner_name": account.owner_name,
        "status": account.status,
        "payload_json": account.payload_json,
        "_ingested_at": ingested_at,
    }


def _balance_row(balance, ingested_at: str) -> dict:
    return {
        "account_id": balance.account_id,
        "balance_type": balance.balance_type,
        "amount": balance.amount,
        "currency": balance.currency,
        "reference_date": (
            balance.reference_date.isoformat() if balance.reference_date else ingested_at[:10]
        ),
        "_ingested_at": ingested_at,
    }


@dlt.resource(
    name=TABLE_TRANSACTIONS,
    write_disposition="merge",
    primary_key=["provider", "account_id", "stable_id"],

    # dlt only materialises a column that saw a value; a run whose rows all had a
    # NULL counterparty would otherwise ship a table missing that column entirely,
    # and Silver's CAST on it would fail. Every column is therefore declared.
    columns={
        "provider": {"data_type": "text"},
        "account_id": {"data_type": "text"},
        "stable_id": {"data_type": "text"},
        "institution_id": {"data_type": "text"},
        "booking_date": {"data_type": "text"},
        "value_date": {"data_type": "text"},
        "amount": {"data_type": "decimal"},
        "currency": {"data_type": "text"},
        "remittance_info": {"data_type": "text"},
        "creditor_name": {"data_type": "text"},
        "debtor_name": {"data_type": "text"},
        "creditor_iban": {"data_type": "text"},
        "debtor_iban": {"data_type": "text"},
        "bank_transaction_code": {"data_type": "text"},
        "payload_json": {"data_type": "text"},
        "_ingested_at": {"data_type": "text"},
    },
)
def raw_transactions(rows):
    yield from rows


@dlt.resource(
    name=TABLE_ACCOUNTS,
    write_disposition="merge",
    primary_key=["provider", "account_id"],
    columns={
        "provider": {"data_type": "text"},
        "account_id": {"data_type": "text"},
        "institution_id": {"data_type": "text"},
        "iban": {"data_type": "text"},
        "currency": {"data_type": "text"},
        "owner_name": {"data_type": "text"},
        "status": {"data_type": "text"},
        "payload_json": {"data_type": "text"},
        "_ingested_at": {"data_type": "text"},
    },
)
def raw_accounts(rows):
    yield from rows


@dlt.resource(
    name=TABLE_BALANCES,
    write_disposition="merge",
    primary_key=["account_id", "balance_type", "reference_date"],
    columns={
        "account_id": {"data_type": "text"},
        "balance_type": {"data_type": "text"},
        "amount": {"data_type": "decimal"},
        "currency": {"data_type": "text"},
        "reference_date": {"data_type": "text"},
        "_ingested_at": {"data_type": "text"},
    },
)
def raw_balances(rows):
    yield from rows


def run(target: str) -> dict[str, int]:
    config.validate_target(target)
    provider = config.enablebanking_provider()
    _preflight(provider)

    strategy = config.fetch_strategy()
    from_date, to_date = _fetch_window(strategy)
    ingested_at = datetime.now(UTC).isoformat()
    institutions = {
        alias: (account.institution_id or alias) for alias, account in provider.accounts.items()
    }

    transaction_rows = [
        _transaction_row(txn, institutions[alias], ingested_at)
        for alias in sorted(provider.accounts)
        for txn in provider.fetch_transactions(alias, from_date, to_date)
    ]
    account_rows = [_account_row(account, ingested_at) for account in provider.list_accounts()]
    balance_rows = [
        _balance_row(balance, ingested_at)
        for alias in sorted(provider.accounts)
        for balance in provider.fetch_balances(alias)
    ]

    if target == "homelab":
        config.configure_iceberg_env("bronze")
        destination = dlt.destinations.filesystem(
            bucket_url=f"s3://{config.bronze_bucket()}",
            credentials=config.s3_credentials(),
        )
    else:
        destination = dlt.destinations.duckdb(config.duckdb_path("bronze"))

    pipeline = dlt.pipeline(pipeline_name=PIPELINE_NAME, destination=destination, dataset_name=DATASET_NAME)
    resource_for = {"raw_transactions": raw_transactions, "raw_accounts": raw_accounts, "raw_balances": raw_balances}
    counts: dict[str, int] = {}
    for table, rows in (
        (TABLE_TRANSACTIONS, transaction_rows),
        (TABLE_ACCOUNTS, account_rows),
        (TABLE_BALANCES, balance_rows),
    ):
        resource = resource_for[table](rows)
        if target == "homelab":
            resource.apply_hints(table_format="iceberg")
        load_info = pipeline.run(resource)
        row_counts = pipeline.last_trace.last_normalize_info.row_counts
        counts[table] = int(row_counts.get(table, 0) or 0)
        logger.info("%s: %s load %s rows=%s", PIPELINE_NAME, table, load_info, counts[table])

    logger.info(
        "%s: strategy=%s window=[%s..%s] accounts=%s row counts=%s",
        PIPELINE_NAME, strategy, from_date, to_date, sorted(institutions), counts,
    )
    return counts
