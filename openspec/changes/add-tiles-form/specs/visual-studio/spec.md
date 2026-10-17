# Spec Delta

## ADDED Requirements

### Requirement: A type may pin the form it means

A visual artifact type SHALL be able to declare the form it means, from the shared
vocabulary, and a declared form MUST be one the vocabulary defines. When a type declares
one, the studio SHALL honour it ahead of the caller's `FORCE`, because choosing the type
is choosing its shape. A type that declares no form SHALL take the caller's `FORCE`, and
with neither the composer SHALL choose. The workflow MUST NOT restate the form's
definition in its own logic: the brief carries the committed vocabulary.

#### Scenario: A type's form is honoured

- **WHEN** a type declares a form and a request pins another
- **THEN** the authored asset takes the type's form
- **AND** the request's pin is not silently substituted for it

#### Scenario: A type without a form takes the request's

- **WHEN** a type declares no form
- **THEN** the request's `FORCE` applies
- **AND** with `FORCE=auto` the composer chooses the form

#### Scenario: An undefined form is caught before the composer

- **WHEN** a type declares a form the vocabulary does not define
- **THEN** the offline registry check fails, naming the type and the value
- **AND** the composer is never handed prose the vocabulary does not carry

## MODIFIED Requirements

### Requirement: Types are declared in a registry

The system SHALL define its visual artifact types in a declarative registry, and each
type MUST declare how it is authored and its output format. Adding or changing a type
MUST be a registry change, not a change to the rendering logic. The registry SHALL
declare `image` (authored by the image model, png), `image_wide` (the same raster at
16:9), `animation` (authored by the composer agent, mp4), `animation_linkedin` (authored
by the composer agent, gif, inside the platform's GIF cap), `animation_linkedin_video`
(authored by the composer agent, mp4, at the feed's aspect), `tiles` (authored by the
composer agent, a looping tiled pattern drawn by a seeded walk, mp4, at the feed's
aspect), `tiles_wide` (the same loop at 16:9), `svg` (authored by the composer agent, a
self-contained animated SVG), `svg_wide` (the same animated SVG at 16:9), `deck`
(authored by the composer agent, a self-contained HTML presentation that the same run also
renders to mp4) and `launch_card` (authored by the composer agent, a still png at the
announcement frame).

A type MUST NOT require a frozen final frame: an animated type's declared budget SHALL
NOT mandate a hold during which nothing moves. A type whose shape is a continuous pattern
rather than a sequence SHALL declare no per-scene floor, and its frames SHALL follow the
rate it declares, so its length is a registry value.

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

#### Scenario: A still type declares no clip
- **WHEN** the still raster type is read
- **THEN** it declares no per-scene floor and no frame budget beyond the single frame
  it ships

#### Scenario: A pattern loop declares no scene floor
- **WHEN** a tiling type is read
- **THEN** it declares no per-scene floor
- **AND** a caller's scene count does not stretch it, because its shape is one continuous
  field

### Requirement: Every trigger speaks one contract

The workflow SHALL expose the same parameter contract on every trigger — a sub-workflow
call, an HTTP API webhook and a form — taking `CONTENT` (the source text, required),
`ASSET_TYPES`, `FEEDBACK`, `FORCE` and `STYLE`, and MAY also take `SCENES`,
`EXTRA_PROMPT` and `SESSION_ID`. `FORCE` SHALL be one of `auto`, `diagram`, `story`,
`data`, `poster`, `code`, `chart`, `timeline`, `quote`, `ui`, `manga`, `retro` or
`tiles`, and `STYLE` SHALL name a brand scheme. `SCENES` SHALL be an optional positive
integer requesting a sequence, and when it is blank the composer's own storyboard SHALL
decide the scene count. `EXTRA_PROMPT` SHALL be optional free text appended to the brief
after the content and the rules. `SESSION_ID` SHALL be an optional session identifier:
when it is present the run SHALL continue that session, and when it is blank the run SHALL
use an identifier scoped to the run so the request is isolated. The workflow MUST NOT read
caller state from a table or sheet to decide what to produce; everything it needs arrives
on the trigger.

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

#### Scenario: A pinned form needs no free text
- **WHEN** a request pins a form through `FORCE` and carries no `EXTRA_PROMPT`
- **THEN** the brief is shaped by that form and its definition
- **AND** free text is not the only channel by which a shape can be asked for
