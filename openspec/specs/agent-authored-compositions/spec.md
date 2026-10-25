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

The **brief** SHALL be the deliverable of the workflow: it carries the source content,
the requested form and style, the output frame, the shared motion rules and any
correction or extra direction the caller supplies. The composer's own guide SHALL state
only facts about its sandbox (the working directory, where the engine and its skills
are, no network at render, how to run the render), and MUST NOT restate the composition
contract or a method the framework already defines.

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

#### Scenario: The method is not restated in our guide
- **WHEN** the composer's guide and the framework's shipped skills are both read
- **THEN** the guide states sandbox facts only
- **AND** the composition contract and the motion method are stated once, by the
  framework

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

### Requirement: The engine's checks gate the render and a caller may supply the review

The authoring turn SHALL gate the render with the rendering engine's own checks
(`lint` and `check`), correct every reported finding, and render only after the checks
pass. The system MUST NOT maintain a separate, hand-authored review checklist in the
composer's guide: the engine's checks are the automated gate, and any craft review is
carried by the brief's motion rules or by a caller-supplied correction.

#### Scenario: Engine findings are corrected
- **WHEN** the engine's checks report a finding against an authored composition
- **THEN** the composition is corrected
- **AND** the render runs only after the checks pass

#### Scenario: A composition that cannot pass
- **WHEN** an authored composition still fails the engine's checks after correction
- **THEN** the attempt is reported as a failure
- **AND** no video is produced from it

#### Scenario: No bespoke checklist in our guide
- **WHEN** the composer's guide is read
- **THEN** it carries no layout, proportion, legibility or pacing checklist
- **AND** no page-indicator or frame-fill rule

#### Scenario: A caller-supplied review reaches the composer
- **WHEN** a request carries feedback or an extra prompt
- **THEN** the brief carries it verbatim
- **AND** the composer acts on it in the same turn it authors

### Requirement: The composer carries the framework's full authoring capability

The authoring image SHALL carry the rendering framework's complete authoring skill set
at one pinned release — the animation rules and scene blueprints, keyframes, the
registry, creative direction, the studio and the core contract — and SHALL NOT rely on
the package manager's default distribution, which carries only a subset. The image
SHALL include the framework's transition primitives locally, because the render runs
with no network. The presence of every expected skill SHALL be asserted during the
image build.

#### Scenario: A motion rule is available
- **WHEN** the composer needs the framework's motion knowledge
- **THEN** the corresponding skill is present in the image
- **AND** it was fetched at the same pinned release as the engine

#### Scenario: A missing skill fails the build
- **WHEN** the expected skill set is not present after the build step
- **THEN** the build fails naming the missing skill
- **AND** an image carrying a subset is not published

#### Scenario: Effects need no network at author time
- **WHEN** a brief names a scene transition
- **THEN** the primitives are present locally
- **AND** the render completes with outbound network disabled

### Requirement: A re-author carries the reason it failed

When an authored asset is rejected by a reviewer, the system SHALL carry the rejection
text into the next authoring turn for that asset, so a correction is made against the
reason rather than from the brief that already failed.

#### Scenario: Rejection reaches the next turn
- **WHEN** an authored asset is rejected and re-requested
- **THEN** the brief for the new turn contains the rejection text
- **AND** the composer's next attempt is authored against it

#### Scenario: No rejection leaves the brief unchanged
- **WHEN** an asset is authored for the first time
- **THEN** the brief carries no feedback section

### Requirement: The artifact's container is the requested one

A request that declares an output container — the frame, the frame rate and the length —
SHALL receive an artifact in that container. The authoring runtime SHALL conform the engine's
render to the declared container after the render and before the artifact is served, for
every output kind, and MUST NOT serve the engine's output unconformed, because its frame is
the composition's own markup rather than the request's.

Conformance SHALL set the frame by scaling, and where the authored aspect differs from the
declared one SHALL cover the declared frame and crop the overflow rather than letterbox it.
It SHALL set the rate so the declared frame count is exact over the declared length, and SHALL
trim a longer render to the declared length. It MUST NOT extend or hold a render to reach a
declared length, because a frozen tail is the cheap-motion tell the composition rules forbid.
When the engine's container already matches the declared one, the runtime SHALL serve the
engine's output unchanged, so a conforming render is not encoded twice.

