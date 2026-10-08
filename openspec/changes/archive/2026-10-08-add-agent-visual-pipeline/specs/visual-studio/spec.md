# Spec Delta

## REMOVED Requirements

### Requirement: Authoring is two-stage

Removed: the model no longer fills a typed content spec; the composer agent authors the
composition directly, so there is no second deterministic stage to derive markup from.

### Requirement: A frozen spec is applied, not re-authored

Removed: there is no content spec to freeze. Agent authoring is deliberately
non-deterministic, so a re-render is not guaranteed identical.

### Requirement: Animation is rendered from a browser timeline

Removed: frame capture and assembly move into the composer's own render, driven by the
type's declared format and budget rather than by a workflow template.

### Requirement: Animated SVG is authored as text

Removed: SVG is one of the outputs the composer may produce, not a separate template.

## MODIFIED Requirements

### Requirement: Types are declared in a registry

The system SHALL define its visual artifact types in a declarative registry, and each
type MUST declare how it is authored and its output format. Adding or changing a type
MUST be a registry change, not a change to the rendering logic. The registry SHALL
declare `image` (authored by the image model, png), `animation` (authored by the composer
agent, mp4) and `animation_linkedin` (authored by the composer agent, gif, inside the
platform's GIF cap).

#### Scenario: Registry drives the work
- **WHEN** the workflow starts
- **THEN** the set of artifacts to produce comes from the registry, not from hard-coded branches

#### Scenario: Unknown type
- **WHEN** a requested type is not in the registry
- **THEN** the request is rejected with a reason naming the unknown type
- **AND** no asset is produced for it

### Requirement: Every trigger speaks one contract

The workflow SHALL expose the same parameter contract on every trigger — a sub-workflow
call, an HTTP API webhook and a form — taking `CONTENT` (the source text, required),
`ASSET_TYPES`, `FEEDBACK`, `FORCE` and `STYLE`. `FORCE` SHALL be one of `auto`,
`diagram`, `story`, `data`, `poster` or `image`, and `STYLE` SHALL name a brand scheme.
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

## ADDED Requirements

### Requirement: A visual is authored by one agent

For an `animation` type the system SHALL produce the asset by having the composer agent
author a composition from the request's content and render it, without a typed content
spec and without a template or layout the workflow selects. The workflow MUST NOT send
the agent a form to fill; it sends the content, the requested form, the style and the
output budget.

#### Scenario: An animation is authored, not templated
- **WHEN** an `animation` asset is requested
- **THEN** the composer agent authors the composition
- **AND** the workflow performed no markup generation of its own

#### Scenario: The agent plans before it builds
- **WHEN** the composer authors an asset
- **THEN** it first states a storyboard (form, style, scenes)
- **AND** the storyboard is recorded with the run

### Requirement: The request may force the form

The system SHALL let a request pin the form of an authored visual with `FORCE`, and SHALL
let the agent choose the form when `FORCE` is `auto`. A forced form MUST be honoured or
reported, never silently replaced.

#### Scenario: A forced form is honoured
- **WHEN** a request sets `FORCE=diagram`
- **THEN** the authored asset is a diagram

#### Scenario: Auto lets the agent choose
- **WHEN** a request sets `FORCE=auto`
- **THEN** the agent picks the form that fits the content

### Requirement: The style is a brand scheme

An authored visual's style SHALL be one of the brand's declared schemes, and a request's
`STYLE` MUST name one. The composer MUST NOT introduce a palette or typeface the brand
does not define.

#### Scenario: A requested scheme is used
- **WHEN** a request sets `STYLE=light`
- **THEN** the authored asset uses the brand's light scheme

#### Scenario: An unknown scheme fails
- **WHEN** a request names a style that is not a brand scheme
- **THEN** the request fails naming it
