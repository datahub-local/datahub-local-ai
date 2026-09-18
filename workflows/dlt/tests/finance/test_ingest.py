"""Local end-to-end test for the finance ingest pipeline.

Runs ``ingest.run("local")`` against a stubbed provider (unit tests in
``test_enablebanking.py`` cover the wire normalisation; here the contract under
test is the dlt pipeline itself): bronze destination, merge dispositions and
idempotent second runs. Uses tmp DuckDB - no warehouse, no network.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import duckdb
import pytest
from finance import ingest
from finance.providers.base import (
    Account,
    Balance,
    RateLimitError,
    TokenMissingError,
    Transaction,
)
from finance.providers.enablebanking import AccountConfig, TokenConfig


class _StubProvider:
    """The BankDataProvider surface with canned rows - no HTTP."""

    def __init__(self):
        self.accounts = {"stub_account": AccountConfig(
            alias="stub_account", iban="ES0000000000000000000000",
            app_id="00000000-0000-0000-0000-0000000000aa", institution_id="Sample Bank",
        )}
        self.tokens = {"stub_account": TokenConfig(alias="stub_account", uid="00000000-0000-0000-0000-000000000001")}

    def list_accounts(self):
        return [Account(
            account_id="stub_account", institution_id="Sample Bank",
            iban="ES0000000000000000000000", currency="EUR", owner_name="SAMPLE HOLDER",
            status="AUTHORIZED", payload_json="{}",
        )]

    def fetch_transactions(self, account_id, date_from, date_to):
        return [Transaction(
            account_id="stub_account", stable_id="STABLE1",
            booking_date=date(2026, 1, 15), value_date=None,
            amount=Decimal("-12.34"), currency="EUR", remittance_info="SAMPLE SHOP",
            creditor_name=None, debtor_name=None, creditor_iban=None, debtor_iban=None,
            bank_transaction_code=None, payload_json="{}",
        )]

    def fetch_balances(self, account_id):
        return [Balance(
            account_id="stub_account", balance_type="CLBD", amount=Decimal("100.00"),
            currency="EUR", reference_date=None, payload_json="{}",
        )]


class _UntokenizedProvider(_StubProvider):
    def __init__(self):
        super().__init__()
        self.tokens = {}


class _RateLimitedSecondAccountProvider(_StubProvider):
    """First account fetches fine, the second raises 429 (the Openbank case)."""

    def __init__(self):
        super().__init__()
        self.accounts = {
            **self.accounts,
            "stub_account_2": AccountConfig(
                alias="stub_account_2", iban="ES2222222222222222222222",
                app_id="00000000-0000-0000-0000-0000000000aa", institution_id="Sample Bank",
            ),
        }
        self.tokens = {
            **self.tokens,
            "stub_account_2": TokenConfig(
                alias="stub_account_2", uid="00000000-0000-0000-0000-000000000002",
            ),
        }

    def list_accounts(self):
        return super().list_accounts() + [Account(
            account_id="stub_account_2", institution_id="Sample Bank",
            iban="ES2222222222222222222222", currency="EUR", owner_name="SAMPLE HOLDER",
            status="AUTHORIZED", payload_json="{}",
        )]

    def fetch_transactions(self, account_id, date_from, date_to):
        if account_id == "stub_account_2":
            raise RateLimitError("stub 429 on the second account")
        return super().fetch_transactions(account_id, date_from, date_to)


def _run_ingest(tmp_path, monkeypatch, provider=None):
    monkeypatch.setenv("DBT_DUCKDB_DIR", str(tmp_path))
    # example_db's module-scoped fixture leaks DBT_DUCKDB_* into the process env
    # without a teardown; duckdb_path() honours those paths first, so drop them
    # and the _DIR default (this test's tmp file) is what gets loaded
    for name in ("DBT_DUCKDB_PATH", "DBT_DUCKDB_SILVER_PATH", "DBT_DUCKDB_GOLD_PATH"):
        monkeypatch.delenv(name, raising=False)
    # dlt journals pipeline state under its config folder keyed by pipeline name;
    # without isolation one test's state leaks into the next (same PIPELINE_NAME)
    monkeypatch.setenv("DLT_CONFIG_FOLDER", str(tmp_path / ".dlt-state"))
    # dlt caches open pipelines by name per process: give every test its own so the
    # destination is always this test's fresh DuckDB file (bodega's integration test
    # solves the same collision with a subprocess)
    monkeypatch.setattr(ingest, "PIPELINE_NAME", f"finance_ingest_{abs(hash(str(tmp_path))) % 10**10}")
    monkeypatch.delenv("FINANCE_FROM_DATE", raising=False)
    monkeypatch.delenv("FINANCE_TO_DATE", raising=False)
    monkeypatch.setattr(ingest.config, "enablebanking_provider", lambda: provider or _StubProvider())
    return ingest.run("local")


def _bronze_db(tmp_path):
    return tmp_path / "bronze.duckdb"


def _table_rows(tmp_path, table):
    con = duckdb.connect(str(_bronze_db(tmp_path)))
    try:
        return con.execute(f"SELECT COUNT(*) FROM bronze.finance.{table}").fetchone()[0]
    finally:
        con.close()


def test_run_lands_all_three_bronze_tables(tmp_path, monkeypatch):
    _run_ingest(tmp_path, monkeypatch)
    con = duckdb.connect(str(_bronze_db(tmp_path)))
    try:
        tables = {
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='finance'"
            ).fetchall()
            if not r[0].startswith("_dlt")
        }
    finally:
        con.close()
    assert tables == {"raw_transactions", "raw_accounts", "raw_balances"}


def test_transaction_rows_are_normalised(tmp_path, monkeypatch):
    _run_ingest(tmp_path, monkeypatch)
    con = duckdb.connect(str(_bronze_db(tmp_path)))
    try:
        rows = con.execute(
            "SELECT stable_id, amount, booking_date, provider, institution_id "
            "FROM bronze.finance.raw_transactions"
        ).fetchall()
    finally:
        con.close()
    # booking_date is stored as text (column hint); the decimal keeps its sign —
    # DBIT turns the row negative already at the adapter
    assert rows == [("STABLE1", Decimal("-12.34"), "2026-01-15", "enablebanking", "Sample Bank")]


def test_accounts_carry_stable_fields(tmp_path, monkeypatch):
    _run_ingest(tmp_path, monkeypatch)
    con = duckdb.connect(str(_bronze_db(tmp_path)))
    try:
        rows = con.execute(
            "SELECT account_id, owner_name, status FROM bronze.finance.raw_accounts"
        ).fetchall()
    finally:
        con.close()
    assert rows == [("stub_account", "SAMPLE HOLDER", "AUTHORIZED")]


def test_second_run_rewrites_without_duplicates(tmp_path, monkeypatch):
    _run_ingest(tmp_path, monkeypatch)
    _run_ingest(tmp_path, monkeypatch)
    # every table merges on its stable key, so a re-fetch rewrites the same rows
    assert _table_rows(tmp_path, "raw_transactions") == 1
    assert _table_rows(tmp_path, "raw_accounts") == 1
    # balances merge on (account, type, reference_date): a NULL reference_date
    # falls back to the ingestion date, so a same-day re-run is one snapshot
    assert _table_rows(tmp_path, "raw_balances") == 1


def test_longest_omits_the_date_window(tmp_path, monkeypatch):
    # longest treats date_from as a lower border and ignores date_to, so sending
    # the 4-week window would cap the history instead of extending it
    assert ingest._fetch_window("longest") == (None, None)
    from_date, to_date = ingest._fetch_window("default")
    assert from_date is not None and to_date is not None


def test_rate_limited_account_keeps_the_rows_already_loaded(tmp_path, monkeypatch):
    # per-account loading: the first account is written before the second 429s,
    # so a mid-fleet rate limit leaves partial data instead of discarding all
    with pytest.raises(RateLimitError, match="second account"):
        _run_ingest(tmp_path, monkeypatch, provider=_RateLimitedSecondAccountProvider())
    assert _table_rows(tmp_path, "raw_transactions") == 1
    assert _table_rows(tmp_path, "raw_accounts") == 2


def test_untokenized_account_fails_before_any_data_call(tmp_path, monkeypatch):
    monkeypatch.setenv("DBT_DUCKDB_DIR", str(tmp_path))
    monkeypatch.setattr(ingest.config, "enablebanking_provider", lambda: _UntokenizedProvider())
    with pytest.raises(TokenMissingError, match="finance-enablebanking-token"):
        ingest.run("local")
    assert not _bronze_db(tmp_path).exists()
