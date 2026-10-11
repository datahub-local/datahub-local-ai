# Spec Delta

## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: An authored composition is reviewed before it is rendered

**Reason**: The nine-point review was our own harness, compensating for the engine's
checks with a checklist over values the composer could report but not verify, and its
pacing rules mandated the frozen motion this change removes. The guarantee is
re-issued as "The engine's checks gate the render and a caller may supply the review",
where the automated gate is the engine and any craft review is carried by the brief.

**Migration**: None for the engine's checks, which already ran. The guide's review
section, its pacing thresholds and the page-indicator rule are deleted; a caller that
wants a specific review passes it on the trigger as feedback or an extra prompt.

## ADDED Requirements

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
