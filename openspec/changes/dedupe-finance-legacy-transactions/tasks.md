# Tasks

## 1. One row per payment in silver (dbt)

- [ ] 1.1 Add a `finance_is_positional_id(expr)` macro to
  `workflows/dbt/projects/finance/macros/finance_cross_engine.sql`, dispatching to
  `regexp_like` on Trino and `regexp_matches` on DuckDB with the adapter's
  `^\d{4}-\d{2}-\d{2}\.\d+$` pattern; verify `uv run dbt parse --project-dir
  projects/finance --profiles-dir projects/finance --target local` is clean
- [ ] 1.2 Collapse `models/silver/transactions.sql` to one row per payment
  (`ROW_NUMBER() OVER (PARTITION BY provider, account_id, booking_date, amount,
  currency, remittance_info, COALESCE(creditor_name, debtor_name) ORDER BY <is
  positional> ASC, _ingested_at DESC)`, keeping the existing column list and the
  accounts join untouched
- [ ] 1.3 Add `projects/finance/tests/assert_unique_transaction_payment_key.sql`
  (a singular test selecting payment keys with more than one row) and confirm it
  **fails** against the live warehouse before the model change is applied
- [ ] 1.4 Seed a legacy positional row twinned with `S1` in
  `workflows/dbt/tests/finance/test_integration.py` and add a test asserting the
  hash row survives and the ordinal one does not; confirm the existing Silver and
  Gold assertions still hold, and that the new test **fails** before 1.2
- [ ] 1.5 Add the structural assertions to
  `workflows/dbt/tests/finance/test_models.py` (`ROW_NUMBER()`, `payment_rank = 1`,
  `finance_is_positional_id`)
- [ ] 1.6 Run `uv run pytest tests/finance` and `uv run ruff check .` from
  `workflows/dbt`

## 2. Retire the superseded identities in Actual (dlt)

- [ ] 2.1 Add `imported_transactions()` and `delete(transaction)` to the
  `BudgetClient` protocol and `_ActualPaymentClient` in
  `workflows/dlt/projects/finance/sync.py`, reading only
  `enablebanking:`-prefixed, non-tombstoned rows
- [ ] 2.2 Add `config.prune_apply()` (`FINANCE_PRUNE_APPLY`, default false)
- [ ] 2.3 Add `workflows/dlt/projects/finance/prune.py` exposing `run(target)`:
  read silver's full `stable_id` set (raise on empty), read the app's imported
  rows, report the candidates (positional-shaped suffix absent from silver),
  tombstone and commit only when `prune_apply()` is true
- [ ] 2.4 Add `workflows/dlt/tests/finance/test_prune.py`: the superseded id is a
  candidate and the twin-excluded legacy id is not; an absent-but-non-positional
  reference is not; a foreign `financial_id` is never touched; a dry run does not
  commit; an empty silver raises
- [ ] 2.5 Run `uv run pytest tests/` and `uv run ruff check .` from `workflows/dlt`

## 3. Apply to the live fleet

- [ ] 3.1 `dbt build --project finance --select silver.transactions+ --target homelab`
  and record the silver row count before (297) and after (169 expected), plus the
  `PASS`/`ERROR` summary of the new test
- [ ] 3.2 `dlt_runner --pipeline prune --project finance --target homelab` (dry
  run) and record the candidate count (128 expected) and that the 29 positional
  ids still present in silver are reported as kept
- [ ] 3.3 Ask the operator before writing: show the dry-run plan, then re-run with
  `FINANCE_PRUNE_APPLY=true` and record the app's transaction count before (297)
  and after (169 expected)
- [ ] 3.4 Confirm the next `dlt_sync_finance` run adds nothing
  (`{'read': 169, 'added': 0, ...}`) and that `gold.monthly_category_spend`
  `transaction_count` is no longer doubled
- [ ] 3.5 Update `workflows/dlt/README.md` with the two-command operator step and
  the reason the purge is manual

## 4. Record the outcome

- [ ] 4.1 `openspec validate --all` is clean
- [ ] 4.2 Archive with `openspec archive dedupe-finance-legacy-transactions`
