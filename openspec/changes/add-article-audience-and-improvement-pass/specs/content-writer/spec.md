# Spec Delta

## ADDED Requirements

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
improved, fallback, failed, or nothing to apply — SHALL be visible to the human reviewer with
the draft. An aspect registry that is missing, unparsable or empty SHALL fail the run loudly
rather than improve nothing quietly.

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

### Requirement: An article is written for the row's audience

An entry SHALL carry an audience level — `NONE`, `LOW`, `MEDIUM` or `ADVANCED` — and the
drafting pass, the internal review gate, the aspect reviewers and the improvement pass SHALL
all be told that level and one committed definitions file describing what each level's reader
already knows. The gate SHALL scale its term-explanation expectation with the level, so it
never demands explanations the level's reader does not need.

A level that is blank or missing SHALL read as `NONE`, the general reader new to the subject,
so an existing row needs no backfill and behaves exactly as before this change. A level that
is not one of the four SHALL refuse the row before it drafts, naming the value, rather than
being read as a default. The definitions SHALL exist in one committed file and SHALL NOT be
restated in any prompt, gate check or workflow code, and the level ids SHALL agree between that
file, the entry point's validation and the board intake's configured default.

#### Scenario: The level reaches every pass

- **WHEN** a row carries an audience level
- **THEN** the drafting prompt, the gate's prompt, the aspect prompts and the improvement prompt all carry it
- **AND** all four read the same committed definitions

#### Scenario: The gate scales with the level

- **WHEN** a draft for an `ADVANCED` row explains the field's basics anyway
- **THEN** the gate does not reject for lacking term explanations
- **AND** a draft for a `NONE` row that uses a subject term unexplained is still rejected

#### Scenario: A blank level is today's reader

- **WHEN** a row carries no audience level
- **THEN** the drafting pass is told `NONE`
- **AND** the article is written for a reader new to the subject, as before this change

#### Scenario: An invalid level is refused, not defaulted

- **WHEN** a row's audience cell is not one of the four levels
- **THEN** the row is refused before drafting, with the value named in the reason

### Requirement: The aspect registry is the single list of aspects

The aspects that review a draft SHALL be declared in one committed registry — each with an
identifier and its prompt file — and the improvement chain SHALL derive its work from that
registry at run time. The workflow graph SHALL NOT carry an aspect identifier of its own, so
adding, removing or rewording an aspect is a registry and prompt-file change, not a graph
change. A prompt file the registry names SHALL exist in the repository before the graph is
applied, because a fetch of a missing file fails the run.

#### Scenario: An aspect is added without a graph edit

- **WHEN** the registry gains an aspect entry and its prompt file
- **THEN** the next run reviews the draft against that aspect too
- **AND** no workflow export changed

#### Scenario: The registry is load-bearing

- **WHEN** the registry is missing, unparsable or empty
- **THEN** the run fails loudly before any improvement
- **AND** it does not silently present an unimproved draft as improved
