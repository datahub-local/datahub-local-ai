# Spec Delta

## MODIFIED Requirements

### Requirement: An authored asset is inspected before it is offered for review

Every authored visual SHALL be looked at by a critic before the run reports it: a still of the
artifact SHALL be made in the medium's own terms, and a vision model other than the authoring
model SHALL judge it against the artifact's declared contract (frame, form, brand) and the brief's
intent. The critic SHALL answer with a verdict and, when it finds a defect, findings that each
carry an identifier, a severity, a location and a proposed change. Before the critic is called,
the render SHALL pass the deterministic checks the runtime provides, and a check that could not
run MUST be recorded as not run rather than as clean. A critic that cannot be reached, or whose
answer cannot be read, MUST NOT fail the run, but it MUST NOT be recorded as a pass either: the
artifact is reported as produced with the review marked unread, and it SHALL NOT be auto-approved
as reviewed.

#### Scenario: A defect is found and named
- **WHEN** the artifact shows a defect the critic can see in the still
- **THEN** the verdict names it as a finding with an id, a severity, a location and a proposed change

#### Scenario: Deterministic findings come first
- **WHEN** the runtime reports a layout, motion or contrast error
- **THEN** that error reaches the asset as a finding before the critic is asked
- **AND** the critic is not the only evidence that the render is clean

#### Scenario: Nothing to fix
- **WHEN** the still shows no defect the critic can name and the deterministic checks pass
- **THEN** the verdict is a pass and no further turn is taken

#### Scenario: The critic is unavailable
- **WHEN** the review call fails or answers something unreadable
- **THEN** the artifact is reported as produced, and the review is recorded as unread
- **AND** the asset is not presented as reviewed or auto-approved

### Requirement: A finding is corrected in the thread that owns the composition

When the critic reports a finding, the system SHALL take a further authoring turn in the same
session as the one that produced the artifact, carrying the findings as the reviewer's correction
and asking for the change in place, and SHALL re-inspect the result. Findings SHALL carry a stable
identifier across turns, and the critic SHALL say which previously open findings are resolved and
which are still present rather than returning a fresh verdict with no history. A finding that
survives two correction turns SHALL be marked stalled and MUST NOT spend a further turn by
itself, because repeating a correction that does not reach the render is how the loop exhausts
its budget without improving the artifact. The number of turns SHALL be bounded by a setting, and
reaching the bound MUST end the loop with every open finding recorded rather than continuing or
discarding them.

#### Scenario: A finding spends a cycle
- **WHEN** the critic reports a new finding and the budget allows another turn
- **THEN** a further turn is taken in the same session with the findings ordered by severity
- **AND** the re-rendered artifact is inspected again

#### Scenario: A finding is resolved by id
- **WHEN** a correction removes a defect that was open under an id
- **THEN** the next review lists that id as resolved
- **AND** the asset no longer carries it as open

#### Scenario: A finding stalls
- **WHEN** the same finding is still present after a correction turn
- **THEN** it is marked stalled
- **AND** the loop does not take another turn on its account
- **AND** the asset is offered to a human with that finding named

#### Scenario: The budget is reached
- **WHEN** findings remain after the last permitted turn
- **THEN** the artifact is reported with those findings recorded on it
- **AND** no further turn is taken

#### Scenario: A raster is corrected by its prompt
- **WHEN** the artifact is a raster authored by the image model
- **THEN** the finding is applied by rewriting the image prompt and regenerating, bounded the same way

### Requirement: The review's outcome is part of the asset's record

The asset SHALL carry how many review turns were taken, the verdict of the last review, every
finding still open with its id, severity and proposed change, and which findings stalled, so that a
reviewer is never shown a silent artifact and a defect that survived the loop is visible where the
artifact is approved. An asset with an open finding, an unread review, or a deterministic check
that could not run SHALL be marked as needing review, and that mark MUST reach the surface where a
human approves it.

#### Scenario: The approval names the review
- **WHEN** an asset is offered for human review
- **THEN** its record carries the cycles taken and the open findings, if any
- **AND** the approval surface names them

#### Scenario: A correction is visible
- **WHEN** the critic's finding was corrected in a further turn
- **THEN** the record shows the finding, that a turn addressed it, and that the next review resolved it

#### Scenario: A clean asset is marked clean
- **WHEN** the review resolved every finding and the deterministic checks passed
- **THEN** the asset is marked as reviewed and carries no open findings

### Requirement: The review's evidence is a still of the render it judges

A still offered to a review SHALL have been produced from the artifact that turn rendered, and a
still from an earlier turn SHALL NOT stand in for one. The clip's own cut structure SHALL determine
where its stills are taken, so every detected scene contributes a still; a fixed set of time
offsets SHALL be the fallback only when no cut is detected. The number of scenes detected and the
number seen by the review SHALL be recorded on the asset, so coverage is a measurement rather than
an assumption. The capture of a settled frame SHALL use a seek the clip's own rate supports — at
least one frame interval — and the system SHALL treat a capture as produced only when the file
exists and carries content, since a capture can succeed by exit status while writing nothing. A
still that was not produced SHALL be absent from what the review is offered, so the review judges
one frame fewer rather than the wrong turn's frame; a missing still MUST NOT fail the artifact.

#### Scenario: Every scene is seen
- **WHEN** a clip is reviewed and its cuts are detected
- **THEN** each detected scene contributes a still
- **AND** the asset records how many scenes were detected and seen

#### Scenario: No cuts is one scene
- **WHEN** cut detection finds no boundary in a clip
- **THEN** the review falls back to time offsets
- **AND** the asset does not claim more coverage than it has

#### Scenario: The settled frame is the settled frame

- **WHEN** a clip is sampled for review and its rate is low enough that a fixed sub-frame seek
  reaches no frame
- **THEN** the settled-frame capture still writes the last frame

#### Scenario: A capture that wrote nothing is not offered

- **WHEN** a still's capture exits without writing a file
- **THEN** that still is not among the stills offered to the review
- **AND** a file from an earlier turn at that name is not served in its place

#### Scenario: A missing still does not fail the asset

- **WHEN** no settled-frame still can be produced
- **THEN** the review runs on the stills that were produced
- **AND** the artifact is reported as rendered

## ADDED Requirements

### Requirement: A connector is declared and drawn between its endpoints

A composition that draws a relationship between two elements SHALL declare that relationship as
data — the source, the target and whether it carries a head — and SHALL draw it with the runtime
helper that resolves both endpoints from the laid-out boxes, rather than placing the line and head
by hand. The helper SHALL place a head on the target's edge, and SHALL report that every
declaration resolved or name the declarations that did not. A diagram brief with no declaration,
or with a declaration the helper could not resolve, SHALL be a finding rather than a silent
render.

#### Scenario: A connector is drawn from its endpoints
- **WHEN** a composition declares a connector between two elements
- **THEN** the line and head are placed from the elements' measured boxes
- **AND** the head sits on the target's edge

#### Scenario: A declaration does not resolve
- **WHEN** a declared source or target does not exist, or the helper did not run
- **THEN** the asset carries the unresolved declarations as a finding
- **AND** the render is not reported as clean

#### Scenario: A diagram declares no connector
- **WHEN** a visual authored from a diagram brief carries no connector declaration
- **THEN** the asset reports that the connector gate did not run
- **AND** the review does not treat it as clean
