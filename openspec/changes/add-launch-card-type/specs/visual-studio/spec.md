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

## ADDED Requirements

### Requirement: A still raster type is composed in one frame

WHEN a requested type's format is a still raster, the brief SHALL state that the whole
visual is composed in the composition's first frame, and that nothing arrives by
fading, sliding or typing. The produced asset SHALL be that first frame of the render,
and the system MUST NOT require the composer to hold a finished composition for a
duration — the part of the composition after the first frame is not sampled and is not
part of the artifact.

A still type SHALL be selectable like any other type and SHALL NOT be produced by
interpreting a moving composition or by templating a layout.

#### Scenario: The card is complete in the first frame
- **WHEN** a still raster type is requested
- **THEN** the brief asks for the whole visual in the first frame
- **AND** no element is left to an entrance animation

#### Scenario: A still is legible without motion
- **WHEN** the still asset is fetched
- **THEN** it is a complete, readable visual on its own
- **AND** no scene of a clip was selected to stand in for it
