# Spec Delta

## REMOVED Requirements

### Requirement: A human retry re-drafts with the draft they rejected

**Reason**: It required a session of its own per retry, which lost the row's context and re-drafted
a different article.

**Migration**: None. "A human retry continues the row's session" states the behaviour.

## ADDED Requirements

### Requirement: A human retry continues the row's session

The writer's session SHALL be one per row for the row's whole life: the first draft SHALL open it,
and every later rejection, feedback round and retry SHALL continue it, so the turn keeps the pages
the row read and the asks it already applied. The request SHALL also carry the draft of record, so
a turn whose session is missing edits the draft the person read instead of drafting a different
one.

#### Scenario: A human asks for one change

- **WHEN** a person answers the review with feedback
- **THEN** the next turn continues the row's session
- **AND** it applies the feedback to the draft they read, keeping what the feedback does not name

#### Scenario: A retry after an automatic rejection

- **WHEN** the code gate rejects an attempt
- **THEN** the next attempt continues the same session
- **AND** it carries the gate's reason

#### Scenario: The session is gone

- **WHEN** the row's session cannot be read
- **THEN** the request's draft of record is the draft the turn edits
- **AND** the run does not start a different article

#### Scenario: A review resumed in a later execution

- **WHEN** the approval is answered after the run that presented the draft has ended
- **THEN** the draft of record is read from the stored draft row
- **AND** the retry carries it
