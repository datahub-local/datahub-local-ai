# Spec Delta

## MODIFIED Requirements

### Requirement: A draft is reviewed before it is returned

The draft SHALL pass the drafting gate's counted checks before it leaves `Article Creator`: the
answer carries an H1 and a body, the word budget with its margin, the requested asset markers, and
no transport or session failure. A draft the gate rejects SHALL be regenerated with the gate's own
reason carried into the next attempt, and the number of attempts SHALL be bounded. The source
ledger SHALL NOT be part of that verdict: it is data the reviewer reads.

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

#### Scenario: A block no page carries is not a rejection

- **WHEN** the ledger records a fenced block with no page behind it
- **THEN** the gate still accepts the draft if the counted checks pass
- **AND** the block is named to the reviewer instead

## REMOVED Requirements

### Requirement: The draft is audited by a turn that can read the artifacts

**Reason**: It gave the audit a verdict the lane branched on. On 2026-11-09 the audit rejected two
consecutive drafts the code gate had passed, and the second rejection cost a third seven-minute
draft.

**Migration**: "The reviewer advises and never blocks" states the audit's new place in the loop; the
task itself is unchanged.

## ADDED Requirements

### Requirement: The reviewer advises and never blocks

After a draft passes the gate, the lane SHALL run one `audit` turn with the ledger, the session
transcript and the pages, and SHALL present its findings to the human next to the draft. The
findings SHALL NOT reject the draft, SHALL NOT trigger a retry, and a review that fails or cannot
answer SHALL add a note rather than fail the round.

#### Scenario: Findings reach the human

- **WHEN** the reviewer returns findings
- **THEN** the Slack review message carries them with the draft
- **AND** the draft is presented whatever they say

#### Scenario: The reviewer cannot answer

- **WHEN** the audit turn fails or the request dies
- **THEN** the draft is presented with a note naming the failure
- **AND** no attempt is spent

#### Scenario: Two drafts, one reviewer call each

- **WHEN** the gate rejects an attempt and the retry passes
- **THEN** the reviewer runs on the accepted draft only
