# Spec Delta

## MODIFIED Requirements

### Requirement: The composer carries the framework's full authoring capability

The authoring image SHALL take the rendering framework's authoring contract from the installed
engine itself — the documentation the pinned release serves — rather than from a tree fetched out
of an upstream repository. Its release SHALL be pinned once, and it SHALL NOT rely on the package
manager's default distribution of skills. The image SHALL include the framework's transition
primitives locally, because the render runs with no network. Every documentation topic the
composer's guide names SHALL be asserted during the image build, and a mismatch between the
guide's named topics and that set SHALL fail before the image is published. The authoring session
SHALL additionally offer the cluster catalog's read tools — GitHub (`search_code`,
`search_repositories`, `get_file_contents`, `list_branches`, `list_commits`, `list_tags`) and
Firecrawl (`firecrawl_search`, `firecrawl_scrape`, `firecrawl_map`) — declared directly to the
model, with every other tool on those servers hidden. The engine's documentation SHALL remain the
contract; a worked example found through the catalog is a pattern to check against it.

#### Scenario: The contract is the installed version's

- **WHEN** the composer needs the framework's composition contract or its timeline rules
- **THEN** it reads them from the engine binary at the pinned release
- **AND** the guidance cannot describe a version other than the one that renders

#### Scenario: A worked example is needed

- **WHEN** the brief names a look or effect the engine's docs describe but do not demonstrate
- **THEN** the composer may find a worked composition through the catalog's read tools
- **AND** it checks the result against `hyperframes docs` and `hyperframes lint` before using it

#### Scenario: A catalog write tool is named

- **WHEN** a turn tries to reach a catalog write tool such as `create_or_update_file`
- **THEN** the tool is not declared to the model, because only the read tools carry `direct` exposure

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

#### Scenario: The catalog does not answer

- **WHEN** a catalog server fails to connect
- **THEN** the turn continues on the engine's documentation and the authoring method
- **AND** a turn that cannot author fails by name rather than reporting success

### Requirement: An authored composition renders offline

An authored composition SHALL render with no outbound network. Every script and font it needs SHALL
be present locally; a composition referring to a remote resource SHALL fail rather than silently
render without it. A file read through the catalog while authoring SHALL NOT be referenced by its
remote address in the composition.

#### Scenario: No network at render time

- **WHEN** an authored composition is rendered with outbound network disabled
- **THEN** the render completes
- **AND** the composition's motion and typography are intact

#### Scenario: A remote resource

- **WHEN** an authored composition references a remote script or font
- **THEN** the render fails naming the reference
- **AND** it does not silently produce a video missing that resource

#### Scenario: A catalog read is composed in

- **WHEN** the composer uses a pattern found through the catalog
- **THEN** the file or asset is written locally beside the composition
- **AND** no URL from the catalog read appears in the authored file
