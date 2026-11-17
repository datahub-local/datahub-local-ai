# Spec Delta

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
self-contained animated SVG), `svg_wide` (the same animated SVG at 16:9), `sketch`
(authored by the composer agent, a hand-drawn diagram whose strokes draw themselves on,
mp4 at 16:9), `sketch_svg` (the same drawing as a self-contained animated SVG at 16:9),
`figure` (authored by the composer agent, a self-contained static SVG at 16:9 that
illustrates the section brief it was given), `deck` (authored by the composer agent, a
self-contained HTML presentation that the same run also renders to mp4) and `launch_card`
(authored by the composer agent, a still png at the announcement frame).

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

#### Scenario: A sketch is one drawing
- **WHEN** a sketch type is read
- **THEN** it declares no per-scene floor and no intro scene
- **AND** a caller's scene count does not stretch it, because its shape is one drawing
  completing

### Requirement: The request may force the form

The system SHALL let a request pin the form of an authored visual with `FORCE`, and SHALL
let the agent choose the form when `FORCE` is `auto`. A forced form MUST be honoured or
reported, never silently replaced. `FORCE` SHALL accept `sketch`, which asks for a
hand-drawn diagram whose strokes draw themselves on.

#### Scenario: A forced form is honoured
- **WHEN** a request sets `FORCE=diagram`
- **THEN** the authored asset is a diagram

#### Scenario: Auto lets the agent choose
- **WHEN** a request sets `FORCE=auto`
- **THEN** the agent picks the form that fits the content

#### Scenario: A sketch is honoured
- **WHEN** a request sets `FORCE=sketch`
- **THEN** the authored asset is a hand-drawn diagram whose strokes draw themselves on
- **AND** it keeps the brand's palette and typeface, roughening geometry rather than
  introducing a sketch typeface
