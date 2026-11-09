# Spec Delta

## MODIFIED Requirements

### Requirement: The source ledger is derived from the turn's transcript

The session server SHALL write `sources.json` itself, from the pages the turn actually scraped. A
fenced block that appears on a scraped page SHALL be recorded as `quoted` with that page's URL. A
block that is not that copy SHALL be recorded as `derived` when it parses by its language and every
name it uses — field, flag, image, kind, object name — appears on a page the session read, with the
entry naming the page that carries the most of them. A block with a name on no page, or with a line
its language cannot parse, SHALL get no entry and SHALL be reported with that name. The model SHALL
NOT be asked to write the ledger, and no separate fetch SHALL be made to verify a page the pod
already brokered.

#### Scenario: A quoted block

- **WHEN** the article fences a block that appears in a page the turn scraped
- **THEN** the ledger carries one entry with that block, that page's URL and `mode: quoted`
- **AND** the entry is written by the server, not returned by the model

#### Scenario: A composed block from a page's own names

- **WHEN** the article fences a resource assembled from fields the scraped page documents
- **THEN** the ledger carries one entry with `mode: derived` and the page carrying those names
- **AND** the gate accepts it

#### Scenario: An invented block

- **WHEN** the article fences a block naming an object no scraped page carries
- **THEN** no entry is written for it
- **AND** the gate rejects the draft naming that object

#### Scenario: Text the model never received

- **WHEN** a block would match only the part of a page beyond the truncation the model saw
- **THEN** the block is not verified, because it was never read

### Requirement: The draft is audited by a turn that can read the artifacts

The adapter SHALL keep offering an `audit` task that runs in the run's directory with tools and the
source proxy, reads the article, the derived ledger and the session transcript, and answers a
verdict with findings. The lane SHALL NOT call it in the automatic path: one authoring turn is the
draft of record, and the audit, the aspect pass and the edit remain available on demand. The audit
SHALL NOT write the article, and SHALL NOT report the counts code already decides.

#### Scenario: A block no page carries

- **WHEN** the draft fences a block whose names no page carries
- **THEN** an on-demand audit's prompt carries that block and the pages read
- **AND** the finding names the page to quote, the missing name, or says to write it as prose

#### Scenario: A claim no page carries

- **WHEN** the draft names a schedule, field or version that appears in no scraped page
- **THEN** the audit reports it as a finding naming the section

#### Scenario: A requested section that never landed

- **WHEN** the entry's feedback asks for a section the draft does not carry
- **THEN** the audit reports the missing section as the finding that blocks the draft

#### Scenario: The audit disagrees with the code gate

- **WHEN** the audit passes a draft the parser rejects
- **THEN** the parser's problem still rejects it, because the count is code's

#### Scenario: The audit's evidence is reachable

- **WHEN** the audit is told to search the session transcript or fetch a page
- **THEN** the transcript path is set in its environment and the proxy admits the declared hosts

#### Scenario: The lane does not audit

- **WHEN** a draft passes the code gate
- **THEN** it is presented for human review without an audit, an aspect pass or an edit

## REMOVED Requirements

### Requirement: A draft is improved before it reaches a human review

**Reason**: The automatic aspect pass and edit were three extra model turns whose own failures —
timeout, over-budget fallback, a fallback that returned the unchanged draft — accounted for three
of the last six failed rounds. The requirement is replaced by "The lane authors a draft in one
turn": the drafting gate remains the only automatic gate, and the human review is unchanged.

**Migration**: None. The `audit`, `aspects` and `improve` tasks stay on the adapter for on-demand
use, and their code re-check (`check_improved_draft`) still accepts the ledger's derived mode.

## ADDED Requirements

### Requirement: The lane authors a draft in one turn

The lane SHALL call the drafting task once per attempt, SHALL gate the answer in code, and SHALL
present the accepted draft for human review without an aspect pass or an edit. A draft the gate
rejects SHALL be retried at most once, in a session of its own, carrying the previous draft and the
gate's reason; a second rejection SHALL reach the human with the reason rather than being rewritten
automatically.

#### Scenario: A gate-passed draft

- **WHEN** the drafting turn's answer passes the code gate
- **THEN** it is stored and presented for review
- **AND** no aspect, audit or edit call is made

#### Scenario: A rejected draft

- **WHEN** the code gate rejects the answer
- **THEN** one retry runs in a new session carrying the previous draft and the reason
- **AND** a second rejection reaches the human with the reason

#### Scenario: The retry is a new session

- **WHEN** a retry drafts again
- **THEN** it starts in a session of its own rather than continuing the previous transcript
- **AND** the previous draft and the reason are in its brief
