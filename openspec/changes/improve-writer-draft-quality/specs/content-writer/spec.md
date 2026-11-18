# Spec Delta

## ADDED Requirements

### Requirement: An approved outline precedes the draft

The entry point SHALL request an outline from the writer adapter before the drafting turn:
two or three candidate indexes, each a shape, a one-line outcome and an ordered list of
section names with a one-line job per section. The chosen index SHALL be approved in a
blocking review before drafting, stored on the row, and passed to the drafting and
improvement turns as the plan the article writes to. The drafting gate SHALL NOT count
sections against the outline: its enforcement is the writer that reads it and the human
who approved it.

An outline turn that fails or cannot be parsed SHALL retry once and then fail the row with
a reason naming the outline, rather than drafting blind.

#### Scenario: The draft follows the approved index

- **WHEN** an outline option is approved for a row
- **THEN** the drafting turn receives it
- **AND** the draft's sections appear in its order, each doing the job it names

#### Scenario: The gate does not count sections

- **WHEN** a draft is reviewed against an approved outline
- **THEN** no gate check asserts a section count or a heading text against it

#### Scenario: The outline turn fails

- **WHEN** the outline turn errors or its answer cannot be parsed, twice
- **THEN** the row is failed with a reason naming the outline
- **AND** no drafting turn is spent

### Requirement: The retry form offers named directives

The article draft retry form SHALL offer a fixed set of directives (structure or order,
focus, tone, concision, depth) beside its free-text feedback, and the chosen directive
SHALL be carried into the feedback the improvement turn reads, verbatim and ahead of the
free text.

#### Scenario: A directive reaches the improver

- **WHEN** the reviewer picks a directive and adds no free text
- **THEN** the improvement turn's feedback block contains the directive's wording

## MODIFIED Requirements

### Requirement: The entry point passes only the drafting task

Every article writer turn SHALL run inside `Article Creator`. The entry point SHALL select
the turn with a `TASK` input whose default is `draft` and SHALL pass `outline` before the
automatic path and `draft` for it, SHALL NOT pass `aspects` or `improve`, and SHALL NOT
post to the writer adapter itself. The sub-workflow SHALL answer the adapter's result, so
the entry point reads one response shape.

A task the sub-workflow does not implement SHALL fail the run naming the task, and SHALL
NOT fall back to drafting.

#### Scenario: The automatic path drafts once

- **WHEN** the entry point calls the writer for an entry
- **THEN** it passes `TASK: outline` and, once the index is approved, `TASK: draft`
- **AND** it contains no HTTP node that posts to the writer adapter
- **AND** no aspect or edit call is made

#### Scenario: The other tasks stay available

- **WHEN** an operator asks `Article Creator` for `review`, `audit`, `aspects` or `improve`
- **THEN** the sub-workflow serves it
- **AND** the entry point does not pass it

#### Scenario: An unimplemented task does not draft

- **WHEN** a caller asks `Article Creator` for a task it does not implement
- **THEN** the run fails naming the task
- **AND** no draft is spent
