# Spec Delta

## ADDED Requirements

### Requirement: An authored composition is reviewed before it is rendered

Because the rendering engine's own checks do not detect a composition that fills only
part of its frame or that changes too fast for a viewer, and the authoring agent cannot
see images, the authoring turn SHALL review the composition against content,
proportion, legibility and pacing before rendering it, and SHALL correct every miss.
The review SHALL be reported with its measured values so it is checkable from the run
record.

#### Scenario: Frame proportion is checked
- **WHEN** an authored composition is reviewed before rendering
- **THEN** each scene's content is confirmed to fill the frame's height rather than a
  band within it
- **AND** a scene whose content does not fill the frame is corrected before rendering

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
