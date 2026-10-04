# Spec Delta

## ADDED Requirements

### Requirement: A composition can be authored from a brief

The system SHALL support producing a video by authoring a composition from a
free-form brief, where the composition is generated for that brief rather than
selected from a fixed set of layouts or templates. The authored composition SHALL
be the artifact of record: it is what is committed, reviewed and re-rendered.

This path SHALL be distinct from the typed-spec render service. A typed spec
selects an arrangement the system defines; an authored composition is written for
one brief. Neither SHALL be presented as the other, and adding this path SHALL NOT
change what a typed-spec request accepts.

#### Scenario: A brief with no matching template
- **WHEN** a brief describes something no existing layout or template expresses
- **THEN** a composition is authored for that brief
- **AND** the result is not a fallback to the nearest template

#### Scenario: The composition is the artifact
- **WHEN** an authored composition is produced
- **THEN** the composition source is retained alongside the video
- **AND** the video can be reproduced from that source without re-authoring

### Requirement: An authored composition is validated before it is rendered

The system SHALL validate an authored composition with the rendering engine's own
checks before rendering it, and SHALL correct findings rather than render a
composition that fails them. A composition that cannot be made to pass SHALL be
reported as a failure, not rendered with the defect.

#### Scenario: A validation finding is corrected
- **WHEN** validation reports a defect in an authored composition
- **THEN** the composition is corrected
- **AND** the successful render is attempted only after validation passes

#### Scenario: A composition that cannot pass
- **WHEN** an authored composition still fails validation after correction
- **THEN** the attempt is reported as a failure
- **AND** no video is produced from it

### Requirement: An authored composition renders offline

An authored composition SHALL render with no outbound network. Every script and
font it needs SHALL be present locally; a composition referring to a remote
resource SHALL fail rather than silently render without it.

#### Scenario: No network at render time
- **WHEN** an authored composition is rendered with outbound network disabled
- **THEN** the render completes
- **AND** the composition's motion and typography are intact

#### Scenario: A remote resource
- **WHEN** an authored composition references a remote script or font
- **THEN** the render fails naming the reference
- **AND** it does not silently produce a video missing that resource

### Requirement: Authoring runs in the agent fleet only when its capability is proven

Where authoring is delegated to a cluster agent runtime, that runtime SHALL be
verified to support the work before a persona is declared to use it: writing a
composition file, running the engine's validation and render commands, and reaching
the render toolchain. The runtime SHALL be pinned by digest.

An unverified runtime SHALL be recorded as a gate, not assumed to work.

#### Scenario: A runtime's capability is unproven
- **WHEN** a runtime is a candidate for authoring but its capability surface is unverified
- **THEN** a probe run is performed and its outcome recorded
- **AND** no persona is declared to depend on the runtime until the probe passes

#### Scenario: A probe can author and render
- **WHEN** the probe run is given a brief
- **THEN** the run writes a composition, validates it, renders it, and reports the result
- **AND** the runtime's digest and the probe outcome are recorded

### Requirement: Authored output is attributable to the brief that produced it

Each authored composition SHALL record the brief it was authored from, so a later
reviewer can judge whether the composition answers the brief and a re-run can be
compared against it.

#### Scenario: Review of an authored composition
- **WHEN** a committed authored composition is reviewed
- **THEN** the brief that produced it is available with it
- **AND** the rendered video and its declared duration and dimensions are recorded
