"""Sync step: push ``silver.finance.transactions`` into Actual Budget exactly once.

The app half of spec 005 §4.6. It reads the curated silver rows for the sync
window and imports each into the budget the operator actually budgets in,
keyed on ``imported_id = "enablebanking:" + stable_id`` so a re-run adds nothing.

Two rules from the spec shape the code:

- **Dedup is the pipeline's, not the library's.** actualpy's
  ``create_transaction`` does not reconcile like the Node ``importTransactions``
  (gate 7), so the existing ``financial_id``s are pre-queried and a row already
  present is skipped explicitly.
- **No category is ever set.** The budget's own rules own categorisation; the
  lake only supplies date, account, amount, payee text and an imported id.

The map from bank ``account_id`` to Actual account name lives in the
``finance-actual`` secret; a row whose account is not in the map fails the run
naming it — never a silent skip. The mapped account is created in the budget on
the first sync if it does not exist (``get_or_create_account``, matched by name),
so no manual UI step is needed; actualpy sets only name and ``offbudget``, so an
account needing a specific type is still created by hand.

``local`` is dry-run by default and stops before ``actual.commit()``; when Actual
is not configured at all it reports the rows read without claiming to have
deduped. ``FINANCE_SYNC_DRY_RUN=true`` makes the homelab run a dry run too.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from . import config

PIPELINE_NAME = "finance_sync"
IMPORTED_ID_PREFIX = "enablebanking:"
DEFAULT_WINDOW_DAYS = 60
NOTES_MAX = 200

logger = logging.getLogger(__name__)


class ActualAccountMapError(Exception):
    """A transaction's account has no entry in the finance-actual map."""


@dataclass(frozen=True)
class ActualSettings:
    base_url: str
    password: str
    file: str


class BudgetClient(Protocol):
    """The slice of the Actual budget this pipeline needs, and nothing else."""

    def existing_imported_ids(self) -> set[str]: ...

    def ensure_account(self, name: str) -> None: ...

    def create(
        self,
        *,
        booking_date: date,
        account: str,
        amount: Decimal,
        imported_id: str,
        payee: str | None,
        notes: str | None,
    ) -> None: ...

    def commit(self) -> None: ...


def _window() -> tuple[date, date]:
    """``[from_date, to_date]`` inclusive; ``FINANCE_SYNC_WINDOW_DAYS`` lookback."""
    from_date = config.sync_from_date()
    to_date = config.sync_to_date()
    if from_date is None:
        days = config.sync_window_days() or DEFAULT_WINDOW_DAYS
        from_date = (datetime.now(UTC).date() - timedelta(days=days - 1)).isoformat()
    if to_date is None:
        to_date = datetime.now(UTC).date().isoformat()
    return date.fromisoformat(from_date), date.fromisoformat(to_date)


def _read_transactions_local(silver_duckdb_path: str, from_date: date, to_date: date) -> list[dict]:
    """Curated silver rows for the window from DuckDB (local target)."""
    import duckdb

    con = duckdb.connect(silver_duckdb_path, read_only=True)
    try:
        exists = con.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema='finance' AND table_name='transactions'"
        ).fetchone()[0]
        if not exists:
            return []
        rows = con.execute(
            "SELECT account_id, stable_id, booking_date, payee, amount, remittance_info "
            "FROM finance.transactions "
            "WHERE booking_date >= ? AND booking_date <= ? "
            "ORDER BY booking_date, stable_id",
            [from_date, to_date],
        ).fetchall()
    finally:
        con.close()
    return [
        {
            "account_id": r[0],
            "stable_id": r[1],
            "booking_date": r[2],
            "payee": r[3],
            "amount": r[4],
            "remittance_info": r[5],
        }
        for r in rows
    ]


def _read_transactions_homelab(trino_url: str, from_date: date, to_date: date) -> list[dict]:
    """Curated silver rows for the window from Trino/Iceberg (homelab target)."""
    from sqlalchemy import create_engine, text

    engine = create_engine(trino_url)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT account_id, stable_id, booking_date, payee, amount, remittance_info "
                "FROM silver.finance.transactions "
                "WHERE booking_date >= :from_date AND booking_date <= :to_date "
                "ORDER BY booking_date, stable_id"
            ),
            {"from_date": from_date, "to_date": to_date},
        ).fetchall()
    return [
        {
            "account_id": r.account_id,
            "stable_id": r.stable_id,
            "booking_date": r.booking_date,
            "payee": r.payee,
            "amount": r.amount if isinstance(r.amount, Decimal) else Decimal(str(r.amount)),
            "remittance_info": r.remittance_info,
        }
        for r in rows
    ]


def _read_transactions(target: str, from_date: date, to_date: date) -> list[dict]:
    if target == "local":
        return _read_transactions_local(config.duckdb_path("silver"), from_date, to_date)
    return _read_transactions_homelab(config.trino_url(), from_date, to_date)


