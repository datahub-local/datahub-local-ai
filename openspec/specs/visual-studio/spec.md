# visual-studio Specification

## Purpose

Turns one source text into a set of visual assets through a declared type registry: a static image authored by the image model, and animations authored by the composer agent. The workflow is generic and stateless between runs: parameters arrive on the trigger, the result is returned and recorded.

## Requirements

### Requirement: Types are declared in a registry

The system SHALL define its visual artifact types in a declarative registry, and each type MUST declare how it is authored and its output format. Adding or changing a type MUST be a registry change, not a change to the rendering logic. The registry SHALL declare `image` (authored by the image model, png), `animation` (authored by the composer agent, mp4) and `animation_linkedin` (authored by the composer agent, gif, inside the platform's GIF cap).

#### Scenario: Registry drives the work
- **WHEN** the workflow starts
- **THEN** the set of artifacts to produce comes from the registry, not from hard-coded branches

#### Scenario: Unknown type
- **WHEN** a requested type is not in the registry
- **THEN** the request is rejected with a reason naming the unknown type
- **AND** no asset is produced for it

### Requirement: The requested set is a trigger parameter

The set of asset types to produce SHALL be declared by the caller in the `ASSET_TYPES` parameter, identically on every trigger. When the declaration is blank, the system SHALL apply the registry's documented default rather than producing nothing. A request MAY carry at most the registry's per-request cap of types; a set over the cap SHALL be reported, not silently truncated.

#### Scenario: Declared set is used
- **WHEN** a request declares an image and an animation
- **THEN** exactly those assets are produced

#### Scenario: Blank declaration
- **WHEN** a request declares no asset types
- **THEN** the registry's default set is produced

#### Scenario: Over the cap
- **WHEN** a request declares more types than the cap
- **THEN** the types within the cap are produced
- **AND** each remaining type is reported as skipped with the cap as the reason

### Requirement: Every trigger speaks one contract

The workflow SHALL expose the same parameter contract on every trigger — a sub-workflow call, an HTTP API webhook and a form — taking `CONTENT` (the source text, required), `ASSET_TYPES`, `FEEDBACK`, `FORCE` and `STYLE`. `FORCE` SHALL be one of `auto`, `diagram`, `story`, `data`, `poster` or `image`, and `STYLE` SHALL name a brand scheme. The workflow MUST NOT read caller state from a table or sheet to decide what to produce; everything it needs arrives on the trigger.

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

### Requirement: One file per requested and supported type

For a given request the system SHALL produce at most one asset per requested and supported type, with content derived only from the request. It MUST NOT produce duplicate assets for the same type in one run.

#### Scenario: Asset set produced
- **WHEN** a request asks for an image and an animation
- **THEN** one file per requested supported type is produced

#### Scenario: Duplicate request deduplicated
- **WHEN** the same type is requested twice in one request
- **THEN** exactly one asset is produced for that type

### Requirement: Asset content is returned; identity is the caller's

The system SHALL return each asset with its content (image data, markup or text) and its format. It MUST NOT return a repository path, a URL or a filename; deriving those and placing the asset is the caller's job.

#### Scenario: Studio invents no path
- **WHEN** the studio returns an asset
- **THEN** it returns content and type only

### Requirement: A requested image is produced even when every other asset fails

When the request includes the `image` type, the system SHALL produce it even if every animation fails, so a caller that always requests an image always gets one.

#### Scenario: An image survives animation failures
- **WHEN** one or more animations fail
- **THEN** the requested image is still produced

### Requirement: A declared-but-unavailable type is reported

WHEN a requested type is declared but not producible in the current environment, the system SHALL report it as unavailable with a reason and MUST NOT fail the run or block the other assets.

#### Scenario: An agent type requested without a composer session
- **WHEN** an agent-authored type is requested and the composer session address is not configured
- **THEN** it is reported unavailable with a reason
- **AND** the requested image is still produced

### Requirement: Every run is recorded for later retrieval

The system SHALL record one row per run in a `visual_studio_table` DataTable, keyed by an auto-generated `RUN_ID` (the execution id), carrying the request parameters and the full result — every asset with its status, content and any error — so a caller can fetch a run's outcome over HTTP after the fact. The run's response SHALL carry the same outcome.

#### Scenario: Run recorded
- **WHEN** a run finishes
- **THEN** exactly one row is recorded with the run id, the request and every asset's outcome
- **AND** the response carries the same asset set

#### Scenario: Result fetched later
- **WHEN** a caller reads the run row by `RUN_ID`
- **THEN** it can reconstruct every asset the run produced, including its content

### Requirement: Model output is data, not commands

The system's own writes SHALL be limited to the `visual_studio_table` DataTable; it MUST NOT write to any repository. A brief delivered to a model SHALL be treated as data: no model-authored string may be executed as a command. The composition a composer authors is the intended artifact, not a command to run.

#### Scenario: Model output is data
- **WHEN** a brief or an image prompt is handled
- **THEN** it is never executed as a command

### Requirement: Studio assets follow the brand for their kind

Every asset the studio produces SHALL follow the shared brand tokens for its
kind. A diagrammatic asset — the `image` or an `animation` — SHALL be rendered
from the brand's flat UI language: its scheme surface, the moss accent ramp, the
brand typefaces (or, on a capture surface that cannot carry a brand face, the
substitute the token document declares for it), and the shared radii, borders and
pill shapes. A photographic image SHALL be produced from a prompt carrying the
brand's photographic art direction. The studio SHALL NOT define a palette or a
typeface of its own, and the accents it offers a caller SHALL be the brand's.

#### Scenario: A diagrammatic asset is branded
- **WHEN** the studio produces the image or an animation
- **THEN** its colours, typefaces and shapes come from the brand tokens
- **AND** no palette outside the brand is introduced

#### Scenario: A photographic image is branded by art direction
- **WHEN** the studio produces a photographic image
- **THEN** its prompt carries the brand's photographic art direction
- **AND** it is not asked to reproduce UI tokens

#### Scenario: The caller cannot pick a non-brand palette
- **WHEN** a request supplies an accent or leaves it blank
- **THEN** the value used is inside the brand's accent ramp
- **AND** an out-of-brand value is not rendered

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
