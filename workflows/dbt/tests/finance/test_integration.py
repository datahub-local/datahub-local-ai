"""Integration test: run the finance pipeline against the local (DuckDB) target.

Seeds the bronze tables the dlt ingest would produce plus the enrich-owned
merchant_categories, runs `dbt build` against DuckDB (one file per medallion
catalog), then asserts the materialized silver and gold tables. No external
services - slower than the structural tests, so it is kept separate.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).parent.parent.parent / "projects" / "finance"

TRANSACTIONS_COLUMNS = [
    "provider", "account_id", "stable_id", "booking_date", "value_date", "amount", "currency",
    "remittance_info", "creditor_name", "debtor_name", "creditor_iban", "debtor_iban",
    "bank_transaction_code", "institution_id", "payload_json", "_ingested_at",
]
TRANSACTION_ROWS = [
    # categorised debit: creditor name wins as payee
    ("enablebanking", "acct_a", "S1", "2026-01-15", "2026-01-14", -12.34, "EUR",
     "SAMPLE SHOP", "Sample Shop SL", None, None, "ES0000000000000000000000", None,
     "Openbank", "{}", "2026-01-16T06:00:00+00:00"),
    # inflow: falls back to the debtor name
    ("enablebanking", "acct_a", "S2", "2026-01-20", None, 100.00, "EUR",
     "SALARY", None, "Sample Employer", None, "ES1111111111111111111111", None,
     "Openbank", "{}", "2026-01-21T06:00:00+00:00"),
    # uncategorised payee: remittance text, with a whitespace run to collapse
    ("enablebanking", "acct_a", "S3", "2026-02-02", None, -5.00, "EUR",
     "ACME  UNKNOWN", None, None, None, None, None,
     "Openbank", "{}", "2026-02-03T06:00:00+00:00"),
]
ACCOUNTS_COLUMNS = [
    "provider", "account_id", "institution_id", "iban", "currency", "owner_name", "status",
    "payload_json", "_ingested_at",
]
ACCOUNT_ROWS = [
    ("enablebanking", "acct_a", "Openbank", "ES0000000000000000000000", "EUR",
     "SAMPLE HOLDER", "AUTHORIZED", "{}", "2026-01-16T06:00:00+00:00"),
]
BALANCES_COLUMNS = [
    "account_id", "balance_type", "amount", "currency", "reference_date", "_ingested_at",
]
BALANCE_ROWS = [
    # two snapshots for the same day: the newer must win
    ("acct_a", "CLBD", 90.00, "EUR", "2026-01-31", "2026-02-01T06:00:00+00:00"),
    ("acct_a", "CLBD", 100.00, "EUR", "2026-01-31", "2026-02-02T06:00:00+00:00"),
    # NULL reference_date: falls back to the ingestion date
    ("acct_a", "CLBD", 110.00, "EUR", None, "2026-02-03T06:00:00+00:00"),
]
CATEGORY_ROWS = [
    ("SAMPLE SHOP SL", "SHOPPING", "RETAIL", "Openbank", "2026-01-01T00:00:00+00:00"),
]


def _seed(connect, schema, table, column_types, rows):
    connect.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    cols = ", ".join(f'"{c}" {t}' for c, t in column_types.items())
    connect.execute(f"CREATE OR REPLACE TABLE {schema}.{table} ({cols})")
    placeholders = ", ".join("?" for _ in column_types)
    connect.executemany(f"INSERT INTO {schema}.{table} VALUES ({placeholders})", rows)


def _types(columns, overrides=None):
    return {c: (overrides or {}).get(c, "VARCHAR") for c in columns}


@pytest.fixture(scope="module")
def warehouse(tmp_path_factory):
    import duckdb

    tmp = tmp_path_factory.mktemp("finance_dbt_integration")
    paths = {
        "DBT_DUCKDB_PATH": str(tmp / "bronze.duckdb"),
        "DBT_DUCKDB_SILVER_PATH": str(tmp / "silver.duckdb"),
        "DBT_DUCKDB_GOLD_PATH": str(tmp / "gold.duckdb"),
    }
    saved = {name: os.environ.get(name) for name in paths}
    os.environ.update(paths)

    bronze = duckdb.connect(paths["DBT_DUCKDB_PATH"])
    _seed(bronze, "finance", "raw_transactions",
          _types(TRANSACTIONS_COLUMNS, {"amount": "DECIMAL(18, 2)"}), TRANSACTION_ROWS)
    _seed(bronze, "finance", "raw_accounts", _types(ACCOUNTS_COLUMNS), ACCOUNT_ROWS)
    _seed(bronze, "finance", "raw_balances",
          _types(BALANCES_COLUMNS, {"amount": "DECIMAL(18, 2)"}), BALANCE_ROWS)
    bronze.close()

    # The enrich-owned dimension the gold model reads from the silver catalog.
    silver = duckdb.connect(paths["DBT_DUCKDB_SILVER_PATH"])
    _seed(silver, "finance", "merchant_categories",
          _types(["payee_clean", "category", "subcategory", "first_seen_institution", "categorized_at"]),
          CATEGORY_ROWS)
    silver.close()

    # Run dbt in a subprocess so its DuckDB instance is gone before verification —
    # avoids DuckDB's per-process "file already attached" conflicts when re-opening.
    proc = subprocess.run(
        [sys.executable, "-m", "dbt_runner", "--project", "finance",
         "--target", "local", "--full-refresh"],
        cwd=PROJECT_DIR.parent.parent,
        env={**os.environ},
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    yield paths

    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


@pytest.fixture(scope="module")
def con(warehouse):
    import duckdb

    verify = duckdb.connect(warehouse["DBT_DUCKDB_PATH"], read_only=True)
    verify.execute(f"ATTACH '{warehouse['DBT_DUCKDB_SILVER_PATH']}' AS silver (READ_ONLY)")
    verify.execute(f"ATTACH '{warehouse['DBT_DUCKDB_GOLD_PATH']}' AS gold (READ_ONLY)")
    yield verify
    verify.close()


class TestSilver:
    def test_transactions_typed_and_signed(self, con):
        rows = con.execute(
            "SELECT stable_id, booking_date, amount, direction, currency "
            "FROM silver.finance.transactions ORDER BY stable_id"
        ).fetchall()
        assert [(r[0], str(r[1]), float(r[2])) for r in rows] == [
            ("S1", "2026-01-15", -12.34), ("S2", "2026-01-20", 100.0), ("S3", "2026-02-02", -5.0),
        ]
        assert [r[3] for r in rows] == ["outflow", "inflow", "outflow"]

    def test_payee_precedence_and_cleaning(self, con):
        payees = dict(con.execute(
            "SELECT stable_id, payee_clean FROM silver.finance.transactions"
        ).fetchall())
        assert payees["S1"] == "SAMPLE SHOP SL"     # creditor name, uppercased
        assert payees["S2"] == "SAMPLE EMPLOYER"    # debtor name fallback
        assert payees["S3"] == "ACME UNKNOWN"       # remittance, whitespace collapsed

    def test_account_iban_is_masked_and_joined(self, con):
        row = con.execute(
            "SELECT DISTINCT iban_masked FROM silver.finance.transactions"
        ).fetchall()
        assert row == [("****0000",)]

    def test_balances_latest_snapshot_wins(self, con):
        rows = con.execute(
            "SELECT balance_date, amount FROM silver.finance.balances ORDER BY balance_date"
        ).fetchall()
        assert [(str(r[0]), float(r[1])) for r in rows] == [("2026-01-31", 100.0), ("2026-02-03", 110.0)]

    def test_accounts_masked(self, con):
        row = con.execute("SELECT iban_masked, institution_id FROM silver.finance.accounts").fetchone()
        assert row == ("****0000", "Openbank")


class TestGold:
    def test_monthly_spend_keeps_the_uncategorised_sentinel(self, con):
        rows = con.execute(
            "SELECT category, direction, amount, transaction_count "
            "FROM gold.finance.monthly_category_spend ORDER BY category, direction"
        ).fetchall()
        normalised = [(c, d, float(a), n) for c, d, a, n in rows]
        assert ("SHOPPING", "outflow", 12.34, 1) in normalised
        # the payee the LLM has not seen stays in the total instead of vanishing
        assert ("UNCATEGORISED", "inflow", 100.0, 1) in normalised
        assert ("UNCATEGORISED", "outflow", 5.0, 1) in normalised

    def test_monthly_spend_is_magnitudes_not_signed(self, con):
        total = con.execute(
            "SELECT MIN(amount) FROM gold.finance.monthly_category_spend"
        ).fetchone()[0]
        assert total >= 0

    def test_balance_series_is_labelled(self, con):
        rows = con.execute(
            "SELECT balance_date, amount, iban_masked, institution_id "
            "FROM gold.finance.account_balance_series ORDER BY balance_date"
        ).fetchall()
        assert [(str(r[0]), float(r[1]), r[2], r[3]) for r in rows] == [
            ("2026-01-31", 100.0, "****0000", "Openbank"),
            ("2026-02-03", 110.0, "****0000", "Openbank"),
        ]
