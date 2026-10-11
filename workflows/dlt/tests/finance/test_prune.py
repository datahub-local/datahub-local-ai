"""Tests for the Actual Budget prune pipeline.

No real Actual server and no actualpy call: the budget is a fake that records what
was deleted and whether it committed, and the silver read is patched. The contract
under test is that only a positional-shaped imported id which is gone from silver
is a candidate - never a lone positional row, never a provider reference, never a
row the pipeline did not write - and that nothing is written without
``FINANCE_PRUNE_APPLY``.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from finance import prune


class _Payee:
    def __init__(self, name):
        self.name = name


class _FakeTransaction:
    def __init__(self, financial_id, acct="My account", amount="-12.00", payee="SHOP"):
        self.financial_id = financial_id
        self.acct = acct
        self.date = "2026-01-15"
        self.amount = amount
        self.payee = _Payee(payee) if payee else None
        self.tombstone = 0

    def delete(self):
        self.tombstone = 1


class _FakeBudget:
    def __init__(self, transactions):
        self.transactions = list(transactions)
        self.deleted = []
        self.committed = False

    def imported_transactions(self):
        return [t for t in self.transactions if not t.tombstone]

    def delete(self, transaction):
        self.deleted.append(transaction.financial_id)
        transaction.delete()

    def commit(self):
        self.committed = True


@contextmanager
def _fake_factory(budget):
    yield budget


_SILVER = {"hash_a", "2026-01-01.0"}


def _run(budget, silver_ids=_SILVER, apply=False, target="homelab", monkeypatch=None):
    monkeypatch.setattr(prune, "_silver_ids", lambda t: set(silver_ids))
    monkeypatch.setattr(prune, "_actual_client", lambda s: _fake_factory(budget))
    if apply:
        monkeypatch.setenv("FINANCE_PRUNE_APPLY", "true")
    else:
        monkeypatch.delenv("FINANCE_PRUNE_APPLY", raising=False)
    for name, value in (
        ("FINANCE_ACTUAL_BASE_URL", "http://actual.example"),
        ("FINANCE_ACTUAL_PASSWORD", "pw"),
        ("FINANCE_ACTUAL_FILE", "budget"),
    ):
        monkeypatch.setenv(name, value)
    return prune.run(target)


def test_superseded_positional_row_is_the_only_candidate(monkeypatch):
    budget = _FakeBudget(
        [
            _FakeTransaction("enablebanking:hash_a"),           # survivor, in silver
            _FakeTransaction("enablebanking:2026-01-01.0"),     # lone copy, still in silver
            _FakeTransaction("enablebanking:2026-01-02.0"),     # superseded: absent from silver
            _FakeTransaction("enablebanking:ASPSP-REF-1"),      # genuine reference, not positional
            _FakeTransaction(None),                             # an operator's own row
            _FakeTransaction("something:else"),                 # another writer
        ]
    )

    counts = _run(budget, monkeypatch=monkeypatch)

    assert counts["superseded"] == 1
    assert counts["kept"] == 1
    assert budget.deleted == []
    assert budget.committed is False


def test_apply_tombstones_exactly_the_candidates(monkeypatch):
    budget = _FakeBudget(
        [
            _FakeTransaction("enablebanking:hash_a"),
            _FakeTransaction("enablebanking:2026-01-02.0"),
        ]
    )

    counts = _run(budget, apply=True, monkeypatch=monkeypatch)

    assert counts["committed"] is True
    assert budget.deleted == ["enablebanking:2026-01-02.0"]
    assert budget.committed is True


def test_a_provider_reference_absent_from_silver_is_not_touched(monkeypatch):
    budget = _FakeBudget(
        [
            _FakeTransaction("enablebanking:ASPSP-REF-1"),
            _FakeTransaction("enablebanking:REF.2026.0001"),
        ]
    )

    counts = _run(budget, apply=True, monkeypatch=monkeypatch)

    assert counts["superseded"] == 0
    assert budget.deleted == []


def test_dry_run_is_the_default_off_local_too(monkeypatch):
    budget = _FakeBudget([_FakeTransaction("enablebanking:2026-01-02.0")])

    counts = _run(budget, apply=True, target="local", monkeypatch=monkeypatch)

    assert counts["committed"] is False
    assert budget.deleted == []


def test_an_unreadable_silver_stops_the_run(monkeypatch):
    budget = _FakeBudget([_FakeTransaction("enablebanking:2026-01-02.0")])

    with pytest.raises(RuntimeError, match="refusing to plan a purge"):
        _run(budget, silver_ids=set(), apply=True, monkeypatch=monkeypatch)

    assert budget.deleted == []


def test_no_actual_configured_reports_nothing_to_do(monkeypatch):
    monkeypatch.setattr(prune, "_silver_ids", lambda t: set(_SILVER))
    for name in ("FINANCE_ACTUAL_BASE_URL", "FINANCE_ACTUAL_PASSWORD", "FINANCE_ACTUAL_FILE"):
        monkeypatch.delenv(name, raising=False)

    counts = prune.run("homelab")

    assert counts == {"silver": len(_SILVER), "superseded": 0, "kept": 0, "committed": False}


class TestPredicates:
    def test_positional_absent_from_silver_is_superseded(self):
        assert prune._superseded("enablebanking:2026-01-02.0", _SILVER) is True

    def test_positional_present_in_silver_is_kept(self):
        assert prune._superseded("enablebanking:2026-01-01.0", _SILVER) is False
        assert prune._standalone_positional("enablebanking:2026-01-01.0", _SILVER) is True

    def test_a_hash_id_is_never_superseded(self):
        assert prune._superseded("enablebanking:hash_missing", _SILVER) is False

    def test_a_foreign_prefix_is_out_of_scope(self):
        assert prune._superseded("bank:2026-01-02.0", _SILVER) is False
        assert prune._stable_id(None) is None
