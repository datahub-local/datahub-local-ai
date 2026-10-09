# Design

## Context

See `proposal.md` — Why, and `specs/finance-transaction-identity/spec.md` for
the requirements. What shapes the approach below is the current code:

`_stable_id()` in `workflows/dlt/projects/finance/providers/enablebanking.py`
already has both branches. It returns `str(entry_reference)` when that value is
truthy, and otherwise builds
`sha256(account_id | booking_date | amount | currency | remittance | counterparty)`
truncated to 32 hex characters. Nothing new has to be built: the fallback is
correct and already proven — it is the 16 of 156 live rows whose
`entry_reference` is null that carry hash ids today.

So the change is one predicate in front of an existing branch, not a new
strategy. The work is deciding exactly where the boundary sits between "this is
a reference" and "this is a position", and being honest about what the fallback
does and does not cover.

## Goals / Non-Goals

**Goals:**

- Reject a positional reference with the narrowest rule that covers the observed
  value, so no genuine reference is disqualified.
- Keep the identity derivation entirely inside the adapter. No consumer,
  schema, secret or downstream model changes.
- Leave the evidence needed to audit a rejection in place, at no new cost.

**Non-Goals:**

- Retiring the ordinal-keyed rows already in bronze. The merge key changes for
  those rows, so the next ingest adds a hash-keyed counterpart to each and the
  old row stays. That cleanup is destructive and belongs in its own change.
- Making identity independent of `booking_date`. See the trade-off below — it
  is a real limitation of the hash branch, not something this change hides.
- Touching `booking_date` vs `value_date`. Separate question, separate change.

## Decisions

### Reject by shape, matched against the whole value

The predicate is a full-match test for the exact shape Openbank returns: an
ISO-8601 date, a literal `.`, one or more digits, and then end of string —
`^\d{4}-\d{2}-\d{2}\.\d+$`.

*Alternatives considered.*

- **Reject any value containing a `.`.** Rejected: too broad. The spec's own
  example of a legitimate reference is `ASPSP-REF-1`, and banks commonly use
  dotted reference formats (`REF.2026.0001`). A punctuation rule would
  disqualify correct references and move those banks onto the hash branch for
  no reason, changing identity for rows that were fine.
- **Reject any value that parses as a date plus a suffix.** This is the same
  rule stated loosely; the anchored regex expresses it more precisely and cannot
  accidentally match a substring inside a longer reference.
- **Always hash, ignoring `entry_reference` entirely.** Rejected: it throws away
  the only directly-supplied identity from banks that do honour the field, and
  it would change the `stable_id` of every existing row at every bank at once —
  a far larger migration than the bug requires.
- **Keep trusting the field and dedupe downstream instead.** Rejected: the
  duplicate is created at the merge in bronze, and by the time a dbt model could
  see it, the old row may already have been evicted by the row cap. Deduping
  after the loss does not recover the loss.

### The predicate is a module-level compiled pattern with a named helper

A private `_is_positional_reference(value: str) -> bool` wraps a compiled
module-level pattern beside the existing `STABLE_ID_LENGTH` and `BOOK_STATUS`
constants. This keeps `_stable_id()` readable, gives the test a name to exercise
directly if wanted, and matches how the module already hoists its constants.

*Alternative considered:* inlining the regex in `_stable_id()`. Rejected — the
function already carries six parameters and the two branches; a bare regex
literal inside it would be the least legible part of the file and the hardest to
point a test at.

### The fallback stays exactly as it is

No change to the hash inputs, the truncation length, or the field separator.
Keeping it untouched means the 16 rows already hash-keyed keep their current
ids, so this change does not itself create a second population of duplicates
beyond the 140 ordinal-keyed rows it is fixing.

*Alternative considered:* adding `institution_id` or `provider` to the hash
input to make collisions even less likely. Rejected: it would change the id of
every existing hash-keyed row for no demonstrated benefit — the hash is already
scoped by a merge key that includes both.

### The wire value stays in `payload_json`, so no new column

The requirement that a rejection be auditable is satisfied by the existing
`payload_json` column, which holds the untouched provider object including the
original `entry_reference`. Adding a `reference_rejected` boolean would be a
second copy of a fact already derivable — the same objection this repository
already applies to comments beside values and committed generated files.

*Alternative considered:* a boolean column recording why the hash was used.
Rejected as a second copy that can drift: the shape rule can change, and a
stored flag would then describe a policy that is no longer in force, while the
payload stays true to what arrived.

## Risks / Trade-offs

**[The next ingest adds ~140 rows to bronze.]** → Expected and correct: the
merge key differs precisely for the rows being fixed, so each ordinal-keyed row
gains a hash-keyed counterpart. Bronze is at its 156-row cap today, so this
temporarily roughly doubles it. Stated as a non-goal; the cleanup change decides
how to retire the superseded rows. Worth measuring after the first ingest rather
than assuming the count.

**[The hash branch keys on `booking_date`, so an ASPSP that later re-dates a
booking would mint a new identity for that row.]** → Accepted and unchanged from
today's behaviour for the 16 rows already on this branch. It is the weaker half
of the fallback, and `value_date` is not a safe substitute (it is the spend
date, which is a different question — see the proposal's non-goals). Recorded
here so the next person does not mistake it for an oversight.

**[The rule is fitted to one bank's observed shape.]** → Mitigated by its
narrowness: a false negative (a positional reference in some other shape) leaves
that bank on the trusted branch, which is today's status quo rather than a new
regression, and the duplicate rows it produces remain visible in bronze. A false
positive (rejecting a genuine reference) would change identity for rows that were
fine, which is why the rule matches the whole value instead of a substring.

**[`docs/specs/005-personal-finance-datalake.md` records the opposite
observation.]** → The gate note says Openbank returns `entry_reference` null on
every row, read from one 2026-09-14 sample. Left uncorrected it would mislead the
next reader into believing this class of bank needs no handling. The task set
corrects it in place and dates the observation, rather than deleting it — the
existing convention for a superseded finding in that document.
