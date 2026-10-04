# Spec Delta

## Purpose

A small HTTP service that turns a typed content spec into an MP4 motion graphic,
authored deterministically from versioned templates and rendered offline with a pinned
browser and encoder.

## ADDED Requirements

### Requirement: A typed spec is rendered to video

The service SHALL accept a content spec as JSON over HTTP and return a rendered MP4 with
its metadata: content type, byte length, duration, frame count, frame rate and dimensions.
The caller MUST NOT need to supply HTML, CSS or any executable markup.

#### Scenario: Spec in, video out
- **WHEN** a valid content spec is posted
- **THEN** the response carries an MP4 and its duration, frame count and dimensions

#### Scenario: Metadata matches the spec
- **WHEN** a spec declares a duration and animation kind
- **THEN** the returned duration and frame count match that spec

### Requirement: A rendered asset can be handed off by reference

The service SHALL be able to persist a rendered asset and return a bounded reference — an
id and a URL — instead of the bytes, and SHALL serve the asset at that URL until a declared
retention window elapses. The reference SHALL be content-addressed, so the same spec and
service version yield the same id.

#### Scenario: Store then fetch
- **WHEN** a render is requested by reference
- **THEN** the response carries an id and a URL, and fetching that URL returns the MP4

#### Scenario: Unknown reference
- **WHEN** an id that was never rendered, or one past its retention, is fetched
- **THEN** the service answers not-found rather than an empty or partial file

#### Scenario: Same spec, same id
- **WHEN** the same spec is rendered by reference twice
- **THEN** both responses carry the same id

### Requirement: Compositions are authored by the service

The service SHALL generate the browser composition deterministically from the spec and
versioned templates. It MUST reject a request that carries markup or executable content,
and it MUST NOT execute any caller-supplied code. Same spec and same service version
SHALL produce the same composition.

#### Scenario: Caller markup is refused
- **WHEN** a request carries HTML or script rather than a spec
- **THEN** the request fails naming the parameter
- **AND** no render is attempted

#### Scenario: Deterministic composition
- **WHEN** the same spec is rendered twice on the same service version
- **THEN** the two compositions are identical

### Requirement: Rendering is offline and pinned

The service SHALL render without network access, with its browser, its animation runtime
and its fonts bundled in the image, and SHALL pin the render version so an upgrade is a
deliberate image change rather than a silent drift.

#### Scenario: No network at render
- **WHEN** the service renders with its outbound network unreachable
- **THEN** the render still succeeds

### Requirement: The service bounds work and reports failure honestly

The service SHALL reject a spec that exceeds a declared duration or resolution cap, SHALL
bound a render with a timeout, and MUST return a structured error naming the cause rather
than a partial or empty file. It SHALL expose a health endpoint for its probes.

#### Scenario: Over the cap
- **WHEN** a spec exceeds the declared duration or resolution cap
- **THEN** the request is rejected naming the cap

#### Scenario: Render failure
- **WHEN** the render fails
- **THEN** the response is an error naming the cause
- **AND** no partial video is returned

#### Scenario: Health
- **WHEN** the health endpoint is called
- **THEN** it answers without performing a render
