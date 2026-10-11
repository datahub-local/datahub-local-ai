# Tasks

## 1. One row per payment in silver (dbt)

- [x] 1.1 Add a `finance_is_positional_id(expr)` macro to
  `workflows/dbt/projects/finance/macros/finance_cross_engine.sql`, dispatching to
  `regexp_like` on Trino and `regexp_matches` on DuckDB with the adapter's
  `^\d{4}-\d{2}-\d{2}\.\d+$` pattern; `dbt parse --target local` clean
- [x] 1.2 Collapse `models/silver/transactions.sql` to one row per payment
  (`ROW_NUMBER() OVER (PARTITION BY provider, account_id, booking_date, amount,
  currency, remittance_info, COALESCE(creditor_name, debtor_name) ORDER BY <is
  positional> ASC, _ingested_at DESC)`, column list and accounts join unchanged —
  the outer `FROM` became a `ranked` CTE and gained `WHERE payment_rank = 1`
- [x] 1.3 Add `projects/finance/tests/assert_unique_transaction_payment_key.sql`
  and confirm it fails against the live warehouse before the model change: ran it
  against Trino on 2026-10-11 — `FAIL 128` (`Got 128 results`) against the
  pre-change 297-row silver
- [x] 1.4 Seed a legacy positional row twinned with `S1` in
  `workflows/dbt/tests/finance/test_integration.py` and add a test asserting the
  hash row survives; confirmed the change is load-bearing by reverting the dedup
  predicate — the build then fails on the new singular test and every Silver test
  errors, and `test_ranks_rows_within_one_payment` fails
- [x] 1.5 Add the structural assertions to
  `workflows/dbt/tests/finance/test_models.py` (dedup CTE, `payment_rank = 1`,
  `finance_is_positional_id`, `_ingested_at DESC`, the per-engine macros)
- [x] 1.6 `uv run pytest tests/finance` → 45 passed; `uv run ruff check .` → the
  two pre-existing `PLW1510` errors in other projects' tests, none in finance

## 2. Retire the superseded identities in Actual (dlt)

- [x] 2.1 Add `imported_transactions()` and `delete(transaction)` to the
  `BudgetClient` protocol and `_ActualPaymentClient` in
  `workflows/dlt/projects/finance/sync.py`, reading only
  `enablebanking:`-prefixed, non-tombstoned rows; deletion sets `tombstone = 1`
  (Actual has no hard delete)
- [x] 2.2 Add `config.prune_apply()` (`FINANCE_PRUNE_APPLY`, default false)
- [x] 2.3 Add `workflows/dlt/projects/finance/prune.py` exposing `run(target)`:
  reads silver's full `stable_id` set (raises on empty), reads the app's imported
  rows, logs every candidate (positional-shaped suffix absent from silver), and
  tombstones plus commits only when `prune_apply()` is true
- [x] 2.4 Add `workflows/dlt/tests/finance/test_prune.py`: the superseded id is
  the only candidate, a lone positional row is kept, an absent-but-non-positional
  reference is untouched, a foreign prefix is out of scope, a dry run does not
  commit, the `local` target never writes, and an empty silver raises
- [x] 2.5 `uv run pytest tests/` → 175 passed; `uv run ruff check` clean on
  `prune.py`, `sync.py` and the new test (the 19 `PLC0414` in `config.py` are the
  pre-existing re-export aliases)

## 3. Apply to the live fleet

- [x] 3.1 `dbt build --project finance --target homelab --select "silver.* gold.*
  assert_unique_transaction_payment_key"` — `silver.finance.transactions`
  **297 → 169 rows**, `assert_unique_transaction_payment_key` **PASS**,
  `gold.monthly_category_spend` rebuilt to 38 rows, `PASS=20 ERROR=0`
- [x] 3.2 `--pipeline prune --target homelab` dry run — `imported=297
  superseded=128 kept_positional=29 apply=False`, every candidate logged with
  account, date, amount and payee
- [x] 3.3 Operator approved the plan; re-ran with `FINANCE_PRUNE_APPLY=true` —
  `{'silver': 169, 'superseded': 128, 'kept': 29, 'committed': True}`, app
  transactions 297 → 169
- [x] 3.4 Confirmed stable: prune re-run reports `imported=169 superseded=0
  kept_positional=29`; sync dry run `read 169, already present 169, would_add 0`;
  gold is rebuilt. The DAG-level acceptance (a `skip_ingest=true` run ending in
  `added 0`) is the remaining post-archive verification: the `:main` dbt image was
  rebuilt from `7227848` at 2026-10-11T09:46Z, so a run now carries the deduped
  silver model and must end `added 0`.
- [x] 3.5 `workflows/dlt/README.md` gains the `--pipeline prune` section, the
  three-command operator step and the `FINANCE_PRUNE_APPLY` row

## 4. Record the outcome

- [x] 4.1 `openspec validate --all` clean
- [x] 4.2 Archived with `openspec archive dedupe-finance-legacy-transactions` once the
  `:main` dbt image carried the fix; the `skip_ingest` DAG run (3.4) is left as a
  post-archive verification rather than a gate on the archive
