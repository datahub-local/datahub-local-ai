# Spec Delta

## ADDED Requirements

### Requirement: A correction turn keeps the container the request declared

The container a request declared — the frame, the frame count, the length and the rate derived
from them — SHALL reach every authoring turn the run takes, including those a review's findings
prompt. A correction turn SHALL be asked for the same container as the turn it corrects, and the
system MUST NOT re-derive it from whatever fields the review's own items happen to carry. An
authoring turn that has no declared container SHALL stop and name what is missing rather than
authoring at a default frame, length or rate, because a plausible default is indistinguishable
from the caller's request once the run has produced an artifact.

#### Scenario: A review's correction declares the type's container

- **WHEN** a critic reports a finding and a further turn is taken
- **THEN** that turn's brief declares the container the request declared
- **AND** the run does not substitute its own frame, length or rate

#### Scenario: Nothing declares a container

- **WHEN** an authoring turn's item carries no declared frame or length
- **THEN** the run stops and names the missing declaration
- **AND** no artifact is authored at a default

#### Scenario: The record shows the declaration it was authored from

- **WHEN** an asset is reported
- **THEN** it carries the container the run declared for it beside what the runtime delivered

### Requirement: The review's evidence is a still of the render it judges

A still offered to a review SHALL have been produced from the artifact that turn rendered, and a
still from an earlier turn SHALL NOT stand in for one. The capture of a settled frame SHALL use a
seek the clip's own rate supports — at least one frame interval — and the system SHALL treat a
capture as produced only when the file exists and carries content, since a capture can succeed by
exit status while writing nothing. A still that was not produced SHALL be absent from what the
review is offered, so the review judges one frame fewer rather than the wrong turn's frame; a
missing still MUST NOT fail the artifact.

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
