# Tasks

## 1. Reject a positional provider reference (dlt)

- [ ] 1.1 Add a module-level compiled pattern and a `_is_positional_reference(value)` helper to `workflows/dlt/projects/finance/providers/enablebanking.py`, matching the whole value against an ISO date, a literal `.` and an integer; verify `uv run --with pytest pytest tests/finance/test_enablebanking.py -q` still passes and `uv run ruff check projects/finance/providers/enablebanking.py` is clean
- [ ] 1.2 Change `_stable_id()` so `entry_reference` is returned only when it is truthy **and** not positional; verify the existing `test_entry_reference_is_the_stable_id` still passes unchanged for the genuine reference `ASPSP-REF-1`
- [ ] 1.3 Add a test asserting a date-ordinal `entry_reference` (`2026-09-28.9`, and the 0-indexed `2026-09-23.0`) yields the 32-hex hash instead of the raw value, and confirm it **fails** against the pre-change code before the fix is applied
- [ ] 1.4 Add tests for the boundary cases the design names: a null reference hashes, and references that merely contain punctuation (`REF.2026.0001`, `0912-3456-7890`, `ASPSP-REF-1`) are returned unchanged
- [ ] 1.5 Run the full dlt suite (`uv run --with pytest pytest tests/ -q`) and `uv run ruff check .`, confirming no regression outside the finance provider tests

## 2. Correct the record (docs)

- [ ] 2.1 Update `docs/specs/005-personal-finance-datalake.md` gate row 5 and §4.1's stable-id rule: state that an ASPSP reference is used only when it is not a booking-date ordinal, and that the hash is the fallback for any reference failing that check — not only for a null one
- [ ] 2.2 Date-stamp the superseded Openbank observation in the same file (it records `entry_reference` as null on every row, read from a single 2026-09-14 sample; the live data on 2026-10-01 has 140 of 156 rows positional) by correcting it in place rather than deleting it, and verify the sibling relative links still resolve
- [ ] 2.3 Update the identity paragraph in `workflows/dlt/README.md` so it no longer states that `entry_reference` is always usable when present, naming the positional shape as the exception
- [ ] 2.4 Update the `_stable_id()` docstring and the module docstring in `providers/enablebanking.py` to describe the shape check, keeping both short and free of the incident history

## 3. Verify against the live warehouse

- [ ] 3.1 Re-run the finance ingest over an overlapping window on `homelab` and confirm from the task log that the previously ordinal-keyed transactions arrive with hash `stable_id`s, recording the row counts before and after
- [ ] 3.2 Confirm the re-fetch is idempotent: run the same window a second time and verify bronze reports no further inserts for those transactions
- [ ] 3.3 Query `bronze.finance.raw_transactions` and report the measured row count and the number of rows that are now duplicated (same booking date, amount and remittance under two ids); this is the input to the separate cleanup change, not something this change resolves
- [ ] 3.4 Confirm `silver.finance.transactions` still builds and the dbt tests pass after the ingest, so the changed ids propagate without breaking a model
