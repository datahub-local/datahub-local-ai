# Spec Delta

## REMOVED Requirements

### Requirement: Every run is recorded for later retrieval

**Reason**: The row had no reader. A run's outcome is returned to the caller in the
response, which `set_result` builds from `merge_branches` and not from any row, and the
asset's bytes now live in object storage — so the three nodes that wrote a row were the
whole of its use. It also cost the studio a run: `visual_studio_table` reached **202.5 MB
against its 200 MB cap with only 12 rows**, four of them 32-34 MB, and every run failed at
`record_run` *after* authoring and rendering correctly.

**Migration**: A caller reads the outcome from the response, which now carries what the
row used to: the object key each asset was written to (`ASSETS[].S3_KEY`, `S3_BYTES`) and
the resolved `SESSION_ID`. The object is at
`visual-studio/<RUN_ID>-<ASSET_TYPE>.<ext>` in `datahub-local-temp`, pruned on a two-day
window. A thread is continued by sending the `SESSION_ID` the response reports.

## MODIFIED Requirements

### Requirement: Model output is data, not commands

The system's own writes SHALL be limited to object storage and the `TemporalFiles`
DataTable; it MUST NOT write to any repository. A brief delivered to a model SHALL be
treated as data: no model-authored string may be executed as a command. The composition a
composer authors is the intended artifact, not a command to run.

#### Scenario: Model output is data

- **WHEN** a brief or an image prompt is handled
- **THEN** it is never executed as a command

#### Scenario: No run row is written

- **WHEN** any of the studio's workflows runs
- **THEN** it writes no DataTable row for the run itself
- **AND** the rendered asset is written to object storage instead

## ADDED Requirements

### Requirement: A rendered asset is stored outside the response

The system SHALL write each rendered asset to object storage and SHALL carry the object
key in the run's response, so the caller can fetch the bytes and no row is needed to name
them. A failed write SHALL fail the run rather than report a key for an object that does
not exist. The stored objects SHALL be pruned on a bounded window, so the bucket cannot
grow without limit.

#### Scenario: The asset is stored and named

- **WHEN** a run produces an asset
- **THEN** its bytes are written to `datahub-local-temp` under a key derived from the run id and the asset type
- **AND** the response carries that key and the byte count

#### Scenario: A failed write fails the run

- **WHEN** the asset cannot be written
- **THEN** the run fails, and no key is reported

#### Scenario: A run with nothing to store

- **WHEN** every asset of a run failed
- **THEN** the run still responds, with each asset's error
- **AND** it reports no key

#### Scenario: Stored objects expire

- **WHEN** a stored object is older than the retention window
- **THEN** it is deleted from the bucket
- **AND** an object inside the window is left alone
