# finance-transaction-identity Specification

## Purpose
Derives a bank transaction's durable identity from the provider payload so that
a transaction re-fetched at any later time is recognised as the same
transaction, for providers whose advertised stable reference is not actually
stable across fetches.

## Requirements

### Requirement: A provider reference is trusted only when it is not positional

The ingest pipeline SHALL treat an ASPSP-supplied `entry_reference` as the
transaction's `stable_id` only when its value is not a booking-date-scoped
positional ordinal. A value consisting of an ISO-8601 date, a literal `.`, and
an integer followed by nothing else SHALL be rejected as an identity, because
such a value describes a transaction's *position* in a list rather than the
transaction, and the position changes when the list changes.

The rule SHALL be shape-based on the whole value, not a substring search, so
that a genuine opaque reference that merely contains punctuation is still
accepted.

#### Scenario: A positional ordinal is rejected as an identity
- **WHEN** a provider returns a transaction whose `entry_reference` is
  `2026-09-28.9`
- **THEN** the transaction's `stable_id` is the deterministic hash, not
  `2026-09-28.9`

#### Scenario: A genuine opaque reference is accepted unchanged
- **WHEN** a provider returns a transaction whose `entry_reference` is
  `ASPSP-REF-1`
- **THEN** the transaction's `stable_id` is `ASPSP-REF-1`

#### Scenario: A null reference falls back to the hash
- **WHEN** a provider returns a transaction with `entry_reference` null
- **THEN** the transaction's `stable_id` is the deterministic hash

#### Scenario: Punctuation alone does not disqualify a reference
- **WHEN** a provider returns a transaction whose `entry_reference` is
  `REF.2026.0001` or `0912-3456-7890`
- **THEN** the transaction's `stable_id` is that reference, because it does not
  consist solely of a date, a dot and an integer

### Requirement: Identity is stable across repeated fetches

Re-fetching the same transaction over an overlapping window SHALL NOT create a
second row in `bronze.finance.raw_transactions`. The identity used for the merge
SHALL be derived only from values that do not change between fetches of the same
transaction.

#### Scenario: A re-fetch merges rather than inserting
- **WHEN** the same booking day is ingested twice while the bank's transaction
  list has shifted such that the transaction's position changed
- **THEN** bronze holds one row for that transaction and the second ingest
  reports it as an update, not an insert

#### Scenario: Genuinely distinct transactions keep distinct identities
- **WHEN** two transactions share a booking date, an amount, a currency and a
  counterparty but differ in remittance text
- **THEN** they receive different `stable_id` values and both are retained

### Requirement: An unusable reference is reported, not silently substituted

The pipeline SHALL record enough evidence to distinguish a hash-derived identity
from a provider-supplied one, so that a bank which stops supplying a usable
reference is discoverable after the fact rather than inferred from duplicate
rows. The untouched provider payload already stored per row SHALL be sufficient
for this; no additional column is required.

#### Scenario: The provider's own value remains auditable
- **WHEN** a row's `stable_id` is hash-derived because its `entry_reference` was
  rejected
- **THEN** the raw payload for that row still contains the provider's original
  `entry_reference`, so the rejection can be reviewed against the wire value

### Requirement: A transaction has one curated row however many identities the scrape produced

`silver.finance.transactions` SHALL hold at most one row per payment, keyed on
the same values the hash identity is built from — `provider`, `account_id`,
`booking_date`, `amount`, `currency`, `remittance_info` and the counterparty
(`creditor_name` falling back to `debtor_name`). When several rows share that
key, the row whose `stable_id` is **not** a positional ordinal SHALL be the one
kept, because that is the identity the pipeline mints going forward; a
positional row SHALL survive only when it is the sole row for that payment.

This holds regardless of how many fetches produced rows for that payment, so a
later backfill that re-mints an identity for a legacy row collapses into the
same single row rather than adding another.

#### Scenario: A legacy ordinal row and its hash twin collapse to the hash row
- **WHEN** the curated layer holds one row whose `stable_id` is `2026-01-15.0`
  and another whose `stable_id` is the hash for the same payment
- **THEN** `silver.finance.transactions` holds exactly one row for that payment
  and its `stable_id` is the hash

#### Scenario: A payment with only a positional identity is kept
- **WHEN** a payment's only row carries a positional `stable_id`, because no
  fetch has covered its booking date since the identity rule changed
- **THEN** that row is retained, and the payment does not disappear from the
  curated layer

#### Scenario: Genuinely distinct payments are not collapsed
- **WHEN** two rows differ in any of the payment key's values
- **THEN** both are retained

### Requirement: A superseded identity is retired from the budget app

The pipeline SHALL be able to remove the budget-app transactions whose identity
was superseded, without removing any transaction the curated layer still holds.
A transaction is a candidate for retirement only when its imported id is one the
pipeline itself wrote **and** the stable id in that imported id is positional in
shape **and** that stable id no longer appears in `silver.finance.transactions`.
A row the operator wrote by hand, and a row keyed on a genuine provider
reference, are never candidates.

The step SHALL be read-only unless explicitly enabled, SHALL report every
candidate before writing, and SHALL refuse to run when the curated layer is
empty — the one input that would make every positional row a candidate.

#### Scenario: A superseded positional row is retired
- **WHEN** the app holds a transaction imported as `enablebanking:2026-01-15.0`
  and no such stable id exists in the curated layer, while a hash-keyed row for
  the same payment does
- **THEN** the run reports it as a candidate, and with writing enabled tombstones
  it, leaving one row for that payment

#### Scenario: A lone positional row is not retired
- **WHEN** the app holds `enablebanking:2026-01-15.0` and that stable id is still
  present in the curated layer because it is the payment's only row
- **THEN** the run does not report it and never removes it

#### Scenario: A genuine provider reference is not retired
- **WHEN** the app holds `enablebanking:ASPSP-REF-1`, which does not appear in
  the curated layer but is not positional in shape
- **THEN** it is not a candidate

#### Scenario: The run is a dry run until enabled
- **WHEN** the run executes without the enable flag
- **THEN** it logs the candidate count and the rows, and commits nothing

#### Scenario: An unreadable curated layer stops the run
- **WHEN** the curated layer reports no rows
- **THEN** the run fails loudly instead of planning to retire every positional
  transaction
