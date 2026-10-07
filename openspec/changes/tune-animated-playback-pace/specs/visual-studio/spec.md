# Spec Delta

## ADDED Requirements

### Requirement: An animated type may declare its playback pace

An animated type SHALL be able to declare a `durationMs` that fixes its playback pace
regardless of the duration the authoring model puts in the content spec; a type that
declares none SHALL keep following the spec's `motion.durationMs`. The declared value
and the spec value SHALL both be bounded by a shared ceiling, and the frame count SHALL
remain the type's declared count so a longer duration adds time between frames rather
than frames.

#### Scenario: A declared pace overrides the spec
- **WHEN** an animated type declares `durationMs` and a spec requests a shorter `motion.durationMs`
- **THEN** the produced asset's total duration is the type's declared value
- **AND** its frame count is unchanged

#### Scenario: An undeclared pace follows the spec
- **WHEN** an animated type declares no `durationMs`
- **THEN** the produced asset's total duration is the spec's `motion.durationMs`

#### Scenario: The ceiling bounds both
- **WHEN** a declared pace or a spec duration exceeds the animated ceiling
- **THEN** the produced asset is clamped to the ceiling
- **AND** the run does not fail
