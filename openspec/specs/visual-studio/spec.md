# visual-studio Specification

## Purpose

Turns one source text into a set of visual assets through a declared type registry: a static image authored by the image model, and stills, clips, SVGs and a self-contained HTML deck authored by the composer agent. The workflow is generic and stateless between runs: parameters arrive on the trigger, the result is returned and recorded.

## Requirements

### Requirement: Types are declared in a registry

The system SHALL define its visual artifact types in a declarative registry, and each
type MUST declare how it is authored and its output format. Adding or changing a type
MUST be a registry change, not a change to the rendering logic. The registry SHALL
declare `image` (authored by the image model, png), `animation` (authored by the
composer agent, mp4), `animation_linkedin` (authored by the composer agent, gif, inside
the platform's GIF cap), `animation_linkedin_video` (authored by the composer agent,
mp4, at the feed's aspect), `svg` (authored by the composer agent, a self-contained
animated SVG), `deck` (authored by the composer agent, a self-contained HTML
presentation that the same run also renders to mp4) and `launch_card` (authored by the
composer agent, a still png at the announcement frame).

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

#### Scenario: A still type declares no clip
- **WHEN** the still raster type is read
- **THEN** it declares no per-scene floor and no frame budget beyond the single frame
  it ships

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

The workflow SHALL expose the same parameter contract on every trigger — a sub-workflow
call, an HTTP API webhook and a form — taking `CONTENT` (the source text, required),
`ASSET_TYPES`, `FEEDBACK`, `FORCE` and `STYLE`, and MAY also take `SCENES`,
`EXTRA_PROMPT` and `SESSION_ID`. `FORCE` SHALL be one of `auto`, `diagram`, `story`,
`data`, `poster`, `code`, `chart`, `timeline`, `quote`, `ui`, `manga` or `retro`, and
`STYLE` SHALL name a brand scheme. `SCENES` SHALL be an optional positive integer requesting a sequence, and
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

### Requirement: One file per requested and supported type

For a given request the system SHALL produce at most one asset per requested and supported type, with content derived only from the request. It MUST NOT produce duplicate assets for the same type in one run.

#### Scenario: Asset set produced
- **WHEN** a request asks for an image and an animation
- **THEN** one file per requested supported type is produced

#### Scenario: Duplicate request deduplicated
- **WHEN** the same type is requested twice in one request
- **THEN** exactly one asset is produced for that type

### Requirement: Asset content is returned; identity is the caller's

The system SHALL return each asset with its media type, its format, its own status and a
handle to its bytes: either the bytes themselves, or the object key an external process
stored them under. An **agent-authored** asset SHALL be named rather than carried — its
bytes are written to object storage by a process that is not the workflow, because n8n
persists a workflow's binaries as well as its JSON, and the asset carries the key, the byte
count and the media type. A **raster** asset SHALL carry its bytes as the data URL the image
model returned, because those bytes are produced inside n8n and no external process can
fetch them; nothing stores one on its behalf. It MUST NOT return a repository path or a
filename; deriving those and placing the asset remains the caller's job.

#### Scenario: An agent asset is named, not carried

- **WHEN** the studio returns an agent-authored asset
- **THEN** it carries the object key, the byte count and the media type
- **AND** it carries no base64 and no data URL

#### Scenario: A raster asset carries its own bytes

- **WHEN** the studio returns a raster asset
- **THEN** it carries the image as the data URL the model returned
- **AND** it names no object, because nothing stored one

#### Scenario: Studio invents no path

- **WHEN** the studio returns an asset
- **THEN** it returns the handle and the media type only
- **AND** it invents no repository path and no filename

#### Scenario: An asset that was not stored

- **WHEN** an agent asset's bytes could not be stored
- **THEN** it reports its error and names no object
- **AND** the run still reports its other assets

### Requirement: A requested image is produced even when every other asset fails

When the request includes the `image` type, the system SHALL produce it even if every animation fails, so a caller that always requests an image always gets one.

#### Scenario: An image survives animation failures
- **WHEN** one or more animations fail
- **THEN** the requested image is still produced

### Requirement: Model output is data, not commands

The system's own writes SHALL be limited to object storage and the `TemporalFiles`
DataTable; it MUST NOT write to any repository. A brief delivered to a model SHALL be
treated as data: no model-authored string may be executed as a command. The composition a
composer authors is the intended artifact, not a command to run.

#### Scenario: Model output is data

- **WHEN** a brief or an image prompt is handled
- **THEN** it is never executed as a command

#### Scenario: No run row is written

- **WHEN** any of the studio's workflows runs
- **THEN** it writes no DataTable row for the run itself
- **AND** the rendered asset is written to object storage instead

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

### Requirement: A request may carry a scene plan

An authoring request SHALL be able to declare how many scenes the authored visual
should carry, and the brief delivered to the composer SHALL state that the content
be rendered as one item per scene. WHEN the request declares more than one scene,
the brief SHALL also ask for an opening title scene that names the subject, placed
before the declared scenes, so the authored visual carries the declared count plus
the title. WHEN the request declares exactly one scene, the brief SHALL NOT ask for
a title scene. When the request declares no scene count, the composer SHALL choose
its own storyboard.

#### Scenario: A declared scene count is honoured

