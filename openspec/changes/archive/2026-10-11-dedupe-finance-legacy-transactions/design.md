# Design

## Context

Read `proposal.md` for the counts. The shape of the fix is decided by three
measured facts:

- Bronze's positional population is **not fully superseded**: 128 of 157 have a
  hash twin, 29 do not (`2026-08-24` onward, before the re-fetch window).
- The ingest re-fetches a rolling **28-day** window every day, and
  `FINANCE_FETCH_STRATEGY=longest` exists for a backfill. So the set of pairs can
  grow after any cleanup that deletes instead of deduping.
- The Actual sync's dedup key is `stable_id`, and nothing in the pipeline ever
  removed an app row. The sync is a pure insert-if-absent, which is why the app
  doubled the moment silver gained a second id per payment.

## Goals / Non-Goals

**Goals:**

- One row per payment in the curated layer, whichever id shape the row carries.
- The app cleaned without losing the 29 payments that have only a positional id.
- A permanent gate so the same class fails loudly if it ever returns.

**Non-Goals:**

- Deleting or rewriting bronze.
- Changing `_stable_id()` / the positional rule (already correct).
- Making the sync delete anything on a normal run.

## Decisions

### Dedupe in silver, not by deleting bronze rows

Silver is what consumers read (`gold.*`, the Actual sync, the semantic layer), so
one row there is the whole fix; bronze is the landing record and stays as it is.

*Alternatives considered.*

- **Delete the 128 backed positional rows from bronze.** Fixes today's pairs but
  not tomorrow's: a `longest` backfill re-mints a hash id for the 29 legacy rows
  and the pair returns, with nothing left to dedupe it. It is also destructive
  DDL against the one layer that records what the bank actually emitted.
- **Delete *all* positional bronze rows.** Loses the 29 payments from the lake
  (and, after the app purge, from the budget too) — irrecoverable history, the
  cost spec 005 §1.2 exists to avoid.
- **Key the merge on the hash so bronze self-heals.** The merge key already
  cannot collide the two populations; the colliding value is `stable_id` itself,
  so this needs the same silver-side collapse plus an ingest rewrite.

### The survivor is chosen by shape, not by recency

`ROW_NUMBER() OVER (PARTITION BY <payment key> ORDER BY <is positional> ASC,
_ingested_at DESC)` — a non-positional id always wins, and among equals the
latest row does. Choosing by `_ingested_at` alone would work on today's data
(the hash rows are the later fetch) but it encodes "newest wins", which is not
the rule; the rule is "a positional ordinal is not an identity", and the model
says exactly that.

*Alternative considered:* order by `LENGTH(stable_id) = 32`. Rejected — the hash
length is an implementation detail of the adapter, and the test would pin a
coincidence.

### The payment key is the identity's own input set

`(provider, account_id, booking_date, amount, currency, remittance_info,
COALESCE(creditor_name, debtor_name))`. The adapter's hash branch keys on exactly
these values (`_stable_id()`), so two rows sharing this key would already have
collapsed in bronze under `merge`; the silver collapse therefore cannot lose a
row bronze had kept.

*Alternative considered:* a natural key of `(booking_date, amount, remittance)`
alone. Rejected as narrower than the hash inputs: it could merge rows the hash
treats as distinct.

### The positional predicate exists in three places, and that is the cost

The rule (`^\d{4}-\d{2}-\d{2}\.\d+$`) lives in the adapter
(`_POSITIONAL_REFERENCE`), in a cross-engine SQL macro (Trino `regexp_like`,
DuckDB `regexp_matches`), and the prune pipeline imports the adapter's compiled
pattern rather than re-writing it. Warehouse-side dedup cannot call Python, so
the SQL copy is unavoidable; the mitigation is a test, not a comment: the DuckDB
integration test seeds a pair and asserts the *hash* row survives, so a macro
that stopped matching would fail a build rather than silently keep the ordinal.

