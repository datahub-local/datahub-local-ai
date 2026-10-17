# Spec Delta

## ADDED Requirements

### Requirement: An authored asset is inspected before it is offered for review

Every authored visual SHALL be looked at by a critic before the run reports it: a still of the
artifact SHALL be made in the medium's own terms, and a vision model other than the authoring
model SHALL judge it against the artifact's declared contract (frame, form, brand) and the brief's
intent. The critic SHALL answer with a verdict and, when it finds a defect, findings that name
where the defect is and what change fixes it. A critic that cannot be reached, or whose answer
cannot be read, MUST NOT fail the run: the artifact ships and the review's absence is recorded.

#### Scenario: A defect is found and named
- **WHEN** the artifact shows a defect the critic can see in the still
- **THEN** the verdict names it as a finding with a location and a proposed change

#### Scenario: Nothing to fix
- **WHEN** the still shows no defect the critic can name
- **THEN** the verdict is a pass and no further turn is taken

#### Scenario: The critic is unavailable
- **WHEN** the review call fails or answers something unreadable
- **THEN** the artifact is reported as produced, and the review is recorded as not run or as
  unread rather than as a pass

### Requirement: A finding is corrected in the thread that owns the composition

When the critic reports a finding, the system SHALL take a further authoring turn in the same
session as the one that produced the artifact, carrying the findings as the reviewer's correction
and asking for the change in place, and SHALL re-inspect the result. The number of such turns
SHALL be bounded by a setting, and reaching the bound MUST end the loop with the last findings
recorded rather than continuing or discarding them.

#### Scenario: A finding spends a cycle
- **WHEN** the critic reports a finding and the budget allows another turn
- **THEN** a further turn is taken in the same session with the findings as its correction
- **AND** the re-rendered artifact is inspected again

#### Scenario: The budget is reached
- **WHEN** findings remain after the last permitted turn
- **THEN** the artifact is reported with those findings recorded on it
- **AND** no further turn is taken

#### Scenario: A raster is corrected by its prompt
- **WHEN** the artifact is a raster authored by the image model
- **THEN** the finding is applied by rewriting the image prompt and regenerating, bounded the same way

### Requirement: The review's outcome is part of the asset's record

The asset SHALL carry how many review turns were taken, what the critic reported in the last one,
and whether those findings were corrected, so that a reviewer is never shown a silent artifact and
a defect that survived the loop is visible where the artifact is approved.

#### Scenario: The approval names the review
- **WHEN** an asset is offered for human review
- **THEN** its record carries the cycles taken and the surviving findings, if any

#### Scenario: A correction is visible
- **WHEN** the critic's finding was corrected in a further turn
- **THEN** the record shows the finding and that a turn addressed it