- **WHEN** a request declares a scene count
- **THEN** the brief asks for that many items, one per scene

#### Scenario: A multi-scene count opens on a title scene

- **WHEN** a request declares a scene count greater than one
- **THEN** the brief also asks for an opening title scene that names the subject
- **AND** the authored visual carries the declared count plus the title

#### Scenario: A single-scene count has no title scene

- **WHEN** a request declares a scene count of one
- **THEN** the brief asks for no title scene

#### Scenario: No scene count leaves the storyboard to the composer

- **WHEN** a request declares no scene count
- **THEN** the composer plans its own scenes

### Requirement: A request and a type may ask for effects

A request SHALL be able to name a visual effect, a registry block or a scene transition
in its brief, and the composer SHALL use it where one is named. The workflow SHALL NOT
curate a block list of its own; the catalogue is the framework's.

#### Scenario: A named effect is used
- **WHEN** a brief names a transition or an effect
- **THEN** the authored asset uses it
- **AND** the workflow carried no list of its own

### Requirement: A rendered asset is stored outside the response

The system SHALL write each **agent-authored** asset to object storage and SHALL carry the
object key in the run's response, so the caller can fetch the bytes and no row is needed to
name them. The writer SHALL NOT be the workflow that reports the asset: n8n persists a
workflow's binaries as well as its JSON, so a workflow that fetches an asset and uploads it
stores the asset as surely as one that carries it. It SHALL be a process holding a credential
scoped to one bucket and one prefix, and a key outside the `visual-studio/` prefix SHALL be
refused, as SHALL a key nested below it — the deployment prunes by listing that prefix with a
`/` delimiter, so a nested object is never seen by the prune. A failed write SHALL report that
asset's error rather than a key for an object that does not exist. A **raster** asset is
stored by nothing, and this requirement does not apply to it. The stored objects SHALL be
pruned on a bounded window, so the bucket cannot grow without limit.

#### Scenario: The asset is stored and named

- **WHEN** a run produces an agent-authored asset
- **THEN** its bytes are written to `datahub-local-temp` under a key derived from the run id and the asset type
- **AND** the response carries that key and the byte count
- **AND** the writer is a service that fetched them, not the workflow that reports them

#### Scenario: A failed write fails the run

- **WHEN** the asset cannot be written
- **THEN** that asset carries the failure as its error, and no key is reported for it
- **AND** the run reports itself FAILED when that was its only asset, and PARTIAL otherwise

#### Scenario: A run with nothing to store

- **WHEN** every agent asset of a run failed
- **THEN** the run still responds, with each asset's error
- **AND** it reports no key

#### Scenario: Stored objects expire

- **WHEN** a stored object is older than the retention window
- **THEN** it is deleted from the bucket
- **AND** an object inside the window is left alone

#### Scenario: A zero-byte render is not stored

- **WHEN** the source answers `200` with an empty body
- **THEN** nothing is written and that asset carries the failure
- **AND** no key is reported for an empty object

#### Scenario: A nested key is refused

- **WHEN** a destination with a further `/` below the prefix is requested
- **THEN** the write is refused, because the prune lists the prefix with a `/` delimiter
  and would never see such an object to delete it

#### Scenario: A deck's two files

- **WHEN** a deck run produces the deck and its paired video
- **THEN** both are stored and both are named
- **AND** each names its own object, the deck's carrying the deck's extension and the video's
  the video's

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

### Requirement: A type the registry cannot resolve is reported

WHEN a requested type cannot be resolved — an id the registry does not declare, or one
declared but not producible in the current environment — the system SHALL answer with an
asset carrying that id and a reason, and MUST NOT fail the run or block any other
requested asset. The answer SHALL be an asset in the run's asset list: an empty result is
not a report, and a caller may not have to distinguish "nothing was produced" from "no
answer was given".

#### Scenario: An agent type requested without a composer session
- **WHEN** an agent-authored type is requested and the composer session address is not configured
- **THEN** it is reported unavailable with a reason
- **AND** the requested image is still produced

#### Scenario: The only requested type cannot be resolved
- **WHEN** a request asks for one type the registry cannot resolve and nothing else
- **THEN** the run answers with that type's asset, carrying a reason that names it
- **AND** the run status reports the failure
- **AND** the caller sees the reason rather than an empty result

### Requirement: A still raster type is composed in one frame

WHEN a requested type's format is a still raster, the brief SHALL state that the whole
visual is complete and legible in the composition's **final** frame, and the produced
asset SHALL be that frame of the render. The brief MUST NOT require the composer to
suppress motion: an entrance MAY run, because the sampled frame is the settled one, and
the constraint the brief carries is that nothing may leave, dim or hide before the end.
The system MUST NOT require the composer to hold a finished composition for a duration,
and the part of the composition before the sampled frame is not part of the artifact.

A still type SHALL be selectable like any other type and SHALL NOT be produced by
interpreting a moving composition or by templating a layout.

#### Scenario: The card is complete in the sampled frame
- **WHEN** a still raster type is requested
- **THEN** the brief names the final frame as the artifact
- **AND** it forbids an element leaving, dimming or hiding before that frame

#### Scenario: A still is legible without motion
- **WHEN** the still asset is fetched
- **THEN** it is a complete, readable visual on its own
- **AND** no scene of a clip was selected to stand in for it
