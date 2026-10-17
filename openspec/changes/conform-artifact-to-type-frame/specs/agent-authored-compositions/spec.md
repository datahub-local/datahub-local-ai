# Spec Delta

## ADDED Requirements

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
