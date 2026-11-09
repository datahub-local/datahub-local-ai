# Spec Delta

## MODIFIED Requirements

### Requirement: A draft is reviewed before it is returned

The draft SHALL pass the drafting gate's objective checks before it leaves `Article Creator`: the
word budget, the requested asset markers, the session's answer and the source ledger, each counted
in code. A draft the gate rejects SHALL be regenerated with the gate's own reason carried into the
next attempt, and the number of attempts SHALL be bounded, so a draft that cannot satisfy the gate
reports a reason instead of being returned or retried forever. No model review SHALL run between
the gate and the return; the `review` and `audit` tasks remain available on demand, and the human
review is the judgement step.

The length budget SHALL be checked in code rather than trusted to a model: a count a model is asked
for is a count it may invent. A draft outside the budget SHALL be rejected whatever the answer says,
and the reason SHALL name the real count and the budget.

#### Scenario: A draft that breaks a rule is regenerated

- **WHEN** the gate rejects a draft
- **THEN** the drafting prompt is rendered again carrying the gate's reason
- **AND** the returned draft is not the rejected one

#### Scenario: An over-budget draft is retried, not returned

- **WHEN** the draft's body exceeds the entry's word budget
- **THEN** the draft is rejected with the count and the budget in the reason
- **AND** the run continues to another attempt instead of ending

#### Scenario: The review reads the rules the writer followed

- **WHEN** an on-demand review or audit prompt is composed
- **THEN** it carries the committed writing-rules file the drafting pass was given
- **AND** no second copy of those rules exists for it

#### Scenario: Markers name the requested types

- **WHEN** a draft is written for a requested asset set
- **THEN** each requested type's marker uses that type's own id
- **AND** a requested type with no marker is a gate failure

#### Scenario: The attempt bound is reached

- **WHEN** every attempt within the bound is rejected
- **THEN** the sub-workflow answers with a failure naming the bound and the gate's last reason
- **AND** the entry point reports it once, with its own context

#### Scenario: An accepted draft carries no stale reason

- **WHEN** a draft is accepted after an earlier attempt was rejected
- **THEN** the answer's error field is empty
- **AND** the earlier reason is not returned with the accepted draft
