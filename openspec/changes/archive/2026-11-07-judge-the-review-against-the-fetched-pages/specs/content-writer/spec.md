# Spec Delta

## ADDED Requirements

### Requirement: The review judges facts against the pages the writer fetched

The review gate SHALL judge a draft's facts, names, numbers, quotations and dates against the
entry's inputs, the entry's seed page, and every page the writer fetched during that run. The
fetched pages SHALL remain available to the review turn in the same session; the source ledger
continues to name the pages a fenced block was read on. A fact from a fetched page SHALL NOT be
rejected as invented merely because the seed page does not carry it.

A fact absent from the entry's inputs, the seed page and every fetched page SHALL be a failure,
and a citation of a page the writer did not fetch SHALL be a failure.

#### Scenario: A fact from a fetched page is sourced

- **WHEN** the draft states a fact that is on a page the writer fetched during the run
- **THEN** the review does not reject it for being absent from the seed page
- **AND** the seed page remains the entry's source, not the limit of the corpus

#### Scenario: A fact from nowhere is still invented

- **WHEN** the draft states a fact that is absent from the entry's inputs, the seed page and every fetched page
- **THEN** the review rejects it as invented

#### Scenario: A citation must name a fetched page

- **WHEN** the draft cites a URL the writer did not fetch during the run
- **THEN** the review rejects the citation
