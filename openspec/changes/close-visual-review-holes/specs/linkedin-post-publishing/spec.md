# Spec Delta

## ADDED Requirements

### Requirement: An animated asset with open findings is approved knowingly

When an animated asset is offered for human approval, the approval SHALL carry the review's
verdict and every finding still open, with each finding's severity and the change it asks for. An
asset whose review could not be read, or whose deterministic checks could not run, SHALL be
presented as unreviewed rather than as clean. The approval notice MUST NOT describe such an asset
as a completed animation without naming what the review found, because the person approving it is
the last gate before publication.

#### Scenario: The approval names the open findings
- **WHEN** an animated asset with open findings is sent for approval
- **THEN** the approval notice lists each open finding with its severity
- **AND** it says that approving publishes the asset anyway

#### Scenario: A clean asset is named clean
- **WHEN** the review resolved every finding and the deterministic checks passed
- **THEN** the approval notice carries no finding list
- **AND** the asset is not marked as unreviewed

#### Scenario: An unread review is not a pass
- **WHEN** the review answer could not be read
- **THEN** the approval notice says the asset was not reviewed
- **AND** the asset is not presented as clean
