# Spec Delta

## ADDED Requirements

### Requirement: The writer adapter owns every article model turn

The article lane's drafting, publish gate, aspect review and improvement edit SHALL each be a
turn of the writer adapter, in one session per entry. The workflow SHALL send the session id, the
entry's fields, the draft of record and any feedback, findings or objective problem; it SHALL
carry no prompt text, no aspect registry and no model node of its own. The adapter SHALL render
every prompt from files in its image.

A human rejection SHALL re-enter the same writer session as feedback, carrying the draft the
person read, so the feedback always reaches the writer.

The deterministic gates SHALL remain in the workflow: word budget, asset markers and source
ledger fidelity SHALL be counted in code, and a gate SHALL NOT accept a verdict a second copy of
the model's own count.

A turn that cannot answer SHALL be reported rather than silently pass. A gate turn SHALL reject
the draft with its transport failure named, so the retry carries the cause. An aspect turn that
fails SHALL contribute no findings and leave the other aspects running. An edit turn that
returns no article SHALL be reported failed, distinct from nothing to apply.

#### Scenario: A round's turns share one session

- **WHEN** a draft is reviewed, an aspect pass runs, or an edit is applied
- **THEN** each turn names the same session id as the draft
- **AND** the adapter renders the turn's prompt from its own files

#### Scenario: A human rejection reaches the writer

- **WHEN** a person answers the review with feedback
- **THEN** the aspect and edit turns run in the draft's session with that feedback
- **AND** the edit carries the draft the person was reading

#### Scenario: A gate turn that cannot answer is a rejection with its reason

- **WHEN** the review request fails or answers no verdict
- **THEN** the drafting loop retries with the failure named in the explanation
- **AND** the run does not end on the failed reviewer

#### Scenario: An edit turn that cannot answer is failed, not empty

- **WHEN** the edit request fails or returns no article
- **THEN** the outcome is reported failed with the reason
- **AND** the gate-passed draft is used and named to the reviewer

#### Scenario: The article workflows carry no model node

- **WHEN** either article workflow is exported
- **THEN** it contains no language-model node and no model credential
- **AND** the only model calls leave it as HTTP requests to the writer adapter

#### Scenario: The prompts exist once

- **WHEN** the gate, aspect or improvement prompt is rendered
- **THEN** it is read from the adapter image
- **AND** no copy exists under `agents/n8n/`

## MODIFIED Requirements

### Requirement: The aspect registry is the single list of aspects

The aspects that review a draft SHALL be declared in one committed registry in the writer
adapter's image — each with an identifier and its prompt file beside it — and the adapter SHALL
derive its reviewer turns from that registry at run time. The workflow graph SHALL NOT carry an
aspect identifier of its own, so adding, removing or rewording an aspect is a registry and
prompt-file change in the image, not a workflow change. The registry SHALL be validated before
the adapter serves a turn, because a turn that runs with no aspects would improve on nothing
while looking healthy.

#### Scenario: An aspect is added without a graph edit

- **WHEN** the registry gains an aspect entry and its prompt file
- **THEN** the next image reviews the draft against that aspect too
- **AND** no workflow export changed

#### Scenario: The registry is load-bearing

- **WHEN** the registry is missing, unparsable or empty
- **THEN** the adapter refuses to start
- **AND** it does not answer aspect turns with an empty findings list
