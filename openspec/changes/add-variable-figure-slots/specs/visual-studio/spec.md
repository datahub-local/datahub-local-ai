# Spec Delta

## ADDED Requirements

### Requirement: A figure is authored from its section

The registry SHALL declare a `figure` type for a section illustration in an article: authored by
the composer agent, a static SVG at 16:9. A request for that type SHALL carry the heading and text
of the section the slot sits in, and the type's brief SHALL illustrate that section rather than the
source as a whole. The type SHALL be authored once per requested slot, so a caller that needs
several figures requests the type several times with different section briefs.

#### Scenario: Two figures, two sections

- **WHEN** the caller requests two figure slots with different section briefs
- **THEN** each is authored from its own section
- **AND** each returns its own SVG

#### Scenario: A figure slot has no section

- **WHEN** a figure request carries no section text
- **THEN** the request is refused with a reason naming the missing brief
- **AND** no figure is authored

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
self-contained animated SVG), `svg_wide` (the same animated SVG at 16:9), `figure`
(authored by the composer agent, a self-contained static SVG at 16:9 that illustrates the
section brief it was given), `deck` (authored by the composer agent, a self-contained HTML
presentation that the same run also renders to mp4) and `launch_card` (authored by the
composer agent, a still png at the announcement frame).

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
