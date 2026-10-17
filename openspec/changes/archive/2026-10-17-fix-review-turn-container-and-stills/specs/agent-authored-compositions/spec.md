# Spec Delta

## ADDED Requirements

### Requirement: A still is made for the clip that was served

The stills a runtime offers beside an artifact SHALL be frames of the served artifact, taken at a
seek its container supports, and a still SHALL be reported only when it was written this turn.
The settled frame SHALL be sampled at the end of the clip by a seek of at least one frame interval
at the artifact's own rate, so a low-rate clip — the rate is derived from the declared frame count
over the declared length, and can be a single-digit number of frames per second — does not silently
lose that specimen. A capture that produced no bytes SHALL NOT be reported as a still, so a caller
that fetches the reported names cannot receive an earlier render's file under one.

#### Scenario: A low-rate clip keeps its settled frame

- **WHEN** a clip is served at a rate whose frame interval is longer than a fixed sub-frame seek
- **THEN** the settled-frame still is written

#### Scenario: Only the stills that exist are reported

- **WHEN** a still cannot be produced
- **THEN** its name is not among the reported stills
- **AND** no file from a previous run or turn is offered in its place
