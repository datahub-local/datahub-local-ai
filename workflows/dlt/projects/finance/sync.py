"""Sync step: push ``silver.finance.transactions`` into Actual Budget exactly once.

The app half of spec 005 §4.6. It reads the curated silver rows for the sync
window and imports each into the budget the operator actually budgets in,
keyed on ``imported_id = "enablebanking:" + stable_id`` so a re-run adds nothing.

Four rules from the spec shape the code:

- **Dedup is the pipeline's, not the library's.** actualpy's
  ``create_transaction`` does not reconcile like the Node ``importTransactions``
  (gate 7), so the existing ``financial_id``s are pre-queried and a row already
  present is skipped explicitly.
- **The app owns categorisation, and its rules are seeded from the lake.** The
  lake's ``silver.finance.merchant_categories`` (the LLM enrich) is not written
  onto each transaction; instead the sync materialises it into the app as
  categories and one rule per merchant (``payee_clean`` -> category), plus a
  catch-all inflow rule that sends uncategorised credits to Actual's ``Income``
  category. Actual never runs rules over actualpy-inserted rows (probed
  2026-09-17, gate 7), so the run invokes ``run_rules()`` itself — first on the
  rows just created, then on any transaction still lacking a category, so a rule
  added later backfills without ever overwriting a category a human set.
- **Generated rules are ours and are upserted by deterministic id.** Each rule's
  id is ``uuid5(RULE_NAMESPACE, key)``, so a changed lake category updates the
  same rule and the operator's own rules are never touched. They run in the
  ``pre`` stage, which leaves every operator rule (default stage) free to
  override them.
- **Existing rows are re-keyed onto ``payee_clean``.** The first live sync
  (2026-09-17) predated clean payees and passed the raw bank text as the payee,
  so its rows carried a payee a merchant rule can never match and stayed
  uncategorised forever. Every run reconciles the payee of a transaction it
  already imported onto its ``payee_clean`` (creating the payee if needed)
  before ``run_rules()``, so the backlog heals on the next sync. A payee that is
  neither the expected clean name nor the raw bank label is left alone — that is
  a human rename, which the pipeline does not own.

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

import json
import logging
import uuid
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
CATEGORY_GROUP = "Auto-categorised"
LAKE_INCOME_CATEGORY = "INCOME"
ACTUAL_INCOME_CATEGORY = "Income"
RULE_STAGE = "pre"
# Fixed namespace: every generated rule has a deterministic id, so a sync can
# update its own rules and leave the operator's alone (spec 005 §4.6).
RULE_NAMESPACE = uuid.UUID("2f6b1c8e-4d0a-4e7b-9c31-6a5d9e2f7b40")

logger = logging.getLogger(__name__)


class ActualAccountMapError(Exception):
    """A transaction's account has no entry in the finance-actual map."""


class ActualBudgetNotFound(Exception):
    """``FINANCE_ACTUAL_FILE`` matches no budget on the Actual server."""


@dataclass(frozen=True)
class ActualSettings:
    base_url: str
    password: str
    file: str


class BudgetClient(Protocol):
    """The slice of the Actual budget this pipeline needs, and nothing else."""

    def existing_imported_ids(self) -> set[str]: ...

    def reconcile_payees(self, rows: list[dict]) -> int: ...

    def ensure_account(self, name: str) -> None: ...

    def ensure_category(self, name: str, *, group: str, is_income: bool = False) -> str: ...

    def ensure_payee(self, name: str) -> str: ...

    def ensure_rule(
        self,
        key: str,
        *,
        payee_id: str | None,
        category_id: str,
        inflow: bool,
        stage: str | None,
    ) -> None: ...

    def uncategorised(self) -> list: ...

    def create(
        self,
        *,
        booking_date: date,
        account: str,
        amount: Decimal,
        imported_id: str,
        payee: str | None,
        imported_payee: str | None,
        notes: str | None,
    ) -> object: ...

    def run_rules(self, transactions: list) -> None: ...

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
            "SELECT account_id, stable_id, booking_date, payee, payee_clean, amount, remittance_info "
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
            "payee_clean": r[4],
            "amount": r[5],
            "remittance_info": r[6],
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
                "SELECT account_id, stable_id, booking_date, payee, payee_clean, amount, remittance_info "
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
            "payee_clean": r.payee_clean,
            "amount": r.amount if isinstance(r.amount, Decimal) else Decimal(str(r.amount)),
            "remittance_info": r.remittance_info,
        }
        for r in rows
    ]


def _read_transactions(target: str, from_date: date, to_date: date) -> list[dict]:
    if target == "local":
        return _read_transactions_local(config.duckdb_path("silver"), from_date, to_date)
    return _read_transactions_homelab(config.trino_url(), from_date, to_date)


