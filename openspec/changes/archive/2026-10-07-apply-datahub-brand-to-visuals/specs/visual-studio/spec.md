# Spec Delta

## ADDED Requirements

### Requirement: Studio assets follow the shared brand

Every asset the studio produces SHALL follow the shared brand tokens for its
kind. A diagrammatic asset — an infographic, diagram, animated image, animated
SVG or video — SHALL be rendered from the brand's flat UI language: its scheme
surface, the moss accent ramp, the brand typefaces (or, on a capture surface that
cannot carry a brand face, the substitute the token document declares for it),
and the shared radii, borders and pill shapes. A raster hero SHALL be produced
from a prompt carrying the brand's photographic art direction. The studio SHALL
NOT define a palette or a typeface of its own, and the accents it offers a caller
SHALL be the brand's.

#### Scenario: A spec-driven asset is branded
- **WHEN** the studio renders an infographic, diagram, animated image, animated SVG or video
- **THEN** its markup, colours, typefaces and shapes come from the brand tokens
- **AND** no palette outside the brand is introduced

#### Scenario: A raster hero is branded by art direction
- **WHEN** the studio produces the static hero
- **THEN** its prompt carries the brand's photographic art direction
- **AND** it is not asked to reproduce UI tokens

#### Scenario: The caller cannot pick a non-brand palette
- **WHEN** a request supplies an accent or leaves it blank
- **THEN** the value used is inside the brand's accent ramp
- **AND** an out-of-brand value is not rendered
