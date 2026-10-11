# Proposal

## Why

`2026-10-09-fix-finance-transaction-identity` stopped trusting Openbank's
positional `entry_reference` and re-keyed transactions onto a hash, but
explicitly deferred retiring the rows already landed under the positional id
(that change's non-goals). Both populations therefore coexist, and every
consumer reads both:

- `silver.finance.transactions` holds **297 rows for ~169 payments** on
  2026-10-11; 128 payments carry a positional and a hash `stable_id`.
- The Actual Budget sync dedupes on `imported_id = "enablebanking:<stable_id>"`
  (`sync.py`), so each hash id was imported as a *new* transaction beside the
  positional one. Measured in `job-dlt-sync-actual-wsfpeoq2`:
  `{'read': 297, 'added': 123, 'skipped': 174}` — the budget the operator reads
  now shows two of every payment.
- `gold.monthly_category_spend` sums silver, so its `amount` and
  `transaction_count` are roughly doubled.

Bronze holds 157 positional rows; 128 have a hash twin and **29 do not** — they
are booked around `2026-08-24` and predate the 2026-09-01 re-fetch window, so the
fix never minted a hash id for them. Deleting the positional rows in the lake
would therefore lose 29 real transactions, and the daily ingest re-fetches a
rolling **28-day** window (`DEFAULT_LOOKBACK_DAYS`) with a `--strategy longest`
backfill available, so a one-off bronze delete cannot hold: a later backfill
re-mints a hash id and the pair returns.

## What Changes

- **Silver collapses to one row per payment**, preferring the non-positional
  `stable_id`. A positional row survives only when it is the only copy of that
  payment (the 29).
- A **dbt singular test pins one row per payment key**, so the class fails the
  build instead of silently reappearing.
- A new one-off, **dry-run-by-default maintenance pipeline** (`--pipeline
  prune`) tombstones the Actual transactions whose identity was superseded —
  the positional-shaped `financial_id`s that no longer appear in silver — and
  nothing else.
- **Bronze is left untouched.** It stays the append-only landing record; the
  rule is enforced in the curated layer consumers actually read.

## Non-goals

- **No bronze deletion or rewrite.** The 128 redundant rows stay as the record
  of what the bank emitted and of the ordinal shape.
- **No change to `_stable_id()` or the ingest window.** The identity rule is
  correct; this change cleans up behind it.
- **No new identity shape**, no `reference_rejected` column — the rejection
  stays auditable through the untouched `payload_json`.
- **No purge in the daily DAG.** The duplicate rows are a one-off consequence of
  one change; the pipeline is run once, by hand.
- **No change to which copy survives**: the pipeline-owned hash row is kept, in
  both the lake and the app, as it is the identity the pipeline will mint from
  now on.

## Capabilities

### Modified Capabilities

- `finance-transaction-identity`: adds the curated-layer rule that a transaction
  has exactly one row however many identities the bank's list produced for it,
  and the app-side retirement of the superseded one.

## Impact

- `workflows/dbt/projects/finance/models/silver/transactions.sql` — dedup.
- `workflows/dbt/projects/finance/macros/finance_cross_engine.sql` — a
  cross-engine positional-id predicate.
- `workflows/dbt/projects/finance/tests/assert_unique_transaction_payment_key.sql`
  (new) — the permanent guard.
- `workflows/dbt/tests/finance/test_integration.py`, `test_models.py` — the
  seeded pair and the structural checks.
- `workflows/dlt/projects/finance/prune.py` (new), `sync.py` (its Actual client
  gains read/delete of the pipeline's own rows), `config.py` (`prune_apply`),
  `workflows/dlt/tests/finance/test_prune.py` (new).
- `workflows/dlt/README.md` — the operator step.
- No published schema change, no secret change, no new dependency.
