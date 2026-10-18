# Spec Delta

## ADDED Requirements

### Requirement: A human retry is handed the draft the human rejected

When a person asks for changes to a draft they read, the drafting pass that regenerates it SHALL
receive the draft they were reading, so the change is an edit rather than a fresh article. The draft
SHALL be the one that was on screen when the feedback was written and not an earlier round's, the
first pass SHALL send none, and the pass SHALL prefer a draft rejected inside the same invocation
over the caller's.

#### Scenario: A human asks for one change

- **WHEN** a person answers the approval with feedback and the graph re-enters the drafting
  sub-workflow
- **THEN** the drafting prompt carries the draft they were reading
- **AND** the parts of it the feedback does not name are kept

#### Scenario: A third round edits the second draft

- **WHEN** a draft is sent for review a second time and rejected again
- **THEN** the drafting prompt carries the most recently reviewed draft
- **AND** it does not carry the first round's draft

#### Scenario: The first authoring sends nothing

- **WHEN** the drafting sub-workflow is called for the first time in a run
- **THEN** no previous draft is passed
- **AND** the prompt's previous-draft block is empty

#### Scenario: The internal review loop is unaffected

- **WHEN** the drafting pass is re-rendered by the internal review gate inside one invocation
- **THEN** it edits the draft that gate just rejected
- **AND** the caller's draft does not displace it
