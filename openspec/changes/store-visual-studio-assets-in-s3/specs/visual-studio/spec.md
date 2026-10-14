# Spec Delta

## MODIFIED Requirements

### Requirement: Every run is recorded for later retrieval

The system SHALL record one row per run in a `visual_studio_table` DataTable, keyed by an
auto-generated `RUN_ID` (the execution id), carrying the request parameters — including
the session identifier when one was supplied — and every asset's outcome: its status, its
storyboard, any error, and the **object key** its bytes were written to. The row SHALL NOT
carry the asset's bytes: they SHALL be written to object storage
(`datahub-local-temp`) under a key derived from the run id and the asset type, and the
key SHALL be recorded in the row. The run's response SHALL carry the same outcome *with*
the asset, so an in-run consumer needs no second fetch. A recorded row and the objects it
names SHALL be retained for a bounded window of two days and then pruned together, so
neither the table nor the bucket can grow without limit; within that window a caller can
reconstruct every asset the run produced from the key the row carries.

#### Scenario: Run recorded

- **WHEN** a run finishes
- **THEN** exactly one row is recorded with the run id, the request and every asset's outcome
- **AND** the row names the object each asset was written to
- **AND** the response carries the same asset set, including its content

#### Scenario: The asset is not in the row

- **WHEN** a row is read back
- **THEN** it carries no base64 data URL for any asset
- **AND** the bytes are present in object storage under the key the row names

#### Scenario: Result fetched later

- **WHEN** a caller reads the run row by `RUN_ID` within the retention window
- **THEN** it can locate every asset the run produced by the key the row carries
- **AND** the object is still present in the bucket

#### Scenario: A failed upload fails the run

- **WHEN** an asset cannot be written to object storage
- **THEN** the run fails rather than recording a key for an object that was never written

#### Scenario: An empty run records no key

- **WHEN** every asset of a run failed
- **THEN** the row is still recorded, with each asset's error
- **AND** it carries no object key

#### Scenario: A thread is joinable

- **WHEN** a run carried a `SESSION_ID`
- **THEN** its recorded request carries that identifier
- **AND** every run in one session can be read together by that identifier

#### Scenario: An expired run is pruned

- **WHEN** a recorded row is older than the retention window
- **THEN** it is deleted from the table
- **AND** the objects it named are deleted from the bucket on the same window
- **AND** a row and an object inside the window are left alone

#### Scenario: The failure path is not silent

- **WHEN** the error workflow cannot record a failed run
- **THEN** that failure is reported rather than swallowed by the error path itself
