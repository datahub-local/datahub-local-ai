# Spec Delta

## ADDED Requirements

### Requirement: A draft is reviewed before it is returned

The article draft SHALL be reviewed by a second pass before it leaves `Article Creator`, against
the same committed rules the writer was given, and a draft the review rejects SHALL be regenerated
rather than returned. The review SHALL judge the draft against the writing rules the drafting pass
followed, the length budget, and the requested asset markers. A rejection SHALL carry a reason into
the next attempt, and the number of attempts SHALL be bounded, so a draft that cannot satisfy the
review reports a reason instead of being returned or retried forever.

The length budget SHALL be checked in code rather than trusted to the review: a count a model is
asked for is a count it may invent. A draft outside the budget SHALL be rejected whatever the review
says, and the reason SHALL name the real count and the budget.

#### Scenario: A draft that breaks a rule is regenerated

- **WHEN** the review rejects a draft
- **THEN** the drafting prompt is rendered again carrying the reviewer's reason
- **AND** the returned draft is not the rejected one

#### Scenario: An over-budget draft is retried, not returned

- **WHEN** the draft's body exceeds the entry's word budget
- **THEN** the draft is rejected with the count and the budget in the reason
- **AND** the run continues to another attempt instead of ending

#### Scenario: The review reads the rules the writer followed

- **WHEN** the reviewer's prompt is composed
- **THEN** it carries the committed writing-rules file the drafting pass was given
- **AND** no second copy of those rules exists for the reviewer

#### Scenario: The attempt bound is reached

- **WHEN** every attempt within the bound is rejected
- **THEN** the sub-workflow answers with a failure naming the bound and the reviewer's last reason
- **AND** the entry point reports it once, with its own context

#### Scenario: An accepted draft carries no stale reason

- **WHEN** a draft is accepted after an earlier attempt was rejected
- **THEN** the answer's error field is empty
- **AND** the earlier reason is not returned with the accepted draft

#### Scenario: Markers name the requested types

- **WHEN** a draft is written for a requested asset set
- **THEN** each requested type's marker uses that type's own id
- **AND** a requested type with no marker is a review failure
