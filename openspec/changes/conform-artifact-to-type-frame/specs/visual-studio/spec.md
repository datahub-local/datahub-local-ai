# Spec Delta

## ADDED Requirements

### Requirement: An asset reports the container it was produced at

An asset SHALL carry what the authoring runtime reported about its container: the frame it
was served at, the frame the composition was authoritatively authored at where the two
differ, and whether the render was shorter than the length requested. The container fields a
caller already reads — the declared frame, frame count and duration — describe the declared
container, which the served artifact satisfies by construction; they MUST NOT be presented as
a measurement of the artifact. An asset whose runtime reported no container information SHALL
carry empty fields rather than the declared values in their place, so "no report" and "the
declared container" are distinguishable.

#### Scenario: A conformed asset carries both frames

- **WHEN** a render is conformed to the declared frame from another
- **THEN** the asset names the served frame
- **AND** it names the authored frame the composition was made at

#### Scenario: A short render is visible on the asset

- **WHEN** the served artifact is shorter than the declared length
- **THEN** the asset says so
- **AND** the declared duration is not silently replaced by the artifact's

#### Scenario: No report is not a declared container

- **WHEN** the runtime reported no container information for an asset
- **THEN** the asset's conformance fields are empty
- **AND** the declared values are not restated as if they had been measured
