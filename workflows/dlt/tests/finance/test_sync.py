"""Tests for the Actual Budget sync pipeline.

No real Actual server and no actualpy call: the budget is a fake that records
what was created and what was committed, and the silver read is either a tmp
DuckDB file or a patched reader. The contract under test is dedup on
``imported_id``, fail-on-unmapped and the local dry-run default.
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
    def __init__(self, existing=None):
        self.existing = set(existing or [])
        self.created = []
        self.committed = False

    def existing_imported_ids(self):
        return set(self.existing)

    def create(self, **kwargs):
        self.created.append(kwargs)

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
            "amount": Decimal(amount),
            "remittance_info": remittance,
        }
        for account_id, stable_id, booking_date, payee, amount, remittance in specs
    ]


_SETTINGS = ActualSettings(base_url="http://actual.example", password="pw", file="budget")


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
            "amount DECIMAL(18,2), remittance_info VARCHAR)"
        )
        for account_id, stable_id, booking_date, payee, amount, remittance in rows:
            con.execute(
                "INSERT INTO finance.transactions VALUES (?, ?, ?, ?, ?, ?)",
                [account_id, stable_id, date.fromisoformat(booking_date), payee, Decimal(amount), remittance],
            )
        con.close()
        return db

    def test_returns_only_rows_in_window(self, tmp_path):
        db = self._write_silver(
            tmp_path,
            [
                ("alias", "IN", "2024-01-15", "SHOP", "-12.34", "card"),
                ("alias", "OUT", "2023-12-01", "OLD", "-1.00", None),
            ],
        )
        rows = sync._read_transactions_local(str(db), date(2024, 1, 1), date(2024, 1, 31))
        assert [r["stable_id"] for r in rows] == ["IN"]
        assert rows[0]["amount"] == Decimal("-12.34")

    def test_missing_table_is_empty(self, tmp_path):
        db = tmp_path / "silver.duckdb"
        duckdb.connect(str(db)).close()
        assert sync._read_transactions_local(str(db), date(2024, 1, 1), date(2024, 1, 31)) == []


class TestSync:
    def test_creates_only_rows_not_already_imported(self):
        rows = _rows(
            ("alias", "S1", date(2024, 1, 1), "SHOP A", "-10.00", "card"),
            ("alias", "S2", date(2024, 1, 2), "SHOP B", "-20.00", "card"),
        )
        budget = _FakeBudget(existing={"enablebanking:S1"})
        counts = _sync(rows, {"alias": "My account"}, _SETTINGS, dry_run=False, client_factory=lambda s: _fake_factory(budget))
        assert counts == {"read": 2, "added": 1, "skipped": 1, "committed": True}
        assert [c["imported_id"] for c in budget.created] == ["enablebanking:S2"]
        assert budget.committed is True

    def test_imported_id_and_payee_and_notes(self):
        long_note = "x" * 500
        rows = _rows(("alias", "S1", date(2024, 1, 1), "SHOP A", "-10.00", long_note))
        budget = _FakeBudget()
        _sync(rows, {"alias": "My account"}, _SETTINGS, dry_run=False, client_factory=lambda s: _fake_factory(budget))
        created = budget.created[0]
        assert created["imported_id"] == "enablebanking:S1"
        assert created["account"] == "My account"
        assert created["payee"] == "SHOP A"
        assert created["amount"] == Decimal("-10.00")
        assert created["booking_date"] == date(2024, 1, 1)
        assert len(created["notes"]) == sync.NOTES_MAX

    def test_dry_run_creates_nothing_and_does_not_commit(self):
        rows = _rows(("alias", "S1", date(2024, 1, 1), "SHOP", "-10.00", None))
        budget = _FakeBudget()
        counts = _sync(rows, {"alias": "My account"}, _SETTINGS, dry_run=True, client_factory=lambda s: _fake_factory(budget))
        assert counts["would_add"] == 1
        assert counts["committed"] is False
        assert budget.created == []
        assert budget.committed is False

    def test_empty_payee_is_passed_through(self):
        rows = _rows(("alias", "S1", date(2024, 1, 1), None, "-10.00", None))
        budget = _FakeBudget()
        _sync(rows, {"alias": "My account"}, _SETTINGS, dry_run=False, client_factory=lambda s: _fake_factory(budget))
        assert budget.created[0]["payee"] is None


class TestRun:
    def _silver(self, tmp_path, rows):
        db = tmp_path / "silver.duckdb"
        con = duckdb.connect(str(db))
        con.execute("CREATE SCHEMA finance")
        con.execute(
            "CREATE TABLE finance.transactions ("
            "account_id VARCHAR, stable_id VARCHAR, booking_date DATE, payee VARCHAR, "
            "amount DECIMAL(18,2), remittance_info VARCHAR)"
        )
        for account_id, stable_id, booking_date, payee, amount, remittance in rows:
            con.execute(
                "INSERT INTO finance.transactions VALUES (?, ?, ?, ?, ?, ?)",
                [account_id, stable_id, date.fromisoformat(booking_date), payee, Decimal(amount), remittance],
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
        self._silver(tmp_path, [("alias", "S1", "2024-01-01", "SHOP", "-10.00", None)])
        self._env(tmp_path, monkeypatch)
        budget = _FakeBudget()
        monkeypatch.setattr(sync, "_actual_client", lambda s: _fake_factory(budget))
        counts = sync.run("local")
        assert counts["would_add"] == 1
        assert counts["committed"] is False
        assert budget.created == []

    def test_unmapped_account_fails_naming_it(self, tmp_path, monkeypatch):
        self._silver(tmp_path, [("alias", "S1", "2024-01-01", "SHOP", "-10.00", None)])
        self._env(tmp_path, monkeypatch, accounts='{"other": "Other account"}')
        with pytest.raises(ActualAccountMapError, match="alias"):
            sync.run("local")

    def test_unconfigured_actual_reports_rows_without_dedup(self, tmp_path, monkeypatch):
        self._silver(tmp_path, [("alias", "S1", "2024-01-01", "SHOP", "-10.00", None)])
        self._env(tmp_path, monkeypatch)
        for name in ("FINANCE_ACTUAL_BASE_URL", "FINANCE_ACTUAL_PASSWORD", "FINANCE_ACTUAL_FILE"):
            monkeypatch.delenv(name, raising=False)
        counts = sync.run("local")
        assert counts == {"read": 1, "added": 0, "skipped": 0, "would_add": 1, "committed": False}

    def test_no_rows_is_a_noop(self, tmp_path, monkeypatch):
        self._silver(tmp_path, [])
        self._env(tmp_path, monkeypatch)
        assert sync.run("local") == {"read": 0, "added": 0, "skipped": 0, "committed": False}
