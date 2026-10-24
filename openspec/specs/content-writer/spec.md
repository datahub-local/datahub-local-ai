# content-writer Specification

## Purpose

The article lane: `Article Content Writer` takes a queued row — topic, description, source link and
source text — and turns it into a published blog post, calling `Article Creator` to draft the body
and then owning the slug, the visual assets and the commit. This spec covers what the drafting half
must guarantee about the draft it hands back.

The capability is still being built: `add-content-writer-agent` is the change that adds the lane
itself, and its archive extends this spec. What is here now is the review requirement the drafting
half must satisfy.

## Requirements

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

### Requirement: The published commit carries the requested asset set

The commit SHALL carry the assets the entry asked for and no others. An asset row whose type is not
in the entry's requested set — a leftover from an earlier request, or a row written by hand — SHALL
NOT be committed, and the run SHALL report the types it left out rather than dropping them
silently. The requested set SHALL be derived once and read by every consumer, so the set the draft
is written for, the set the publish gate checks and the set the commit carries cannot disagree.

#### Scenario: A leftover asset row is not committed

- **WHEN** the entry holds an approved asset row for a type it no longer requests
- **THEN** that row is not among the committed files
- **AND** the run names the type it left out

#### Scenario: The requested set has one definition

- **WHEN** any node needs the entry's requested asset types
- **THEN** it reads the set the selector derived
- **AND** no second derivation of the hero rule exists to drift from it

#### Scenario: A requested asset is still committed

- **WHEN** every requested type has an approved row
- **THEN** each of them is committed at its own marker, with the article, in one commit

### Requirement: A rejected draft is carried into the retry

A rejected draft SHALL be passed back to the drafting pass that regenerates it, so the retry edits
the draft the review just rejected rather than writing a new one from nothing. The retry SHALL carry
the most recent attempt's draft and not an earlier one, SHALL render an empty block on the first
attempt, and SHALL NOT require a second lookup for material the run already holds.

#### Scenario: The retry edits the rejected draft

- **WHEN** the review rejects a draft and the drafting prompt is rendered again
- **THEN** the prompt carries the draft that was just rejected
- **AND** the drafting rules ask for that draft to be edited rather than replaced

#### Scenario: A third attempt edits the second draft

- **WHEN** a run reaches a second retry
- **THEN** the prompt carries the most recent rejected draft
- **AND** it does not carry the first attempt's draft

#### Scenario: The first attempt carries no draft

- **WHEN** the drafting prompt is rendered for the first attempt
- **THEN** the previous-draft block is empty
- **AND** the drafting rules are not told to edit a draft that does not exist

#### Scenario: A retry does not search again

- **WHEN** a drafting turn is a retry
- **THEN** it writes from the source material the run already holds
- **AND** it does not repeat a lookup the run has already made

### Requirement: The requested asset set names each type once

The entry's requested asset set SHALL name each type exactly once, whatever the row's `ASSET_TYPES`
holds. A type listed twice SHALL NOT cause two studio calls, two asset rows, or two committed files
at one path, and every consumer of the set SHALL read the de-duplicated set rather than its own copy.

#### Scenario: A duplicated type is requested once

- **WHEN** the row's `ASSET_TYPES` names the same type twice
- **THEN** the requested set carries that type once
- **AND** the pending set, the publish gate and the commit path all see one entry for it

#### Scenario: A duplicated hero is one hero

- **WHEN** the row names the hero raster twice
- **THEN** the requested set carries the hero once
- **AND** the hero rule does not prepend a second one

### Requirement: A human retry is handed the draft the human rejected

When a person asks for changes to a draft they read, the pass that regenerates it SHALL receive
the draft they were reading, so the change is an edit rather than a fresh article. In this lane
that pass is the improvement pass: the retry SHALL NOT re-enter the drafting sub-workflow, and the
draft of record SHALL be resolved in this order — the converged draft of this run, then the
drafting call's own answer, then the stored draft row — so a review resumed in a later execution
still improves the draft the person read. The draft SHALL be the one that was on screen when the
feedback was written and not an earlier round's, the first pass SHALL send none, and a drafting
pass re-rendered inside one invocation SHALL prefer the draft its own gate just rejected.

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