### The purge deletes exactly "positional, and gone from silver"

`--pipeline prune` reads silver's `stable_id` set (the whole table, no window),
reads every app transaction the pipeline imported, and tombstones those whose
suffix is positional-shaped **and absent from silver**. Properties that fall out:

- **Self-guarding before the dedup lands.** Run it before the dbt rebuild and
  silver still holds all 157 positional ids, so there are zero candidates and it
  reports nothing to do. There is no ordering trap and no need to assert that
  the rebuild happened.
- **The 29 are spared without special-casing.** They survive in silver as the
  sole copy, so their ids are present and are never candidates.
- **A genuine opaque reference is never touched**, even though it too may be
  absent from silver: the shape check gates it.
- **Human rows are out of scope.** Only `enablebanking:`-prefixed financial ids
  are considered.
- **An empty silver is a hard error**, not a plan to delete everything — the one
  input that could turn this into a mass deletion is rejected.

*Alternatives considered.*

- **Purge from the sync on every run.** Deletion inside the daily insert path
  makes the DAG able to remove budget rows unattended, for a one-off migration.
  Rejected; the pipeline is run by hand once.
- **Purge by the app's own sibling check** (a positional row next to a
  same-day, same-amount hash row). Rejected as the primary rule: it re-derives
  a key the app only holds in truncated form (`notes` is capped at 200), and it
  treats two coincidentally identical same-day purchases as a pair. The
  absent-from-silver rule is exact because silver is the authoritative id set.
- **A dedicated maintenance script rather than a pipeline.** Rejected: the dlt
  runner discovers `run(target)` modules, so `prune.py` gets the CLI, the target
  handling and the log format for free, and is unit-testable like `sync`.

### Deletion in Actual is a tombstone, and a dry run is the default

actualpy's `Transactions.delete()` sets `tombstone = 1` — Actual has no hard
delete. The pipeline writes only when `FINANCE_PRUNE_APPLY` is truthy; unlike the
sync (where a local target is the dry run), a homelab run is *also* a dry run
unless asked, because the operation is destructive and one-off. The plan is
always logged with account, date, amount, payee and financial id, so `--apply`
can be approved against visible rows.

## Risks / Trade-offs

**[The model's partition key is written a second time, in SQL.]** → Accepted;
it is the same expression the adapter hashes. A drift shows up as duplicate
rows in the dbt test, which is the failure this change is about, so it cannot
pass silently in the direction that loses data.

**[Collapsing on the payment key merges two genuinely distinct same-day
purchases that the bank reports identically.]** → Not a new loss: the adapter's
hash already keys on the same values, so bronze's `merge` collapsed those two
before silver saw them.

**[A positional row outside every fetch window keeps its positional id in silver
and in the app forever.]** → Expected. It is the only copy of that payment;
re-keying it needs a fetch that covers its date (`--strategy longest`).

**[The purge is a manual step, so it can be forgotten.]** → The duplicate rows
stay visible in the budget and the dbt test defines what "done" means; the
README states the two commands. Nothing else in the fleet re-imports them,
because after the dedup the sync's window no longer contains a positional id.

## Open Questions

_None at archive time._ The superseded Actual rows that the operator had
categorised or renamed by hand are not distinguishable from pipeline-written
ones in this data (both copies were categorised by the same generated rules), so
both are treated as pipeline rows. If a rename is ever found on a positional
copy, the report prints each candidate in full before `--apply`.

## Definition of Done

- `dbt build --project finance --target homelab` passes, including the new
  uniqueness test, and `silver.finance.transactions` holds one row per payment.
- `--pipeline prune --project finance --target homelab` reports 128 candidates
  in a dry run, and the budget holds one row per payment after `--apply`.
- `uv run pytest` and `uv run ruff check .` are clean in `workflows/dlt`;
  `uv run pytest tests/finance` is clean in `workflows/dbt`.
