# Proposal

## Why

The finance pipeline derives every transaction's identity from Enable Banking's
`entry_reference`, on the documented premise that it is "unique and immutable
... across multiple PSU authentication sessions". Openbank does not honour that:
it returns a **positional, 0-indexed ordinal scoped to the booking date** —
`2026-09-28.9` is literally "the tenth transaction booked on 28 September".
The field is renumbered whenever the bank's list shifts, so a late settlement
inserted mid-list gives every transaction after it a new `entry_reference`.

Verified live on 2026-10-01: 140 of the 156 rows in
`bronze.finance.raw_transactions` carry this date-ordinal shape, and the ordinal
runs `0..n-1` contiguously within each `booking_date`. The consequence is that
the merge key `(provider, account_id, stable_id)` never collides across fetches:
a re-fetched transaction arrives as a **new** row rather than an update. The same
45 € FOTO RIVAS CENTRO purchase is present twice under ids
`4727428c…` (2026-09-28 load) and `2026-09-28.9` (2026-09-30 load).

Two failures follow, and both are silent:

- **The lake accumulates duplicates and evicts real history.** Bronze sits at
  exactly its 156-row cap while re-registered copies consume capacity, and the
  oldest genuine transactions are what get dropped — the one irrecoverable cost
  in spec 005 §1.2.
- **Identity is not stable end to end.** `stable_id` is reused as Actual
  Budget's `imported_id`, so the same shifting value that defeats bronze's
  dedup also defeats the app's, and the date a transaction lands on is at the
  mercy of the same renumbering.

`docs/specs/005-personal-finance-datalake.md:322` records Openbank as having
`entry_reference` **null on every row** — true of the single 2026-09-14 sample it
was read from, false of the live data three weeks later. The design gate was
answered from one observation and never re-checked.

## What Changes

- The provider adapter stops trusting `entry_reference` unconditionally. A value
  that is a booking-date-scoped ordinal is **not** an identity and is rejected in
  favour of the existing deterministic hash.
- The rejection rule is shape-based and narrow (an ISO date, a literal `.`, and
  an integer), so a genuine opaque reference — including one that merely contains
  punctuation — is still honoured.
- `stable_id` becomes stable for Openbank rows: the hash branch already keys on
  `booking_date | amount | currency | remittance | counterparty`, all of which
  are constant for a given transaction, so a re-fetch merges instead of inserting.
- The stale gate finding in `docs/specs/005-personal-finance-datalake.md` is
  corrected and the rule restated: the ASPSP's reference is validated against a
  stable shape, and the hash is the fallback for any bank whose reference fails
  that check — not merely for a `null` one.
- The adapter's docstring and `workflows/dlt/README.md` stop asserting that
  `entry_reference` is always usable.

## Non-goals

- **No bronze cleanup in this change.** The 140 ordinal-keyed rows already in
  bronze will be joined by 140 hash-keyed counterparts on the next ingest, since
  the merge key differs for exactly the rows this fixes. Deciding how to retire
  the superseded rows — a one-off dedup keyed on the hash, or letting them age
  out — is a separate, destructive operation against live data and belongs in
  its own change.
- **No change to `booking_date` vs `value_date`.** Which date a consumer should
  read is a live question (the operator reads a transaction on `value_date`, the
  day the spend happened, while every consumer currently aggregates on
  `booking_date`). It is deliberately kept out of this change so the identity fix
  can land and be measured on its own.
- **No `transaction_id` revival.** Enable Banking documents it as unstable and
  it is null throughout this data; nothing here reintroduces it.
- **No change to the Actual Budget rows already written.** The `imported_id`
  dedup means the app keeps its existing 156 rows; a date or identity correction
  in the app is part of the cleanup change, not this one.

## Capabilities

### New Capabilities

- `finance-transaction-identity`: how the finance pipeline derives and validates
  a bank transaction's stable identity across fetches, for providers whose
  advertised reference is not actually stable.

### Modified Capabilities

_None — the only existing spec is `visual-studio`, which this change does not
touch._

## Impact

- `workflows/dlt/projects/finance/providers/enablebanking.py` — `_stable_id()`
  gains a shape check; a new private predicate and a module-level pattern.
- `workflows/dlt/tests/finance/test_enablebanking.py` — a new test that fails
  today (a date-ordinal `entry_reference` must yield a hash id) alongside the
  existing `test_entry_reference_is_the_stable_id`, which stays valid for a
  genuine reference.
- `docs/specs/005-personal-finance-datalake.md` — correct gate row 5 and §4.1's
  stable-id rule; mark the Openbank observation with its date.
- `workflows/dlt/README.md` — the identity paragraph.
- No new dependencies. No schema change: bronze already carries `stable_id` and
  the `payload_json` that proves the shape. No secret change.
- Downstream of bronze, nothing changes structurally — silver, gold, Superset and
  the sync all key off `stable_id` and keep working; what changes is that the
  value stops moving.
