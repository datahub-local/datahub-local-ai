# Spec Delta

## MODIFIED Requirements

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
