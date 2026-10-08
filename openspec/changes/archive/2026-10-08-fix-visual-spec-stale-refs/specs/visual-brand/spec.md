# Spec Delta

## REMOVED Requirements

### Requirement: A generated visual follows the brand for its kind

**Reason**: Its wording and scenarios named retired kinds ("infographic", "animated
SVG") and a "hero". The guarantee is re-issued for the current kinds.

**Migration**: None — behaviour is unchanged and restated by "A generated visual
applies the brand for its kind".

## ADDED Requirements

### Requirement: A generated visual applies the brand for its kind

The system SHALL distinguish two visual kinds and apply the brand differently to
each. A **diagrammatic** asset — the `image` or an `animation` — SHALL use the
brand's flat UI language: its dark or light scheme surface, the moss accent ramp,
the brand typefaces, and the shared radii, thin borders and pill shapes. A
**photographic** asset — a photographic image — SHALL be described to its
generator in the brand's photographic art direction rather than its UI tokens.

#### Scenario: A diagram uses the flat UI language
- **WHEN** the image or an animation is produced
- **THEN** its surface, accents, type and shapes come from the brand's flat UI language
- **AND** it does not introduce a palette the brand does not define

#### Scenario: A photographic image uses the art direction
- **WHEN** a photographic image is produced
- **THEN** its prompt carries the brand's photographic art direction
- **AND** it is not asked to render UI tokens such as hex accents or typefaces

#### Scenario: The two do not mix
- **WHEN** a photographic asset is produced
- **THEN** it is not styled as an interface card
- **AND** when a diagrammatic asset is produced, it is not delegated to the photographic art direction
