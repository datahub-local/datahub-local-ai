# Spec Delta

## ADDED Requirements

### Requirement: A rejected draft is carried into the retry

A rejected draft SHALL be passed back to the drafting pass that regenerates it, so the retry edits
the draft the review just rejected rather than writing a new one from nothing. The retry SHALL carry
the most recent attempt's draft and not an earlier one, SHALL render an empty block on the first
attempt, and SHALL NOT require a second lookup for material the run already holds.

#### Scenario: The retry edits the rejected draft

- **WHEN** the review rejects a draft and the drafting prompt is rendered again
- **THEN** the prompt carries the draft that was just rejected
- **AND** the drafting rules ask for that draft to be edited rather than replaced

#### Scenario: A third attempt edits the second draft

- **WHEN** a run reaches a second retry
- **THEN** the prompt carries the most recent rejected draft
- **AND** it does not carry the first attempt's draft

#### Scenario: The first attempt carries no draft

- **WHEN** the drafting prompt is rendered for the first attempt
- **THEN** the previous-draft block is empty
- **AND** the drafting rules are not told to edit a draft that does not exist

#### Scenario: A retry does not search again

- **WHEN** a drafting turn is a retry
- **THEN** it writes from the source material the run already holds
- **AND** it does not repeat a lookup the run has already made
