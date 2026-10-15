# Spec Delta

## MODIFIED Requirements

### Requirement: Every trigger speaks one contract

The workflow SHALL expose the same parameter contract on every trigger — a sub-workflow
call, an HTTP API webhook and a form — taking `CONTENT` (the source text, required),
`ASSET_TYPES`, `FEEDBACK`, `FORCE` and `STYLE`, and MAY also take `SCENES`,
`EXTRA_PROMPT` and `SESSION_ID`. `FORCE` SHALL be one of `auto`, `diagram`, `story`,
`data`, `poster`, `code`, `chart`, `timeline`, `quote` or `ui`, and `STYLE` SHALL name a
brand scheme. `SCENES` SHALL be an optional positive integer requesting a sequence, and
when it is blank the composer's own storyboard SHALL decide the scene count.
`EXTRA_PROMPT` SHALL be optional free text appended to the brief after the content and
the rules. `SESSION_ID` SHALL be an optional session identifier: when it is present the
run SHALL continue that session, and when it is blank the run SHALL use an identifier
scoped to the run so the request is isolated. The workflow MUST NOT read caller state
from a table or sheet to decide what to produce; everything it needs arrives on the
trigger.

`image` is not a form: it is the raster authoring medium, selected by the requested
asset type, and a still is the fallback when the composer fails.

#### Scenario: Same contract on every surface
- **WHEN** the same parameters arrive via the API webhook, the form or a sub-workflow call
- **THEN** the same asset set is produced

#### Scenario: Missing content
- **WHEN** a request arrives without `CONTENT`
- **THEN** the request fails naming the missing parameter

#### Scenario: An unknown force fails loudly
- **WHEN** a request carries a `FORCE` outside the enum
- **THEN** the request fails naming the value
- **AND** no asset is produced

#### Scenario: An extra prompt is passed through
- **WHEN** a request carries `EXTRA_PROMPT`
- **THEN** the brief given to the composer ends with it verbatim
- **AND** a request without it produces a brief with no empty section

#### Scenario: A session is continued
- **WHEN** a request carries a `SESSION_ID`
- **THEN** the run addresses its artifact under that identifier and continues that session

#### Scenario: A run without a session id is isolated
- **WHEN** a request carries no `SESSION_ID`
- **THEN** the run uses an identifier scoped to that run
- **AND** it does not read or overwrite another run's session state

## ADDED Requirements

### Requirement: The form vocabulary is one file

The system SHALL define its visual forms, and what each one asks the composer to
build, in a single committed vocabulary. The composer's brief SHALL carry it, and the
classification that chooses a hook and MAY override the hook's default form SHALL read
the same vocabulary. A workflow MUST NOT restate the definitions in its own logic, and
the `FORCE` enum SHALL name exactly the vocabulary's forms plus `auto`.

#### Scenario: A forced form arrives with its definition

- **WHEN** a request pins a form with `FORCE`
- **THEN** the brief names that form and carries the vocabulary that defines it
- **AND** the definition is the one committed copy, not restated by the workflow

#### Scenario: The judge overrides with a defined form

- **WHEN** the classification overrides a hook's default form
- **THEN** it chooses from the vocabulary it was injected
- **AND** the chosen form is one the studio accepts

#### Scenario: The enum and the vocabulary agree

- **WHEN** the `FORCE` enum is declared
- **THEN** it is the vocabulary's forms plus `auto`
- **AND** a form the vocabulary does not define is rejected
