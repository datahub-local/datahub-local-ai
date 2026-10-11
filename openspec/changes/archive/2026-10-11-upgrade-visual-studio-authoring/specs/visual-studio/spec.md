# Spec Delta

## MODIFIED Requirements

### Requirement: Types are declared in a registry

The system SHALL define its visual artifact types in a declarative registry, and each
type MUST declare how it is authored and its output format. Adding or changing a type
MUST be a registry change, not a change to the rendering logic. The registry SHALL
declare `image` (authored by the image model, png), `animation` (authored by the
composer agent, mp4), `animation_linkedin` (authored by the composer agent, gif, inside
the platform's GIF cap), `animation_linkedin_video` (authored by the composer agent,
mp4, at the feed's aspect), `svg` (authored by the composer agent, a self-contained
animated SVG) and `deck` (authored by the composer agent, a self-contained HTML
presentation that the same run also renders to mp4).

A type MUST NOT require a frozen final frame: an animated type's declared budget SHALL
NOT mandate a hold during which nothing moves.

#### Scenario: Registry drives the work
- **WHEN** the workflow starts
- **THEN** the set of artifacts to produce comes from the registry, not from hard-coded branches

#### Scenario: Unknown type
- **WHEN** a requested type is not in the registry
- **THEN** the request is rejected with a reason naming the unknown type
- **AND** no asset is produced for it

#### Scenario: No type mandates a frozen frame
- **WHEN** an animated type's budget is read
- **THEN** it declares no frozen-hold requirement
- **AND** the brief asks for an ambient idle rather than a still final frame

### Requirement: Every trigger speaks one contract

The workflow SHALL expose the same parameter contract on every trigger — a sub-workflow
call, an HTTP API webhook and a form — taking `CONTENT` (the source text, required),
`ASSET_TYPES`, `FEEDBACK`, `FORCE` and `STYLE`, and MAY also take `SCENES`,
`EXTRA_PROMPT` and `SESSION_ID`. `FORCE` SHALL be one of `auto`, `diagram`, `story`,
`data`, `poster` or `image`, and `STYLE` SHALL name a brand scheme. `SCENES` SHALL be an
optional positive integer requesting a sequence, and when it is blank the composer's own
storyboard SHALL decide the scene count. `EXTRA_PROMPT` SHALL be optional free text
appended to the brief after the content and the rules. `SESSION_ID` SHALL be an optional
session identifier: when it is present the run SHALL continue that session, and when it
is blank the run SHALL use an identifier scoped to the run so the request is isolated.
The workflow MUST NOT read caller state from a table or sheet to decide what to produce;
everything it needs arrives on the trigger.

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

### Requirement: A visual is authored by one agent

For an `animation`, `animation_linkedin` or `deck` type the system SHALL produce the
asset by having the composer agent author a composition from the request's content and
render it, without a typed content spec and without a template or layout the workflow
selects. The workflow MUST NOT send the agent a form to fill; it sends the content, the
requested form, the style, the output budget and the shared motion rules.

#### Scenario: An animation is authored, not templated
- **WHEN** an `animation` asset is requested
- **THEN** the composer agent authors the composition
- **AND** the workflow performed no markup generation of its own

#### Scenario: The agent plans before it builds
- **WHEN** the composer authors an asset
- **THEN** it first states a storyboard (form, style, scenes)
- **AND** the storyboard is recorded with the run

#### Scenario: The brief carries the motion rules
- **WHEN** the composer authors any asset
- **THEN** the brief carries the shared motion rules
- **AND** the workflow did not restate them in its own logic

## ADDED Requirements

### Requirement: A request and a type may ask for effects

A request SHALL be able to name a visual effect, a registry block or a scene transition
in its brief, and the composer SHALL use it where one is named. The workflow SHALL NOT
curate a block list of its own; the catalogue is the framework's.

#### Scenario: A named effect is used
- **WHEN** a brief names a transition or an effect
- **THEN** the authored asset uses it
- **AND** the workflow carried no list of its own
