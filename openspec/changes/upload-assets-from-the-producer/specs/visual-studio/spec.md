# Spec Delta

## MODIFIED Requirements

### Requirement: Asset content is returned; identity is the caller's

The system SHALL return each asset with its media type, its format, its own status and a
handle to its bytes: either the bytes themselves, or the object key an external process
stored them under. An **agent-authored** asset SHALL be named rather than carried — its
bytes are written to object storage by a process that is not the workflow, because n8n
persists a workflow's binaries as well as its JSON, and the asset carries the key, the byte
count and the media type. A **raster** asset SHALL carry its bytes as the data URL the image
model returned, because those bytes are produced inside n8n and no external process can
fetch them; nothing stores one on its behalf. It MUST NOT return a repository path or a
filename; deriving those and placing the asset remains the caller's job.

#### Scenario: An agent asset is named, not carried

- **WHEN** the studio returns an agent-authored asset
- **THEN** it carries the object key, the byte count and the media type
- **AND** it carries no base64 and no data URL

#### Scenario: A raster asset carries its own bytes

- **WHEN** the studio returns a raster asset
- **THEN** it carries the image as the data URL the model returned
- **AND** it names no object, because nothing stored one

#### Scenario: Studio invents no path

- **WHEN** the studio returns an asset
- **THEN** it returns the handle and the media type only
- **AND** it invents no repository path and no filename

#### Scenario: An asset that was not stored

- **WHEN** an agent asset's bytes could not be stored
- **THEN** it reports its error and names no object
- **AND** the run still reports its other assets

### Requirement: A rendered asset is stored outside the response

The system SHALL write each **agent-authored** asset to object storage and SHALL carry the
object key in the run's response, so the caller can fetch the bytes and no row is needed to
name them. The writer SHALL NOT be the workflow that reports the asset: n8n persists a
workflow's binaries as well as its JSON, so a workflow that fetches an asset and uploads it
stores the asset as surely as one that carries it. It SHALL be a process holding a credential
scoped to one bucket and one prefix, and a key outside the `visual-studio/` prefix SHALL be
refused, as SHALL a key nested below it — the deployment prunes by listing that prefix with a
`/` delimiter, so a nested object is never seen by the prune. A failed write SHALL report that
asset's error rather than a key for an object that does not exist. A **raster** asset is
stored by nothing, and this requirement does not apply to it. The stored objects SHALL be
pruned on a bounded window, so the bucket cannot grow without limit.

#### Scenario: The asset is stored and named

- **WHEN** a run produces an agent-authored asset
- **THEN** its bytes are written to `datahub-local-temp` under a key derived from the run id and the asset type
- **AND** the response carries that key and the byte count
- **AND** the writer is a service that fetched them, not the workflow that reports them

#### Scenario: A failed write fails the run

- **WHEN** the asset cannot be written
- **THEN** that asset carries the failure as its error, and no key is reported for it
- **AND** the run reports itself FAILED when that was its only asset, and PARTIAL otherwise

#### Scenario: A run with nothing to store

- **WHEN** every agent asset of a run failed
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

#### Scenario: A deck's two files

- **WHEN** a deck run produces the deck and its paired video
- **THEN** both are stored and both are named
- **AND** each names its own object, the deck's carrying the deck's extension and the video's
  the video's