def _read_categories_local(silver_duckdb_path: str) -> list[dict]:
    """Merchant -> lake category rows from DuckDB (local target)."""
    import duckdb

    con = duckdb.connect(silver_duckdb_path, read_only=True)
    try:
        exists = con.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema='finance' AND table_name='merchant_categories'"
        ).fetchone()[0]
        if not exists:
            return []
        rows = con.execute(
            "SELECT payee_clean, category FROM finance.merchant_categories "
            "WHERE subcategory != 'PARSE_ERROR'"
        ).fetchall()
    finally:
        con.close()
    return [{"payee_clean": r[0], "category": r[1]} for r in rows if r[0] and r[1]]


def _read_categories_homelab(trino_url: str) -> list[dict]:
    """Merchant -> lake category rows from Trino/Iceberg (homelab target)."""
    from sqlalchemy import create_engine, text

    engine = create_engine(trino_url)
    with engine.connect() as conn:
        try:
            rows = conn.execute(
                text(
                    "SELECT payee_clean, category FROM silver.finance.merchant_categories "
                    "WHERE subcategory != 'PARSE_ERROR'"
                )
            ).fetchall()
        except Exception:
            logger.debug(
                "silver.finance.merchant_categories not found; seeding no rules (first run?)",
                exc_info=True,
            )
            return []
    return [{"payee_clean": r.payee_clean, "category": r.category} for r in rows if r.payee_clean and r.category]


def _read_categories(target: str) -> list[dict]:
    if target == "local":
        return _read_categories_local(config.duckdb_path("silver"))
    return _read_categories_homelab(config.trino_url())


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

    def reconcile_payees(self, rows: list[dict]) -> int:
        from actual.database import Transactions
        from actual.queries import get_or_create_payee

        session = self._actual.session
        fixed = 0
        for row in rows:
            clean = row["payee_clean"] or row["payee"]
            if not clean:
                continue
            transaction = session.exec(
                self._select(Transactions).where(
                    Transactions.financial_id == IMPORTED_ID_PREFIX + row["stable_id"]
                )
            ).first()
            if transaction is None:
                continue
            current = transaction.payee.name if transaction.payee is not None else None
            if current == clean:
                continue
            # Only rewrite the pipeline's own raw bank label; anything else is a
            # rename a human made in the budget, which the pipeline must not undo.
            if current is not None and current.strip() != (row["payee"] or "").strip():
                continue
            transaction.payee_id = get_or_create_payee(session, clean).id
            fixed += 1
        return fixed

    def ensure_account(self, name: str) -> None:
        from actual.queries import get_or_create_account

        get_or_create_account(self._actual.session, name)

    def ensure_category(self, name: str, *, group: str, is_income: bool = False) -> str:
        from actual.database import Categories, CategoryGroups, CategoryMapping
        from actual.queries import get_category

        session = self._actual.session
        category = get_category(session, name)
        if category is not None:
            return category.id
        group_row = session.exec(
            self._select(CategoryGroups).where(CategoryGroups.name == group)
        ).one_or_none()
        if group_row is None:
            group_row = CategoryGroups(
                id=str(uuid.uuid4()), name=group, is_income=1 if is_income else 0, sort_order=0
            )
            session.add(group_row)
        category = Categories(
            id=str(uuid.uuid4()),
            name=name,
            hidden=False,
            is_income=1 if is_income else 0,
            cat_group=group_row.id,
            sort_order=0,
        )
        session.add(category)
        session.add(CategoryMapping(id=category.id, transfer_id=category.id))
        return category.id

    def ensure_payee(self, name: str) -> str:
        from actual.queries import get_or_create_payee

        return get_or_create_payee(self._actual.session, name).id

    def ensure_rule(
        self,
        key: str,
        *,
        payee_id: str | None,
        category_id: str,
        inflow: bool,
        stage: str | None,
    ) -> None:
        from actual.database import Rules
        from actual.rules import Action, Condition, ConditionType

        if inflow:
            conditions = [Condition(field="amount_inflow", op=ConditionType.GT, value=0)]
        else:
            conditions = [Condition(field="description", op=ConditionType.IS, value=payee_id)]
        actions = [Action(field="category", value=category_id)]
        condition_json = json.dumps(
            [c.model_dump(mode="json", by_alias=True) for c in conditions]
        )
        action_json = json.dumps([a.model_dump(mode="json", by_alias=True) for a in actions])

        session = self._actual.session
        rule_id = str(uuid.uuid5(RULE_NAMESPACE, key))
        rule = session.get(Rules, rule_id)
        if rule is None:
            session.add(
                Rules(
                    id=rule_id,
                    stage=stage,
                    conditions_op="and",
                    conditions=condition_json,
                    actions=action_json,
                )
            )
        else:
            rule.stage = stage
            rule.conditions = condition_json
            rule.actions = action_json
            rule.tombstone = 0

    def uncategorised(self) -> list:
        from actual.queries import get_transactions

        return [t for t in get_transactions(self._actual.session) if not t.category_id]

    def create(
        self, *, booking_date, account, amount, imported_id, payee, imported_payee, notes
    ) -> object:
        from actual.queries import create_transaction

        return create_transaction(
            self._actual.session,
            date=booking_date,
            account=account,
            payee=payee,
            notes=notes,
            amount=amount,
            imported_id=imported_id,
            imported_payee=imported_payee,
        )

    def run_rules(self, transactions: list) -> None:
        # Actual itself never runs rules over actualpy-inserted rows (gate 7),
        # so the app's rules are applied here to the new and uncategorised rows.
        if transactions:
            self._actual.run_rules(transactions)

    def commit(self) -> None:
        self._actual.commit()


