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
