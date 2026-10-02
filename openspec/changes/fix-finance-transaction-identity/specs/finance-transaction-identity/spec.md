# Spec Delta

## Purpose

Derives a bank transaction's durable identity from the provider payload so that
a transaction re-fetched at any later time is recognised as the same
transaction, for providers whose advertised stable reference is not actually
stable across fetches.

## ADDED Requirements

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
