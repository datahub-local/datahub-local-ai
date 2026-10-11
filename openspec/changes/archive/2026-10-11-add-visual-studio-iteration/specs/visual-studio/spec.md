# Spec Delta

## MODIFIED Requirements

### Requirement: Every trigger speaks one contract

The workflow SHALL expose the same parameter contract on every trigger — a sub-workflow call, an HTTP API webhook and a form — taking `CONTENT` (the source text, required), `ASSET_TYPES`, `FEEDBACK`, `FORCE` and `STYLE`, and MAY also take `SCENES` and `SESSION_ID`. `FORCE` SHALL be one of `auto`, `diagram`, `story`, `data`, `poster` or `image`, and `STYLE` SHALL name a brand scheme. `SCENES` SHALL be an optional positive integer requesting a sequence, and when it is blank the composer's own storyboard SHALL decide the scene count. `SESSION_ID` SHALL be an optional session identifier: when it is present the run SHALL continue that session, and when it is blank the run SHALL use an identifier scoped to the run so the request is isolated. The workflow MUST NOT read caller state from a table or sheet to decide what to produce; everything it needs arrives on the trigger.

#### Scenario: Same contract on every surface

- **WHEN** the same parameters arrive via the API webhook, the form or a sub-workflow call
- **THEN** the same asset set is produced

#### Scenario: Missing content

- **WHEN** a request arrives without `CONTENT`
- **THEN** the request fails naming the missing parameter

#### Scenario: An unknown force fails loudly

- **WHEN** a request carries a `FORCE` outside the enum
- **THEN** the request fails naming the value
- **AND** no asset is produced

#### Scenario: A session is continued

- **WHEN** a request carries a `SESSION_ID`
- **THEN** the run addresses its artifact under that identifier and continues that session

#### Scenario: A run without a session id is isolated

- **WHEN** a request carries no `SESSION_ID`
- **THEN** the run uses an identifier scoped to that run
- **AND** it does not read or overwrite another run's session state

### Requirement: Every run is recorded for later retrieval

The system SHALL record one row per run in a `visual_studio_table` DataTable, keyed by an auto-generated `RUN_ID` (the execution id), carrying the request parameters — including the session identifier when one was supplied — and the full result: every asset with its status, content and any error, so a caller can fetch a run's outcome over HTTP after the fact. The run's response SHALL carry the same outcome.

#### Scenario: Run recorded

- **WHEN** a run finishes
- **THEN** exactly one row is recorded with the run id, the request and every asset's outcome
- **AND** the response carries the same asset set

#### Scenario: Result fetched later

- **WHEN** a caller reads the run row by `RUN_ID`
- **THEN** it can reconstruct every asset the run produced, including its content

#### Scenario: A thread is joinable

- **WHEN** a run carried a `SESSION_ID`
- **THEN** its recorded request carries that identifier
- **AND** every run in one session can be read together by that identifier
