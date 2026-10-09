# agent-authored-compositions Specification

## Purpose

Produce a video for a brief that no fixed layout or template expresses: an agent
authors a HyperFrames composition for that brief, gates it with the engine's own
validation, and renders it offline. The composition is the committed artifact of
record. In the cluster the path runs through a purpose-built harness adapter
(`agents/adapters/pi-render/`) on a `HarnessSession`, because a Job's agent
container cannot be given enough memory to render.

## Requirements

### Requirement: A composition can be authored from a brief

The system SHALL support producing a video by authoring a composition from a free-form
brief, where the composition is generated for that brief rather than selected from a
fixed set of layouts or templates. The authored composition SHALL be the artifact of
record: it is what is committed, reviewed and re-rendered.

The authoring turn SHALL plan before it builds: it states a short storyboard (the form,
the style and the scenes) and then authors the composition to that plan. The storyboard
is recorded with the run so a visual can be diagnosed, but nothing downstream parses or
transforms it.

#### Scenario: A brief with no matching template
- **WHEN** a brief describes something no existing template expresses
- **THEN** a composition is authored for that brief
- **AND** the result is not a fallback to the nearest template

#### Scenario: The composition is the artifact
- **WHEN** an authored composition is produced
- **THEN** the composition source is retained alongside the video
- **AND** the video can be reproduced from that source without re-authoring

#### Scenario: The plan is stated first
- **WHEN** a composition is authored
- **THEN** a storyboard is stated before the composition is written
- **AND** the storyboard is recorded with the run

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

### Requirement: An authored composition follows the shared brand

Where a composition is authored from a brief rather than selected from a fixed
template, the brief SHALL carry the shared brand tokens and the authored
composition SHALL use them: the brand's flat UI language for its surface,
accents, typefaces and shapes. The authored path SHALL NOT be the one flow that
ignores the brand, and it SHALL NOT be asked to invent a palette.

#### Scenario: The brief carries the brand
- **WHEN** a composition is authored from a brief
- **THEN** the brief includes the shared brand tokens
- **AND** the authored composition uses them

#### Scenario: An authored diagram matches the deterministic one
- **WHEN** an authored composition and a deterministic asset are produced for the same brand
- **THEN** both use the same palette and typefaces
- **AND** neither is the only branded artefact

### Requirement: An authored composition is reviewed before it is rendered

Because the rendering engine's own checks do not detect a composition that fills only
part of its frame or that changes too fast for a viewer, and the authoring agent cannot
see images, the authoring turn SHALL review the composition against content,
proportion, legibility and pacing before rendering it, and SHALL correct every miss.
The review SHALL be reported with its measured values so it is checkable from the run
record.

#### Scenario: Frame proportion is checked
- **WHEN** an authored composition is reviewed before rendering
- **THEN** each scene's **visible content** is confirmed to fill the frame's height
  rather than a band within it, measured on the content and not on a wrapper that
  stretches to fill
- **AND** a scene whose content does not fill the frame is corrected before rendering

#### Scenario: A multi-scene composition is paginated
- **WHEN** an authored composition has more than one scene
- **THEN** every scene carries a page indicator in the same bottom-right position

#### Scenario: Legibility is checked
- **WHEN** an authored composition is reviewed before rendering
- **THEN** type is confirmed to meet the minimum sizes for the rendered width
- **AND** the composition passes the engine's layout and contrast checks

#### Scenario: Pacing and total length are checked
- **WHEN** an authored composition is reviewed before rendering
- **THEN** each scene, reveal and hold is within the pacing bounds the guide states
- **AND** the composition's total duration does not exceed the duration the brief asks
  for

#### Scenario: Content is checked
- **WHEN** an authored composition is reviewed before rendering
- **THEN** every string shown is traceable to the brief
- **AND** no fact, number or name is introduced that the brief does not contain

#### Scenario: The review is reported
- **WHEN** the authoring turn reports what it produced
- **THEN** the report states the review and its measured values

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
