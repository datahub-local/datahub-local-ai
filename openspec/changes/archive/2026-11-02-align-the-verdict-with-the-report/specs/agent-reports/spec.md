# Spec Delta

## ADDED Requirements

### Requirement: A finding section states its empty form

Every section a reporting persona's format marks as a finding SHALL state the wording it
takes when nothing there needs action, and that wording SHALL open with `Nothing`, `None` or
`No <thing>`, which is what the delivery hook matches to decide the report's verdict. The
reading that shows why may follow after a colon. A normal reading MUST NOT be written in a
finding section as its own bullet, and a finding section MUST NOT carry commentary —
`worth watching`, `not a finding`, `recurring`, a cluster description, or a note that a tool
timed out.

#### Scenario: A clean run

- **WHEN** a run finds nothing to act on
- **THEN** each finding section holds one bullet opening with its stated empty form
- **AND** the report posts with the clean verdict

#### Scenario: A finding section with no stated empty form

- **WHEN** a reporter prompt's format names a finding section and states no empty form
- **THEN** the test over the committed prompts fails, naming the prompt and the section

#### Scenario: Commentary inside a finding section

- **WHEN** a finding section carries a bullet that is neither a finding nor its empty form
- **THEN** the report posts with the warning verdict, whatever its `Status` line says

### Requirement: A section label is classified by what the section is for

A section that reports a reading which is never a finding on its own SHALL be classified as
clean, and a section that exists only to carry findings SHALL be classified as a finding. A
persona's prompt and the hook's label sets MUST agree: a section its prompt calls "never a
finding" MUST NOT warn on a populated reading.

#### Scenario: An idle service count

- **WHEN** a report states how many routed services took no request
- **THEN** it does not warn, because one idle reading is not a finding

#### Scenario: A restart loop

- **WHEN** a container's restarts are above the threshold its prompt states
- **THEN** the report warns
