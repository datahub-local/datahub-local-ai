"""Prune step: retire the Actual Budget transactions whose identity was superseded.

The one-off migration behind the 2026-10-09 identity change. That change stopped
trusting a booking-date-scoped ``entry_reference`` and re-keyed transactions onto
a hash, which means a payment already imported under the old ordinal id has since
been imported again under the hash id - the sync dedupes on
``imported_id = "enablebanking:" + stable_id``, so two identities are two rows.
The duplicate lives in the budget the operator reads, and nothing in the sync
removes it, because the sync only ever inserts.

This pipeline removes exactly those rows and nothing else. A candidate is a
transaction whose imported id starts with ``enablebanking:`` **and** whose stable
id is positional in shape **and** which no longer appears in
``silver.finance.transactions``:

- Before the silver dedup lands, silver still holds every positional id, so the
  plan is empty - running it early is a no-op rather than a mistake.
- A payment whose only row is the positional one, because no fetch has covered
  its booking date since the rule changed, is still in silver and is kept.
- A genuine provider reference that is missing from silver is not positional in
  shape and is therefore never touched. Neither is anything an operator wrote:
  only the pipeline's own prefix is read.

Dry run unless ``FINANCE_PRUNE_APPLY`` is true, on every target - the operation
is destructive and one-off, so the sync's "the local target is the dry run"
convention is not enough here. An unreadable (empty) silver is a hard error, the
one input that would make every positional row a candidate.
"""

from __future__ import annotations

import logging

from . import config
from .providers.enablebanking import _is_positional_reference
from .sync import IMPORTED_ID_PREFIX, ActualSettings, _actual_client

PIPELINE_NAME = "finance_prune"

logger = logging.getLogger(__name__)


def _read_silver_ids_local(silver_duckdb_path: str) -> set[str]:
    """Every stable id in silver from DuckDB (local target)."""
    import duckdb

    con = duckdb.connect(silver_duckdb_path, read_only=True)
    try:
        exists = con.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema='finance' AND table_name='transactions'"
        ).fetchone()[0]
        if not exists:
            return set()
        rows = con.execute("SELECT stable_id FROM finance.transactions").fetchall()
    finally:
        con.close()
    return {row[0] for row in rows if row[0]}


def _read_silver_ids_homelab(trino_url: str) -> set[str]:
    """Every stable id in silver from Trino/Iceberg (homelab target)."""
    from sqlalchemy import create_engine, text

    engine = create_engine(trino_url)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT stable_id FROM silver.finance.transactions")).fetchall()
    return {row.stable_id for row in rows if row.stable_id}


def _silver_ids(target: str) -> set[str]:
    """The whole table, not the sync window: an id absent here is superseded.

    Unlike the sync, this read is not windowed. A positional row outside the
    sync window is the sole copy of its payment and must be recognised as present.
    """
    if target == "local":
        return _read_silver_ids_local(config.duckdb_path("silver"))
    return _read_silver_ids_homelab(config.trino_url())


def _stable_id(financial_id: str | None) -> str | None:
    if not financial_id or not financial_id.startswith(IMPORTED_ID_PREFIX):
        return None
    return financial_id[len(IMPORTED_ID_PREFIX):]


def _superseded(financial_id: str | None, silver_ids: set[str]) -> bool:
    stable_id = _stable_id(financial_id)
    return (
        stable_id is not None
        and _is_positional_reference(stable_id)
        and stable_id not in silver_ids
    )


def _standalone_positional(financial_id: str | None, silver_ids: set[str]) -> bool:
    """A positional row that is still the only copy of its payment."""
    stable_id = _stable_id(financial_id)
    return (
        stable_id is not None
        and _is_positional_reference(stable_id)
        and stable_id in silver_ids
    )


def _describe(transaction) -> str:
    payee = transaction.payee.name if transaction.payee is not None else None
    return (
        f"{transaction.financial_id} account={transaction.acct} "
        f"date={transaction.date} amount={transaction.amount} payee={payee}"
    )


def run(target: str) -> dict:
    config.validate_target(target)

    silver_ids = _silver_ids(target)
    if not silver_ids:
        raise RuntimeError(
            f"{PIPELINE_NAME}: silver.finance.transactions is empty for target "
            f"'{target}'; refusing to plan a purge where every positional "
            "transaction would be a candidate"
        )

    logger.info("%s: silver holds %d identities", PIPELINE_NAME, len(silver_ids))

    configured = all(
        config.env(name)
        for name in ("FINANCE_ACTUAL_BASE_URL", "FINANCE_ACTUAL_PASSWORD", "FINANCE_ACTUAL_FILE")
    )
    if not configured:
        logger.warning(
            "%s: Actual is not configured; the plan cannot be built "
            "(set FINANCE_ACTUAL_*)", PIPELINE_NAME,
        )
        return {"silver": len(silver_ids), "superseded": 0, "kept": 0, "committed": False}

    settings = ActualSettings(config.actual_base_url(), config.actual_password(), config.actual_file())
    apply = config.prune_apply() and target != "local"

    with _actual_client(settings) as client:
        transactions = client.imported_transactions()
        candidates = [t for t in transactions if _superseded(t.financial_id, silver_ids)]
        kept = [t for t in transactions if _standalone_positional(t.financial_id, silver_ids)]

        for transaction in candidates:
            logger.info("%s: candidate %s", PIPELINE_NAME, _describe(transaction))
        logger.info(
            "%s: imported=%d superseded=%d kept_positional=%d apply=%s",
            PIPELINE_NAME, len(transactions), len(candidates), len(kept), apply,
        )

        if not apply:
            logger.info(
                "%s: dry run - %d row(s) would be removed (set FINANCE_PRUNE_APPLY=true "
                "to commit)", PIPELINE_NAME, len(candidates),
            )
            return {
                "silver": len(silver_ids),
                "superseded": len(candidates),
                "kept": len(kept),
                "committed": False,
            }

        for transaction in candidates:
            client.delete(transaction)
        client.commit()

        counts = {
            "silver": len(silver_ids),
            "superseded": len(candidates),
            "kept": len(kept),
            "committed": True,
        }
        logger.info("%s: %s", PIPELINE_NAME, counts)
        return counts