@contextmanager
def _actual_client(settings: ActualSettings) -> Iterator[_ActualPaymentClient]:
    from actual import Actual
    from actual.exceptions import UnknownFileId

    try:
        actual = Actual(
            base_url=settings.base_url,
            password=settings.password,
            file=settings.file,
        )
    except UnknownFileId as exc:
        raise ActualBudgetNotFound(
            f"FINANCE_ACTUAL_FILE={settings.file!r} matches no budget on "
            f"{settings.base_url}; pin the budget's sync id (read it in the "
            "budget's settings), not its display name, which Actual resets on upload"
        ) from exc
    with actual:
        yield _ActualPaymentClient(actual)


def _unmapped_accounts(rows: list[dict], account_map: dict[str, str]) -> list[str]:
    return sorted({r["account_id"] for r in rows} - set(account_map))


def _actual_category_name(lake_category: str) -> str:
    """The lake's ``INCOME`` maps onto Actual's own income category."""
    return ACTUAL_INCOME_CATEGORY if lake_category == LAKE_INCOME_CATEGORY else lake_category


def _seed_rules(client: BudgetClient, categories: list[dict]) -> None:
    """Materialise the lake's merchant categories as Actual categories + rules.

    The catch-all inflow rule is created first and merchant rules after it:
    rules run in insertion order inside a stage, so a merchant rule wins over
    the inflow rule (a refund to a known merchant keeps its spending category)
    while an unclassified credit falls through to ``Income``. Everything is in
    the ``pre`` stage, leaving operator rules free to override them.
    """
    category_ids: dict[str, str] = {}

    def category_id(lake_category: str) -> str:
        if lake_category not in category_ids:
            category_ids[lake_category] = client.ensure_category(
                _actual_category_name(lake_category),
                group=CATEGORY_GROUP,
                is_income=lake_category == LAKE_INCOME_CATEGORY,
            )
        return category_ids[lake_category]

    income_id = category_id(LAKE_INCOME_CATEGORY)
    client.ensure_rule(
        "inflow", payee_id=None, category_id=income_id, inflow=True, stage=RULE_STAGE
    )

    for row in categories:
        payee_id = client.ensure_payee(row["payee_clean"])
        client.ensure_rule(
            f"payee:{row['payee_clean']}",
            payee_id=payee_id,
            category_id=category_id(row["category"]),
            inflow=False,
            stage=RULE_STAGE,
        )


def _sync(
    rows: list[dict],
    categories: list[dict],
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

        # Captured before creating, so the new rows are not run twice.
        uncategorised = client.uncategorised()

        # Categories and rules must exist before the rows are inserted; Actual
        # applies no rules on its own to actualpy-inserted transactions.
        _seed_rules(client, categories)

        # Re-key rows imported before the clean-payee change onto payee_clean, so
        # a merchant rule can finally match them; run before run_rules() below.
        reconciled = client.reconcile_payees(rows)

        # Create any missing Actual accounts first, once each, so the first sync needs
        # no manual UI step. Accounts are matched by name; a later rename splits one.
        for account_name in sorted({account_map[row["account_id"]] for row in to_add}):
            client.ensure_account(account_name)

        created = []
        for row in to_add:
            created.append(
                client.create(
                    booking_date=row["booking_date"],
                    account=account_map[row["account_id"]],
                    amount=row["amount"],
                    imported_id=IMPORTED_ID_PREFIX + row["stable_id"],
                    payee=row["payee_clean"] or row["payee"],
                    imported_payee=row["payee"],
                    notes=(row["remittance_info"] or "")[:NOTES_MAX] or None,
                )
            )
        targets = created + uncategorised
        if targets:
            client.run_rules(targets)
        client.commit()

        counts = {
            "read": len(rows),
            "added": len(to_add),
            "skipped": len(rows) - len(to_add),
            "reconciled": reconciled,
            "committed": True,
        }
        logger.info("%s: %s", PIPELINE_NAME, counts)
        return counts


def run(target: str) -> dict:
    config.validate_target(target)

    from_date, to_date = _window()
    rows = _read_transactions(target, from_date, to_date)
    categories = _read_categories(target)
    dry_run = target == "local" or config.sync_dry_run()
    logger.info(
        "%s: window=[%s..%s] rows=%d merchants=%d dry_run=%s",
        PIPELINE_NAME, from_date, to_date, len(rows), len(categories), dry_run,
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
    return _sync(rows, categories, account_map, settings, dry_run)
