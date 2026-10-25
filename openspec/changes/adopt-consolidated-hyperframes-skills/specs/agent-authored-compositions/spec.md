# Spec Delta

## MODIFIED Requirements

### Requirement: The composer carries the framework's full authoring capability

The authoring image SHALL carry the rendering framework's complete authoring capability at one
pinned release, **as that release defines it** — when the release ships one entry skill with
reference files, the image SHALL carry the entry skill and the references the composer is directed
to, and SHALL NOT preserve a retired skill layout. The image SHALL NOT rely on the package
manager's default distribution, which carries only a subset. The image SHALL include the
framework's transition primitives locally, because the render runs with no network. The presence
of every skill and reference the composer's guide names SHALL be asserted during the image build,
and a mismatch between the guide's named paths and the asserted set SHALL fail before the image is
published.

#### Scenario: A motion rule is available

- **WHEN** the composer needs the framework's motion knowledge
- **THEN** the skill or reference that release provides for it is present in the image
- **AND** it was fetched at the same pinned release as the engine

#### Scenario: A missing skill fails the build

- **WHEN** the expected skill set is not present after the build step
- **THEN** the build fails naming the missing path
- **AND** an image carrying a subset is not published

#### Scenario: The guide and the image cannot drift

- **WHEN** the composer's guide names a skill or reference file
- **THEN** that path is inside the set the image build asserts
- **AND** a path outside it fails the offline test suite rather than the composer's first turn

#### Scenario: A release restructures its skill tree

- **WHEN** the pinned release no longer ships a path the image or the guide expects
- **THEN** the build fails naming it
- **AND** the guide is rewritten against the new layout rather than the retired one being restored

#### Scenario: Effects need no network at author time

- **WHEN** a brief names a scene transition
- **THEN** the primitives are present locally
- **AND** the render completes with outbound network disabled

## ADDED Requirements

### Requirement: An authoring turn always returns a rendered artifact

An authoring turn inside the agent fleet SHALL run unattended to a rendered artifact: the caller
has no preview to approve, so the framework's interactive instruction to stop at a preview and
wait SHALL NOT apply. The composer's guide SHALL state this sandbox fact, and the turn SHALL NOT
report success without the artifact its caller fetches.

#### Scenario: The framework's preview gate is overridden

- **WHEN** the framework's authoring guidance says to stop for approval before rendering
- **THEN** the composer renders in the same turn anyway
- **AND** the caller receives the artifact it requests

#### Scenario: No artifact means no success

- **WHEN** a turn ends without writing its declared output file
- **THEN** the turn is reported as failed with its own reason
- **AND** the failure is not reported as a missing artifact of an otherwise successful run
