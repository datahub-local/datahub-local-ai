"""Tests for the Actual Budget sync pipeline.

No real Actual server and no actualpy call: the budget is a fake that records
what was created and what was committed, and the silver read is either a tmp
DuckDB file or a patched reader. The contract under test is dedup on
``imported_id``, the seeding of categories/payees/rules from the lake's
``merchant_categories``, fail-on-unmapped and the local dry-run default.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal

import duckdb
import pytest
from finance import sync
from finance.sync import ActualAccountMapError, ActualSettings, _sync


class _FakeBudget:
    def __init__(self, existing=None, uncategorised=None, reconciled=0):
        self.existing = set(existing or [])
        self.uncategorised_rows = list(uncategorised or [])
        self.reconciled = reconciled
        self.reconcile_calls = []
        self.created = []
        self.ensured = []
        self.categories = []
        self.payees = []
        self.rules = []
        self.ruled = []
        self.committed = False

    def existing_imported_ids(self):
        return set(self.existing)

    def reconcile_payees(self, rows):
        self.reconcile_calls.append(list(rows))
        return self.reconciled

    def ensure_account(self, name):
        self.ensured.append(name)

    def ensure_category(self, name, *, group, is_income=False):
        self.categories.append({"name": name, "group": group, "is_income": is_income})
        return f"cat:{name}"

    def ensure_payee(self, name):
        self.payees.append(name)
        return f"payee:{name}"

    def ensure_rule(self, key, *, payee_id, category_id, inflow, stage):
        self.rules.append(
            {
                "key": key,
                "payee_id": payee_id,
                "category_id": category_id,
                "inflow": inflow,
                "stage": stage,
            }
        )

    def uncategorised(self):
        return list(self.uncategorised_rows)

    def create(self, **kwargs):
        self.created.append(kwargs)
        return kwargs

    def run_rules(self, transactions):
        self.ruled.append(list(transactions))

    def commit(self):
        self.committed = True


@contextmanager
def _fake_factory(budget):
    yield budget


def _rows(*specs):
    return [
        {
            "account_id": account_id,
            "stable_id": stable_id,
            "booking_date": booking_date,
            "payee": payee,
            "payee_clean": payee_clean,
            "amount": Decimal(amount),
            "remittance_info": remittance,
        }
        for account_id, stable_id, booking_date, payee, payee_clean, amount, remittance in specs
    ]


def _categories(*pairs):
    return [{"payee_clean": payee, "category": category} for payee, category in pairs]


_SETTINGS = ActualSettings(base_url="http://actual.example", password="pw", file="budget")


def _run_sync(rows, categories, budget, account_map=None, dry_run=False):
    return _sync(
        rows,
        categories,
        account_map if account_map is not None else {"alias": "My account"},
        _SETTINGS,
        dry_run=dry_run,
        client_factory=lambda s: _fake_factory(budget),
    )


class TestWindow:
    def test_defaults_to_60_day_lookback(self, monkeypatch):
        for name in ("FINANCE_SYNC_FROM_DATE", "FINANCE_SYNC_TO_DATE", "FINANCE_SYNC_WINDOW_DAYS"):
            monkeypatch.delenv(name, raising=False)
        from_date, to_date = sync._window()
        assert to_date - from_date == timedelta(days=59)

    def test_window_days_env(self, monkeypatch):
        monkeypatch.delenv("FINANCE_SYNC_FROM_DATE", raising=False)
        monkeypatch.delenv("FINANCE_SYNC_TO_DATE", raising=False)
        monkeypatch.setenv("FINANCE_SYNC_WINDOW_DAYS", "10")
        from_date, to_date = sync._window()
        assert to_date - from_date == timedelta(days=9)

    def test_explicit_dates_win(self, monkeypatch):
        monkeypatch.setenv("FINANCE_SYNC_FROM_DATE", "2024-01-01")
        monkeypatch.setenv("FINANCE_SYNC_TO_DATE", "2024-01-31")
        assert sync._window() == (date(2024, 1, 1), date(2024, 1, 31))


class TestReadTransactionsLocal:
    def _write_silver(self, tmp_path, rows):
        db = tmp_path / "silver.duckdb"
        con = duckdb.connect(str(db))
        con.execute("CREATE SCHEMA finance")
        con.execute(
            "CREATE TABLE finance.transactions ("
            "account_id VARCHAR, stable_id VARCHAR, booking_date DATE, payee VARCHAR, "
            "payee_clean VARCHAR, amount DECIMAL(18,2), remittance_info VARCHAR)"
        )
        for account_id, stable_id, booking_date, payee, payee_clean, amount, remittance in rows:
            con.execute(
                "INSERT INTO finance.transactions VALUES (?, ?, ?, ?, ?, ?, ?)",
                [account_id, stable_id, date.fromisoformat(booking_date), payee, payee_clean, Decimal(amount), remittance],
            )
        con.close()
        return db

    def test_returns_only_rows_in_window(self, tmp_path):
        db = self._write_silver(
            tmp_path,
            [
                ("alias", "IN", "2024-01-15", "SHOP", "SHOP", "-12.34", "card"),
                ("alias", "OUT", "2023-12-01", "OLD", "OLD", "-1.00", None),
            ],
        )
        rows = sync._read_transactions_local(str(db), date(2024, 1, 1), date(2024, 1, 31))
        assert [r["stable_id"] for r in rows] == ["IN"]
        assert rows[0]["amount"] == Decimal("-12.34")
        assert rows[0]["payee_clean"] == "SHOP"

    def test_missing_table_is_empty(self, tmp_path):
        db = tmp_path / "silver.duckdb"
        duckdb.connect(str(db)).close()
        assert sync._read_transactions_local(str(db), date(2024, 1, 1), date(2024, 1, 31)) == []


class TestReadCategoriesLocal:
    def test_returns_merchants_skipping_parse_errors(self, tmp_path):
        db = tmp_path / "silver.duckdb"
        con = duckdb.connect(str(db))
        con.execute("CREATE SCHEMA finance")
        con.execute(
            "CREATE TABLE finance.merchant_categories ("
            "payee_clean VARCHAR, category VARCHAR, subcategory VARCHAR)"
        )
        con.execute("INSERT INTO finance.merchant_categories VALUES ('MERCADONA', 'GROCERIES', 'Supermarket')")
        con.execute("INSERT INTO finance.merchant_categories VALUES ('BROKEN', 'OTHER', 'PARSE_ERROR')")
        con.close()
        assert sync._read_categories_local(str(db)) == [
            {"payee_clean": "MERCADONA", "category": "GROCERIES"}
        ]

    def test_missing_table_is_empty(self, tmp_path):
        db = tmp_path / "silver.duckdb"
        duckdb.connect(str(db)).close()
        assert sync._read_categories_local(str(db)) == []


class TestSync:
    def test_creates_only_rows_not_already_imported(self):
        rows = _rows(
            ("alias", "S1", date(2024, 1, 1), "SHOP A", "SHOP A", "-10.00", "card"),
            ("alias", "S2", date(2024, 1, 2), "SHOP B", "SHOP B", "-20.00", "card"),
        )
        budget = _FakeBudget(existing={"enablebanking:S1"})
        counts = _run_sync(rows, [], budget)
        assert counts == {"read": 2, "added": 1, "skipped": 1, "reconciled": 0, "committed": True}
        assert [c["imported_id"] for c in budget.created] == ["enablebanking:S2"]
        assert budget.committed is True

    def test_imported_id_payee_and_notes(self):
        long_note = "x" * 500
        rows = _rows(("alias", "S1", date(2024, 1, 1), "MERCADONA SL", "MERCADONA", "-10.00", long_note))
        budget = _FakeBudget()
        _run_sync(rows, [], budget)
        created = budget.created[0]
        assert created["imported_id"] == "enablebanking:S1"
        assert created["account"] == "My account"
        assert created["payee"] == "MERCADONA"
        assert created["imported_payee"] == "MERCADONA SL"
        assert created["amount"] == Decimal("-10.00")
        assert created["booking_date"] == date(2024, 1, 1)
        assert len(created["notes"]) == sync.NOTES_MAX

    def test_payee_falls_back_to_raw_when_clean_is_missing(self):
        rows = _rows(("alias", "S1", date(2024, 1, 1), "SHOP A", None, "-10.00", None))
        budget = _FakeBudget()
        _run_sync(rows, [], budget)
        assert budget.created[0]["payee"] == "SHOP A"

    def test_seeds_a_category_and_rule_per_merchant(self):
        rows = _rows(("alias", "S1", date(2024, 1, 1), "MERCADONA", "MERCADONA", "-10.00", None))
        budget = _FakeBudget()
        _run_sync(rows, _categories(("MERCADONA", "GROCERIES"), ("REPSOL", "FUEL")), budget)
        assert {c["name"] for c in budget.categories} == {"GROCERIES", "FUEL", "Income"}
        merchant_rules = [r for r in budget.rules if not r["inflow"]]
        assert {r["key"] for r in merchant_rules} == {"payee:MERCADONA", "payee:REPSOL"}
        assert merchant_rules[0]["category_id"] == "cat:GROCERIES"
        assert merchant_rules[0]["payee_id"] == "payee:MERCADONA"
        assert merchant_rules[0]["stage"] == "pre"

    def test_inflow_rule_is_seeded_first_and_targets_income(self):
        rows = _rows(("alias", "S1", date(2024, 1, 1), "MERCADONA", "MERCADONA", "-10.00", None))
        budget = _FakeBudget()
        _run_sync(rows, _categories(("MERCADONA", "GROCERIES")), budget)
        assert budget.rules[0]["key"] == "inflow"
        assert budget.rules[0]["inflow"] is True
        assert budget.rules[0]["category_id"] == "cat:Income"
        assert budget.rules[0]["payee_id"] is None

    def test_lake_income_maps_to_actual_income_category(self):
        rows = _rows(("alias", "S1", date(2024, 1, 1), "ACME", "ACME", "-10.00", None))
        budget = _FakeBudget()
        _run_sync(rows, _categories(("ACME", "INCOME")), budget)
        income = [c for c in budget.categories if c["is_income"]]
        assert [c["name"] for c in income] == ["Income"]
        rule = next(r for r in budget.rules if r["key"] == "payee:ACME")
        assert rule["category_id"] == "cat:Income"

    def test_rules_run_on_created_and_existing_uncategorised(self):
        rows = _rows(("alias", "S1", date(2024, 1, 1), "SHOP A", "SHOP A", "-10.00", None))
        orphan = object()
        budget = _FakeBudget(uncategorised=[orphan])
        _run_sync(rows, [], budget)
        assert budget.ruled == [[budget.created[0], orphan]]

    def test_rules_not_run_when_nothing_to_do(self):
        rows = _rows(("alias", "S1", date(2024, 1, 1), "SHOP", "SHOP", "-10.00", None))
        budget = _FakeBudget(existing={"enablebanking:S1"})
        _run_sync(rows, [], budget)
        assert budget.ruled == []

    def test_reconciles_existing_rows_onto_clean_payee(self):
        rows = _rows(("alias", "S1", date(2024, 1, 1), "RAW BANK TEXT", "MERCADONA", "-10.00", None))
        orphan = object()
        budget = _FakeBudget(existing={"enablebanking:S1"}, uncategorised=[orphan], reconciled=1)
        counts = _run_sync(rows, _categories(("MERCADONA", "GROCERIES")), budget)
        assert counts["reconciled"] == 1
        assert budget.reconcile_calls == [rows]
        assert budget.ruled == [[orphan]]

    def test_dry_run_seeds_nothing_and_does_not_commit(self):
        rows = _rows(("alias", "S1", date(2024, 1, 1), "SHOP", "SHOP", "-10.00", None))
        budget = _FakeBudget()
        counts = _run_sync(rows, _categories(("SHOP", "SHOPPING")), budget, dry_run=True)
        assert counts["would_add"] == 1
        assert counts["committed"] is False
        assert budget.created == []
        assert budget.categories == []
        assert budget.rules == []
        assert budget.committed is False

    def test_creates_each_missing_account_once(self):
        rows = _rows(
            ("a", "S1", date(2024, 1, 1), "X", "X", "-1.00", None),
            ("a", "S2", date(2024, 1, 2), "Y", "Y", "-2.00", None),
            ("b", "S3", date(2024, 1, 3), "Z", "Z", "-3.00", None),
        )
        budget = _FakeBudget()
        _run_sync(rows, [], budget, account_map={"a": "Account A", "b": "Account B"})
        assert budget.ensured == ["Account A", "Account B"]

    def test_does_not_ensure_accounts_for_already_imported_rows(self):
        rows = _rows(("a", "S1", date(2024, 1, 1), "X", "X", "-1.00", None))
        budget = _FakeBudget(existing={"enablebanking:S1"})
        _run_sync(rows, [], budget, account_map={"a": "Account A"})
        assert budget.ensured == []
        assert budget.created == []

    def test_dry_run_creates_no_accounts(self):
        rows = _rows(("a", "S1", date(2024, 1, 1), "X", "X", "-1.00", None))
        budget = _FakeBudget()
        _run_sync(rows, [], budget, account_map={"a": "Account A"}, dry_run=True)
        assert budget.ensured == []

    def test_empty_payee_is_passed_through(self):
        rows = _rows(("alias", "S1", date(2024, 1, 1), None, None, "-10.00", None))
        budget = _FakeBudget()
        _run_sync(rows, [], budget)
        assert budget.created[0]["payee"] is None
        assert budget.created[0]["imported_payee"] is None


class TestRun:
    def _silver(self, tmp_path, rows):
        db = tmp_path / "silver.duckdb"
        con = duckdb.connect(str(db))
        con.execute("CREATE SCHEMA finance")
        con.execute(
            "CREATE TABLE finance.transactions ("
            "account_id VARCHAR, stable_id VARCHAR, booking_date DATE, payee VARCHAR, "
            "payee_clean VARCHAR, amount DECIMAL(18,2), remittance_info VARCHAR)"
        )
        for account_id, stable_id, booking_date, payee, payee_clean, amount, remittance in rows:
            con.execute(
                "INSERT INTO finance.transactions VALUES (?, ?, ?, ?, ?, ?, ?)",
                [account_id, stable_id, date.fromisoformat(booking_date), payee, payee_clean, Decimal(amount), remittance],
            )
        con.close()

    def _env(self, tmp_path, monkeypatch, accounts=None):
        monkeypatch.setenv("DBT_DUCKDB_DIR", str(tmp_path))
        for name in ("DBT_DUCKDB_PATH", "DBT_DUCKDB_SILVER_PATH", "DBT_DUCKDB_GOLD_PATH"):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("FINANCE_SYNC_FROM_DATE", "2024-01-01")
        monkeypatch.setenv("FINANCE_SYNC_TO_DATE", "2024-12-31")
        monkeypatch.setenv("FINANCE_ACTUAL_BASE_URL", "http://actual.example")
        monkeypatch.setenv("FINANCE_ACTUAL_PASSWORD", "pw")
        monkeypatch.setenv("FINANCE_ACTUAL_FILE", "budget")
        monkeypatch.setenv("FINANCE_ACTUAL_ACCOUNTS", accounts if accounts is not None else '{"alias": "My account"}')

    def test_local_defaults_to_dry_run(self, tmp_path, monkeypatch):
        self._silver(tmp_path, [("alias", "S1", "2024-01-01", "SHOP", "SHOP", "-10.00", None)])
        self._env(tmp_path, monkeypatch)
        budget = _FakeBudget()
        monkeypatch.setattr(sync, "_actual_client", lambda s: _fake_factory(budget))
        counts = sync.run("local")
        assert counts["would_add"] == 1
        assert counts["committed"] is False
        assert budget.created == []

    def test_unmapped_account_fails_naming_it(self, tmp_path, monkeypatch):
        self._silver(tmp_path, [("alias", "S1", "2024-01-01", "SHOP", "SHOP", "-10.00", None)])
        self._env(tmp_path, monkeypatch, accounts='{"other": "Other account"}')
        with pytest.raises(ActualAccountMapError, match="alias"):
            sync.run("local")

    def test_unconfigured_actual_reports_rows_without_dedup(self, tmp_path, monkeypatch):
        self._silver(tmp_path, [("alias", "S1", "2024-01-01", "SHOP", "SHOP", "-10.00", None)])
        self._env(tmp_path, monkeypatch)
        for name in ("FINANCE_ACTUAL_BASE_URL", "FINANCE_ACTUAL_PASSWORD", "FINANCE_ACTUAL_FILE"):
            monkeypatch.delenv(name, raising=False)
        counts = sync.run("local")
        assert counts == {"read": 1, "added": 0, "skipped": 0, "would_add": 1, "committed": False}

    def test_no_rows_is_a_noop(self, tmp_path, monkeypatch):
        self._silver(tmp_path, [])
        self._env(tmp_path, monkeypatch)
        assert sync.run("local") == {"read": 0, "added": 0, "skipped": 0, "committed": False}
