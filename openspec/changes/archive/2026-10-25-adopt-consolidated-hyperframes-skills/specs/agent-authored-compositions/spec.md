# Spec Delta

## MODIFIED Requirements

### Requirement: The composer carries the framework's full authoring capability

The authoring image SHALL take the rendering framework's authoring contract from the installed
engine itself — the documentation the pinned release serves — rather than from a tree fetched out
of an upstream repository. Its release SHALL be pinned once, and it SHALL NOT rely on the package
manager's default distribution of skills. The image SHALL include the framework's transition
primitives locally, because the render runs with no network. Every documentation topic the
composer's guide names SHALL be asserted during the image build, and a mismatch between the
guide's named topics and that set SHALL fail before the image is published.

#### Scenario: The contract is the installed version's

- **WHEN** the composer needs the framework's composition contract or its timeline rules
- **THEN** it reads them from the engine binary at the pinned release
- **AND** the guidance cannot describe a version other than the one that renders

#### Scenario: A motion rule is available

- **WHEN** the composer needs the framework's motion knowledge
- **THEN** the brief carries the committed grammar from `visual_motion_rules.md`
- **AND** the image is not required to carry a motion skill for it

#### Scenario: A missing skill fails the build

- **WHEN** the documentation the guide names is not served by the pinned engine
- **THEN** the build fails naming the topic
- **AND** no image is published whose guide points at documentation the engine does not have

#### Scenario: A missing topic fails the build

- **WHEN** a documentation topic the guide names is not served by the pinned engine
- **THEN** the build fails naming the topic
- **AND** an image whose guide points at missing documentation is not published

#### Scenario: The guide and the build cannot drift

- **WHEN** the composer's guide names a documentation topic
- **THEN** that topic is in the set the image build asserts
- **AND** a topic outside it fails the offline test suite rather than the composer's first turn

#### Scenario: An upstream restructure cannot break the build

- **WHEN** the upstream project moves, renames or retires files in its repository
- **THEN** the image build is unaffected
- **AND** only an engine release this repository accepts can change what the composer reads

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
