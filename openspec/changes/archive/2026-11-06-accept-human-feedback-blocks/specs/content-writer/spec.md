# Spec Delta

## MODIFIED Requirements

### Requirement: A human retry is handed the draft the human rejected

When a person asks for changes to a draft they read, the pass that regenerates it SHALL receive
the draft they were reading, so the change is an edit rather than a fresh article. In this lane
that pass is the improvement pass: the retry SHALL NOT re-enter the drafting sub-workflow, and the
draft of record SHALL be resolved in this order — the converged draft of this run, then the
drafting call's own answer, then the stored draft row — so a review resumed in a later execution
still improves the draft the person read. The draft SHALL be the one that was on screen when the
feedback was written and not an earlier round's, the first pass SHALL send none, and a drafting
pass re-rendered inside one invocation SHALL prefer the draft its own gate just rejected.

A round that carries human feedback SHALL change the draft: a returned body and title equal to the
ones it was given SHALL be reported as unchanged and SHALL NOT be reported as an improvement. A
feedback round MAY add a fenced block no fetched page carries, because the person asking for it is
the authority the ledger otherwise stands in for; such a block SHALL be counted and named to the
reviewer as unverified. A block the ledger does carry and that failed verification — not found,
failed validation, drifted excerpt — SHALL still fail on a feedback round, and a round without
human feedback SHALL keep the strict rule.

#### Scenario: A human asks for one change

- **WHEN** a person answers the review with feedback and the graph re-enters the improvement pass
- **THEN** the improvement prompt carries the draft they were reading and the feedback
- **AND** the parts of it the feedback does not name are kept

#### Scenario: A review resumed in a later execution still edits the reviewed draft

- **WHEN** the approval is answered after the run that presented the draft has ended
- **THEN** the draft of record is read from the stored draft row
- **AND** the improvement edits that draft rather than drafting from nothing

#### Scenario: A third round edits the second draft

- **WHEN** a draft is sent for review a second time and rejected again
- **THEN** the improvement pass carries the most recently reviewed draft
- **AND** it does not carry the first round's draft

#### Scenario: The first authoring sends nothing

- **WHEN** a draft is produced for the first time in a run
- **THEN** no previous draft or human feedback is applied
- **AND** the prompt's previous-draft block is empty

#### Scenario: The internal review loop is unaffected

- **WHEN** the drafting pass is re-rendered by the internal review gate inside one invocation
- **THEN** it edits the draft that gate just rejected
- **AND** the improvement pass's draft of record does not displace it

#### Scenario: A feedback round adds a command no fetched page carries

- **WHEN** a person asks for a command the project's documentation does not contain
- **THEN** the improvement pass writes it as a fenced block
- **AND** the block is counted and the review message names it as unverified

#### Scenario: A first-draft edit may not add such a block

- **WHEN** a round without human feedback fences a block no ledger entry carries
- **THEN** the edit fails the code re-check naming the block
- **AND** the pre-improvement draft is presented for review

#### Scenario: Feedback does not excuse a ledgered block the page lost

- **WHEN** a feedback round keeps a block whose ledger entry is `found: false`
- **THEN** the edit fails the code re-check naming the page

#### Scenario: A feedback round that changes nothing says so

- **WHEN** a feedback round returns the body and title it was given
- **THEN** the outcome is reported as unchanged, not improved
- **AND** the reviewer is told the feedback was not applied

### Requirement: A draft is improved before it reaches a human review

A gate-passed draft SHALL be improved before it is presented for human review. One reviewer
per aspect — structure, clarity and flow at minimum — SHALL review the draft and return
advisory findings, and an improvement pass SHALL edit the draft applying those findings and any
human feedback. The aspect reviewers SHALL NOT reject a draft, gate a round, or spend a retry
bound: their findings are input to the improvement pass, and the only gates SHALL remain the
drafting gate's objective checks, the code re-check, and the human approval.

The improvement SHALL be verified in code before it is delivered: the improved draft's body
SHALL be within the entry's word budget and SHALL carry every requested asset marker exactly
once. An improved draft that fails either SHALL be retried with the objective problem stated,
at most once, and the run SHALL then fall back to the gate-passed pre-improvement draft with the
reason recorded. A count SHALL be taken in code, never asked of a model.

A failure inside the improvement pass SHALL degrade rather than block: an aspect reviewer that
cannot answer records no findings for its aspect and the rest run; an improvement pass that
fails records the reason and falls back to the gate-passed draft. The improvement outcome —
improved, unchanged, fallback, failed, or nothing to apply — SHALL be visible to the human
reviewer with the draft, and an unchanged outcome SHALL say the feedback was not applied. An
aspect registry that is missing, unparsable or empty SHALL fail the run loudly rather than
improve nothing quietly.

#### Scenario: Findings are applied and the draft is improved

- **WHEN** the aspect reviewers return findings
- **THEN** the improvement pass edits the draft applying them
- **AND** the draft presented for review is the improved one, with the outcome named

#### Scenario: Nothing to apply leaves the draft unchanged

- **WHEN** every aspect returns no findings and there is no human feedback
- **THEN** no improvement pass runs
- **AND** the draft presented for review is the drafting pass's own, with the outcome named

#### Scenario: An improved draft outside the objective checks is not delivered

- **WHEN** the improved draft exceeds the word budget or drifts a requested asset marker
- **THEN** the failure is counted in code and the improvement is retried once with the problem
- **AND** the draft presented for review is the gate-passed one, with the fallback recorded

#### Scenario: A failed improvement pass does not lose the draft

- **WHEN** the improvement pass fails after its retries
- **THEN** the gate-passed draft is presented for review
- **AND** the reason is recorded and named to the reviewer

#### Scenario: A failed aspect reviewer does not fail the others

- **WHEN** one aspect's review cannot answer
- **THEN** that aspect records no findings
- **AND** the remaining aspects' findings still reach the improvement pass

#### Scenario: A human retry edits the draft the human read

- **WHEN** a person answers the review with feedback
- **THEN** the improvement pass re-enters with that feedback and the draft the person was reading
- **AND** the parts of it the feedback does not name are kept

#### Scenario: An unchanged round is not delivered as an improvement

- **WHEN** the improvement pass returns the draft it was given
- **THEN** the draft of record is the one that was presented before
- **AND** the outcome is named unchanged rather than improved
