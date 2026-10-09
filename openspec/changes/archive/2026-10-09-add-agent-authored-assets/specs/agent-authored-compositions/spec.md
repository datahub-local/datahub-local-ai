# Spec Delta

## ADDED Requirements

### Requirement: A workflow can request an authored composition and receive its artifact

The authoring runtime SHALL accept a request that carries a brief and an output
kind, author and render the composition, and return the rendered artifact to the
caller over HTTP. Each request's artifact MUST be isolated from other requests, so
a caller always receives the artifact authored for its own brief, and the request
MUST identify its output unambiguously without exposing the runtime's filesystem.

#### Scenario: A workflow receives the artifact
- **WHEN** a workflow requests an authored composition with a brief and an output kind
- **THEN** the composition is authored and rendered
- **AND** the rendered artifact is returned to the caller over HTTP

#### Scenario: Requests do not collide
- **WHEN** two authoring requests are made in sequence
- **THEN** each caller receives the artifact authored for its own brief

### Requirement: The deployed authoring runtime is reachable and sized to render

A deployed authoring session SHALL admit the calling workload on its contract port.
Its workspace SHALL be at least the engine's render disk gate, which the runtime's
default claim does not satisfy, and the session MUST remain available between a
workflow's request and its completion.

#### Scenario: The calling workflow reaches the session
- **WHEN** a calling workflow sends an authoring request to the deployed session
- **THEN** the session admits it and returns an artifact

#### Scenario: The workspace can render
- **WHEN** the session renders an artifact
- **THEN** its workspace is at least the engine's disk gate
- **AND** the session is not reclaimed between the request and its completion
