# Spec Delta

## ADDED Requirements

### Requirement: The entry point reaches the writer through Article Creator

Every article writer turn SHALL run inside `Article Creator`. The entry point SHALL select the
turn with a `TASK` input whose values are `draft`, `aspects` and `improve`, defaulting to `draft`,
and SHALL NOT post to the writer adapter itself. The entry point SHALL pass the draft of record,
the merged findings and, on a retry, the objective problem named by its code re-check into the
sub-workflow; the sub-workflow SHALL answer the adapter's result, so the entry point reads one
response shape for a direct call and for a sub-workflow answer.

A task the sub-workflow does not implement SHALL fail the run naming the task, and SHALL NOT fall
back to drafting.

#### Scenario: The aspect pass is a call to the sub-workflow

- **WHEN** the improvement pass starts
- **THEN** the entry point calls `Article Creator` with `TASK` `aspects` and the draft of record
- **AND** the entry point contains no HTTP node that posts to the writer adapter

#### Scenario: The edit pass is a call to the sub-workflow

- **WHEN** the findings or human feedback call for an edit
- **THEN** the entry point calls `Article Creator` with `TASK` `improve`, the draft of record and the merged findings
- **AND** a retry also carries the objective problem the code re-check named

#### Scenario: An unimplemented task does not draft

- **WHEN** a caller asks `Article Creator` for a task it does not implement
- **THEN** the run fails naming the task
- **AND** no draft is spent

#### Scenario: The answer crosses the boundary unchanged

- **WHEN** the sub-workflow returns an aspect or edit answer
- **THEN** the entry point's parser reads the same status and body it would read from a direct call
- **AND** a transport failure is still an error item, not a missing answer