The runtime SHALL report what it received beside what it delivered — the authored frame and
length — and SHALL report a render shorter than the declared length as short. The stills the
runtime offers a caller's review SHALL be taken from the conformed artifact, so the review
judges what the caller receives. A conformance that could not be performed SHALL be reported
and MUST NOT fail the artifact.

#### Scenario: A render at the wrong frame is conformed

- **WHEN** a request declares a frame and the composition renders at another
- **THEN** the served artifact's frame is the declared one
- **AND** the authored frame is reported beside it

#### Scenario: An aspect mismatch is covered, not letterboxed

- **WHEN** the authored aspect differs from the declared aspect
- **THEN** the artifact fills the declared frame, the overflow cropped
- **AND** no bars are added

#### Scenario: The declared length trims a long render

- **WHEN** the render is longer than the declared length
- **THEN** the served artifact ends at the declared length

#### Scenario: A short render is reported, not frozen

- **WHEN** the render is shorter than the declared length
- **THEN** the artifact is delivered as it is
- **AND** it is reported as short
- **AND** no frame is held to reach the declared length

#### Scenario: A conforming render is not re-encoded

- **WHEN** the engine's output already has the declared frame, rate and length
- **THEN** it is served without a second encode

#### Scenario: The stills are the caller's artifact

- **WHEN** the runtime offers stills of the render to a review
- **THEN** every still is a frame of the conformed artifact
- **AND** its frame matches the declared one

### Requirement: A still is made for the clip that was served

The stills a runtime offers beside an artifact SHALL be frames of the served artifact, taken at a
seek its container supports, and a still SHALL be reported only when it was written this turn.
The settled frame SHALL be sampled at the end of the clip by a seek of at least one frame interval
at the artifact's own rate, so a low-rate clip — the rate is derived from the declared frame count
over the declared length, and can be a single-digit number of frames per second — does not silently
lose that specimen. A capture that produced no bytes SHALL NOT be reported as a still, so a caller
that fetches the reported names cannot receive an earlier render's file under one.

#### Scenario: A low-rate clip keeps its settled frame

- **WHEN** a clip is served at a rate whose frame interval is longer than a fixed sub-frame seek
- **THEN** the settled-frame still is written

#### Scenario: Only the stills that exist are reported

- **WHEN** a still cannot be produced
- **THEN** its name is not among the reported stills
- **AND** no file from a previous run or turn is offered in its place

### Requirement: An authoring turn survives a transient model-endpoint stall

The composer's runtime SHALL carry explicit settings for the model calls it makes, and MUST NOT
rely on the vendor's defaults for either: a retry window that outlasts a silence of several
minutes at the model endpoint, and a request idle timeout that exceeds the model gateway's own
streaming timeout, so the gateway's verdict ends an attempt before the runtime's does. The
model gateway SHALL apply a timeout to a streaming call that is separate from, and larger than,
its non-streaming request timeout: for a streaming call that timeout bounds the gap between
chunks, and the gateway cannot substitute another deployment once a stream has emitted to the
client. An authoring turn that exhausts its retry window SHALL end as a failure that names the
model endpoint and the reason.

#### Scenario: A stall inside the window is recovered

- **WHEN** the model endpoint stops sending chunks for longer than the gateway's streaming
  timeout and resumes within the runtime's retry window
- **THEN** a further attempt is made
- **AND** the turn completes without human action

#### Scenario: An exhausted window fails loudly

- **WHEN** every attempt in the retry window fails
- **THEN** the turn fails naming the model endpoint and the reason
- **AND** the failure is reported rather than left for the caller to discover as a missing
  artifact

#### Scenario: The runtime outlasts the gateway

- **WHEN** the runtime's request idle timeout is compared with the gateway's streaming timeout
- **THEN** the runtime's is larger
- **AND** the gateway's verdict is what ends each attempt

#### Scenario: A stalled stream has no substitution

- **WHEN** a streaming call has already delivered content to the client and then stops
- **THEN** the gateway reports the provider's failure rather than substituting another
  deployment
- **AND** the runtime's retry is what recovers the turn