class _ActualPaymentClient:
    """``BudgetClient`` over actualpy. Imported lazily so tests never need the lib."""

    def __init__(self, actual):
        from actual.database import Transactions
        from sqlmodel import select

        self._actual = actual
        self._Transactions = Transactions
        self._select = select

    def existing_imported_ids(self) -> set[str]:
        rows = self._actual.session.exec(
            self._select(self._Transactions.financial_id).where(
                self._Transactions.financial_id.is_not(None)
            )
        ).all()
        return {row for row in rows if row}

    def ensure_account(self, name: str) -> None:
        from actual.queries import get_or_create_account

        get_or_create_account(self._actual.session, name)

    def create(self, *, booking_date, account, amount, imported_id, payee, notes) -> None:
        from actual.queries import create_transaction

        create_transaction(
            self._actual.session,
            date=booking_date,
            account=account,
            payee=None,
            notes=notes,
            amount=amount,
            imported_id=imported_id,
            imported_payee=payee,
        )

    def commit(self) -> None:
        self._actual.commit()


@contextmanager
def _actual_client(settings: ActualSettings) -> Iterator[_ActualPaymentClient]:
    from actual import Actual

    with Actual(
        base_url=settings.base_url,
        password=settings.password,
        file=settings.file,
    ) as actual:
        yield _ActualPaymentClient(actual)


def _unmapped_accounts(rows: list[dict], account_map: dict[str, str]) -> list[str]:
    return sorted({r["account_id"] for r in rows} - set(account_map))


def _sync(
    rows: list[dict],
    account_map: dict[str, str],
    settings: ActualSettings,
    dry_run: bool,
    client_factory: Callable[[ActualSettings], Iterator[BudgetClient]] | None = None,
) -> dict:
    """Push the rows that are not yet in the budget. Returns the counts."""
    # Resolved here, not as a default argument, so a test can replace the global
    # `_actual_client` and have `run()` pick the fake up.
    factory = client_factory or _actual_client
    with factory(settings) as client:
        existing = client.existing_imported_ids()
        to_add = [r for r in rows if IMPORTED_ID_PREFIX + r["stable_id"] not in existing]

        if dry_run:
            logger.info(
                "%s: dry run - %d row(s) read, %d already present, %d would be added (no commit)",
                PIPELINE_NAME, len(rows), len(rows) - len(to_add), len(to_add),
            )
            return {
                "read": len(rows),
                "added": 0,
                "skipped": len(rows) - len(to_add),
                "would_add": len(to_add),
                "committed": False,
            }

        # Create any missing Actual accounts first, once each, so the first sync needs
        # no manual UI step. Accounts are matched by name; a later rename splits one.
        for account_name in sorted({account_map[row["account_id"]] for row in to_add}):
            client.ensure_account(account_name)

        for row in to_add:
            client.create(
                booking_date=row["booking_date"],
                account=account_map[row["account_id"]],
                amount=row["amount"],
                imported_id=IMPORTED_ID_PREFIX + row["stable_id"],
                payee=row["payee"],
                notes=(row["remittance_info"] or "")[:NOTES_MAX] or None,
            )
        client.commit()

        counts = {
            "read": len(rows),
            "added": len(to_add),
            "skipped": len(rows) - len(to_add),
            "committed": True,
        }
        logger.info("%s: %s", PIPELINE_NAME, counts)
        return counts


def run(target: str) -> dict:
    config.validate_target(target)

    from_date, to_date = _window()
    rows = _read_transactions(target, from_date, to_date)
    dry_run = target == "local" or config.sync_dry_run()
    logger.info(
        "%s: window=[%s..%s] rows=%d dry_run=%s", PIPELINE_NAME, from_date, to_date, len(rows), dry_run
    )

    if not rows:
        return {"read": 0, "added": 0, "skipped": 0, "committed": False}

    configured = all(
        config.env(name)
        for name in ("FINANCE_ACTUAL_BASE_URL", "FINANCE_ACTUAL_PASSWORD", "FINANCE_ACTUAL_FILE")
    )
    if dry_run and not configured:
        logger.warning(
            "%s: Actual is not configured; reporting rows read without a dedup check "
            "(set FINANCE_ACTUAL_* to make the dry run real)", PIPELINE_NAME,
        )
        return {"read": len(rows), "added": 0, "skipped": 0, "would_add": len(rows), "committed": False}

    account_map = config.actual_account_map()
    unmapped = _unmapped_accounts(rows, account_map)
    if unmapped:
        raise ActualAccountMapError(
            f"{', '.join(unmapped)}: no Actual account in finance-actual accounts.json; "
            "add the account in the budget and map it, never skip the row"
        )

    settings = ActualSettings(config.actual_base_url(), config.actual_password(), config.actual_file())
    return _sync(rows, account_map, settings, dry_run)
