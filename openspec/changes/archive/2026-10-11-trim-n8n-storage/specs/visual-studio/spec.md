# Spec Delta

## MODIFIED Requirements

### Requirement: Every run is recorded for later retrieval

The system SHALL record one row per run in a `visual_studio_table` DataTable, keyed by an auto-generated `RUN_ID` (the execution id), carrying the request parameters — including the session identifier when one was supplied — and the full result: every asset with its status, content and any error, so a caller can fetch a run's outcome over HTTP after the fact. The run's response SHALL carry the same outcome. A recorded row SHALL be retained for a bounded window of two days and then pruned, so the table cannot grow without limit; within that window the row SHALL remain self-sufficient, so a caller can still reconstruct every asset the run produced.

#### Scenario: Run recorded

- **WHEN** a run finishes
- **THEN** exactly one row is recorded with the run id, the request and every asset's outcome
- **AND** the response carries the same asset set

#### Scenario: Result fetched later

- **WHEN** a caller reads the run row by `RUN_ID` within the retention window
- **THEN** it can reconstruct every asset the run produced, including its content

#### Scenario: A thread is joinable

- **WHEN** a run carried a `SESSION_ID`
- **THEN** its recorded request carries that identifier
- **AND** every run in one session can be read together by that identifier

#### Scenario: An expired run is pruned

- **WHEN** a recorded row is older than the retention window
- **THEN** it is deleted from the table
- **AND** a row inside the window is left alone
