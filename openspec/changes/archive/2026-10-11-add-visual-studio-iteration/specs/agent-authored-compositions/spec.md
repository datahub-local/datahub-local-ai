# Spec Delta

## MODIFIED Requirements

### Requirement: A workflow can request an authored composition and receive its artifact

The authoring runtime SHALL accept a request that carries a brief and an output kind, author and render the composition, and return the rendered artifact to the caller over HTTP. Each request's artifact MUST be isolated from other requests, so a caller always receives the artifact authored for its own brief, and the request MUST identify its output unambiguously without exposing the runtime's filesystem. A request MAY name a session; one that names one SHALL be served in that session's directory and address its artifact under that identifier, so a later request continues the same work instead of authoring a new composition.

#### Scenario: A workflow receives the artifact

- **WHEN** a workflow requests an authored composition with a brief and an output kind
- **THEN** the composition is authored and rendered
- **AND** the rendered artifact is returned to the caller over HTTP

#### Scenario: Requests do not collide

- **WHEN** two authoring requests are made in sequence without naming a session
- **THEN** each caller receives the artifact authored for its own brief

#### Scenario: A request continues a session

- **WHEN** a workflow names a session that already holds a composition
- **THEN** the artifact is addressed under that session identifier
- **AND** the composition authored earlier in that session is available to the turn
