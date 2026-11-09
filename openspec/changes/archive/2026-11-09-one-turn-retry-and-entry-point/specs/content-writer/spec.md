# Spec Delta

## REMOVED Requirements

### Requirement: A human retry is handed the draft the human rejected

**Reason**: The improvement pass it described is out of the automatic path, and its feedback-round
exceptions belong to a ledger rule that no longer exists.

**Migration**: None. The draft the person read is passed to the new draft as `previous_draft`, and
"A human retry re-drafts with the draft they rejected" states the behaviour.

### Requirement: The entry point reaches the writer through Article Creator

**Reason**: It prescribed `aspects` and `improve` calls the lane no longer makes.

**Migration**: None. "The entry point passes only the drafting task" states the one-turn path; the
other tasks remain available on demand.

## ADDED Requirements

### Requirement: A human retry re-drafts with the draft they rejected

When a person asks for changes to a draft they read, the entry point SHALL call `Article Creator`
with `TASK: draft` again, passing the draft they were reading and their feedback, and the turn
SHALL author in a session of its own rather than continuing the session it replaces. The new draft
SHALL pass the same drafting gate as the first, and SHALL be presented for review with the feedback
marked applied only when the body actually changed.

#### Scenario: A human asks for one change

- **WHEN** a person answers the review with feedback
- **THEN** the next draft is authored with that feedback and the draft they read
- **AND** the parts the feedback does not name are kept where the facts allow

#### Scenario: The retry is its own session

- **WHEN** the human retry runs
- **THEN** it starts in a new session with the previous draft in its brief
- **AND** it does not continue the transcript of the draft it replaces

#### Scenario: A review resumed in a later execution

- **WHEN** the approval is answered after the run that presented the draft has ended
- **THEN** the draft of record is read from the stored draft row
- **AND** the retry carries it

### Requirement: The entry point passes only the drafting task

Every article writer turn SHALL run inside `Article Creator`. The entry point SHALL select the turn
with a `TASK` input whose default is `draft` and SHALL pass `draft` for the automatic path, SHALL
NOT pass `aspects` or `improve`, and SHALL NOT post to the writer adapter itself. The sub-workflow
SHALL answer the adapter's result, so the entry point reads one response shape.

A task the sub-workflow does not implement SHALL fail the run naming the task, and SHALL NOT fall
back to drafting.

#### Scenario: The automatic path drafts once

- **WHEN** the entry point calls the writer for an entry
- **THEN** it passes `TASK: draft`
- **AND** it contains no HTTP node that posts to the writer adapter
- **AND** no aspect or edit call is made

#### Scenario: The other tasks stay available

- **WHEN** an operator asks `Article Creator` for `review`, `audit`, `aspects` or `improve`
- **THEN** the sub-workflow serves it
- **AND** the entry point does not pass it

#### Scenario: An unimplemented task does not draft

- **WHEN** a caller asks `Article Creator` for a task it does not implement
- **THEN** the run fails naming the task
- **AND** no draft is spent
