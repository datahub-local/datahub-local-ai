# Spec Delta

## MODIFIED Requirements

### Requirement: Asset content is returned; identity is the caller's

The system SHALL return each asset with its media type, its format and its own status,
and SHALL name where its bytes are stored rather than returning them. It MUST NOT return
the asset's bytes — not as a data URL, and not as binary carried through a workflow that
records its own executions — and it MUST NOT return a repository path or a URL. A caller
that needs the bytes reads them from the object the asset names.

#### Scenario: The asset carries a name, not bytes

- **WHEN** the studio returns an asset
- **THEN** it carries the object key, the byte count and the media type
- **AND** it carries no base64 and no data URL

#### Scenario: Studio invents no path

- **WHEN** the studio returns an asset
- **THEN** it returns the object key and the media type only
- **AND** it invents no repository path and no URL of its own

#### Scenario: An asset that was not stored

- **WHEN** an asset failed to render
- **THEN** it reports its error and names no object

### Requirement: A rendered asset is stored outside the response

The system SHALL write each rendered asset to object storage and SHALL carry the object
key in the run's response, so the caller can fetch the bytes and no row is needed to name
them. The writer SHALL NOT be the workflow that reports the asset, because n8n persists a
workflow's binaries as well as its JSON; it SHALL be a process holding a credential scoped
to one bucket and one prefix, and a key outside the `visual-studio/` prefix SHALL be
refused. A failed write SHALL report that asset's error rather than a key for an object
that does not exist. The stored objects SHALL be pruned on a bounded window, so the bucket
cannot grow without limit.

#### Scenario: The asset is stored and named

- **WHEN** a run produces an asset
- **THEN** its bytes are written to `datahub-local-temp` under a key derived from the run id and the asset type
- **AND** the response carries that key and the byte count
- **AND** the writer is a service that fetched them, not the workflow that reports them

#### Scenario: A failed write fails the run

- **WHEN** the asset cannot be written
- **THEN** that asset carries the failure as its error, and no key is reported for it
- **AND** the run reports itself FAILED when that was its only asset, and PARTIAL otherwise

#### Scenario: A run with nothing to store

- **WHEN** every asset of a run failed
- **THEN** the run still responds, with each asset's error
- **AND** it reports no key

#### Scenario: Stored objects expire

- **WHEN** a stored object is older than the retention window
- **THEN** it is deleted from the bucket
- **AND** an object inside the window is left alone

#### Scenario: A zero-byte render is not stored

- **WHEN** the source answers `200` with an empty body
- **THEN** nothing is written and that asset carries the failure
- **AND** no key is reported for an empty object

#### Scenario: A nested key is refused

- **WHEN** a destination with a further `/` below the prefix is requested
- **THEN** the write is refused, because the prune lists the prefix with a `/` delimiter
  and would never see such an object to delete it

## ADDED Requirements

### Requirement: A successful run is recorded, without its asset

The system SHALL record its successful executions, and an execution's data MUST NOT
contain an asset's bytes in any form. A workflow that carries an asset's bytes is
therefore either not the workflow that stores them, or not one whose successful runs are
recorded.

#### Scenario: A successful run leaves a record

- **WHEN** a studio run succeeds
- **THEN** its execution is recorded in n8n with its nodes and their outputs

#### Scenario: The record is not the asset

- **WHEN** that record is inspected
- **THEN** it carries the object key, the byte count and the composer's report
- **AND** it carries none of the asset's bytes

#### Scenario: The cost of a run is bounded

- **WHEN** a run is recorded
- **THEN** its execution data and the instance's binary store grow by an amount unrelated to the asset's size
