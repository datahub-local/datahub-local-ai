# Spec Delta

## ADDED Requirements

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
