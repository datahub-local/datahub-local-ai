# Tasks

## 1. Reject a positional provider reference (dlt)

- [x] 1.1 Add a module-level compiled pattern and a `_is_positional_reference(value)` helper to `workflows/dlt/projects/finance/providers/enablebanking.py`, matching the whole value against an ISO date, a literal `.` and an integer; verify `uv run --with pytest pytest tests/finance/test_enablebanking.py -q` still passes and `uv run ruff check projects/finance/providers/enablebanking.py` is clean
- [x] 1.2 Change `_stable_id()` so `entry_reference` is returned only when it is truthy **and** not positional; verify the existing `test_entry_reference_is_the_stable_id` still passes unchanged for the genuine reference `ASPSP-REF-1`
- [x] 1.3 Add a test asserting a date-ordinal `entry_reference` (`2026-09-28.9`, and the 0-indexed `2026-09-23.0`) yields the 32-hex hash instead of the raw value, and confirm it **fails** against the pre-change code before the fix is applied
- [x] 1.4 Add tests for the boundary cases the design names: a null reference hashes, and references that merely contain punctuation (`REF.2026.0001`, `0912-3456-7890`, `ASPSP-REF-1`) are returned unchanged
- [x] 1.5 Run the full dlt suite (`uv run --with pytest pytest tests/ -q`) and `uv run ruff check .`, confirming no regression outside the finance provider tests

## 2. Correct the record (docs)

- [x] 2.1 Update `docs/specs/005-personal-finance-datalake.md` gate row 5 and §4.1's stable-id rule: state that an ASPSP reference is used only when it is not a booking-date ordinal, and that the hash is the fallback for any reference failing that check — not only for a null one
- [x] 2.2 Date-stamp the superseded Openbank observation in the same file (it records `entry_reference` as null on every row, read from a single 2026-09-14 sample; the live data on 2026-10-01 has 140 of 156 rows positional) by correcting it in place rather than deleting it, and verify the sibling relative links still resolve
- [x] 2.3 Update the identity paragraph in `workflows/dlt/README.md` so it no longer states that `entry_reference` is always usable when present, naming the positional shape as the exception
- [x] 2.4 Update the `_stable_id()` docstring and the module docstring in `providers/enablebanking.py` to describe the shape check, keeping both short and free of the incident history

## 3. Verify against the live warehouse

- [x] 3.1 Re-run the finance ingest over an overlapping window on `homelab` and confirm from the task log that the previously ordinal-keyed transactions arrive with hash `stable_id`s, recording the row counts before and after — ran `dlt ingest --project finance --target homelab` with `FINANCE_FROM_DATE=2026-09-01`, `FINANCE_TO_DATE=2026-10-09` **ingest only** (not the DAG, so the changed ids do not reach the Actual sync). Log: 137 transactions fetched, `raw_transactions` load step finished. `bronze.finance.raw_transactions` **before** 174 rows (157 positional, 17 hash) → **after** 294 rows (157 positional, 137 hash). Every previously ordinal-keyed row now has a hash id with its original reference kept in `payload_json` (e.g. booking 2026-09-28 `2026-09-28.0`… now `3afa5b74…`, `entry_reference` still `2026-09-28.0`)
- [x] 3.2 Confirm the re-fetch is idempotent: run the same window a second time and verify bronze reports no further inserts for those transactions — second run over the same window fetched the same 137 rows; `bronze.finance.raw_transactions` unchanged at 294 rows (157 positional / 137 hash), so the merge key produced no further inserts
- [x] 3.3 Query `bronze.finance.raw_transactions` and report the measured row count and the number of rows that are now duplicated (same booking date, amount and remittance under two ids); this is the input to the separate cleanup change, not something this change resolves — measured after the re-ingest: **294** rows total; **128** `(booking_date, amount, remittance_info)` keys carry two ids each, and in every one the pair is exactly one positional + one hash (128 + 128 = **256** rows across both populations); the remaining **38** keys are single-id. (8 more pairs than the 120 new hash rows: 8 pre-existing hash-keyed rows already shared a key with an ordinal row.)
- [x] 3.4 Confirm `silver.finance.transactions` still builds and the dbt tests pass after the ingest, so the changed ids propagate without breaking a model — `dbt build --project finance --target homelab --select silver.*`: `PASS=13 WARN=0 ERROR=0 SKIP=0`; `silver.finance.transactions` materialised with 294 rows, `not_null_transactions_stable_id` among the passing tests
