# visual-brand Specification

## Purpose
Gives every visual-generation flow in the repository one committed source of
brand tokens, extracted from the published site, so a diagram, an animation and
an image read as the same product.

## Requirements

### Requirement: One committed source of brand tokens

The system SHALL carry exactly one committed brand-token document describing the
palette, the typography, the shared layout idioms (radii, borders, surfaces,
pills) and the available colour schemes. Every surface that produces a visual
SHALL derive its colours and typefaces from that document. A colour or typeface
value written outside it SHALL be treated as a defect rather than a second source
of truth.

#### Scenario: A single source
- **WHEN** a visual-generation surface needs a colour or a typeface
- **THEN** it reads it from the brand-token document
- **AND** no other file defines that value for a generated visual

#### Scenario: The tokens change the output
- **WHEN** a brand token used by a surface changes
- **THEN** the next asset that surface produces reflects the change
- **AND** changing it requires no edit to that surface's code or prompt

### Requirement: The tokens are extracted from the site and re-syncable

The brand-token document SHALL be derived from the site repository that owns the
canonical brand, by a documented and repeatable step. Re-running that step
against unchanged upstream SHALL produce no change; a real upstream change SHALL
appear as a reviewable diff. The canonical source SHALL be named in the
documentation, and the extraction SHALL NOT be required at render or run time.

#### Scenario: An unchanged re-sync is a no-op
- **WHEN** the extraction step is re-run with the upstream brand unchanged
- **THEN** the committed token document is byte-identical
- **AND** no diff is produced

#### Scenario: An upstream change is reviewable
- **WHEN** a canonical colour or typeface changes upstream
- **THEN** the extraction produces a diff limited to the changed tokens
- **AND** the change is reviewed before it reaches a generated asset

#### Scenario: No network at generation time
- **WHEN** an asset is generated
- **THEN** its brand tokens are read from the committed document
- **AND** no request is made to the site to fetch them

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

### Requirement: The brand spans two schemes and an asset declares its own

The brand SHALL define a dark scheme and a light scheme. A diagrammatic asset
SHALL use exactly one of them, chosen by the producer, and SHALL be internally
consistent: text, surfaces and accents all come from the same scheme.

#### Scenario: Dark scheme
- **WHEN** a diagrammatic asset uses the dark scheme
- **THEN** its background, text and accent all come from the dark scheme's tokens

#### Scenario: Light scheme
- **WHEN** a diagrammatic asset uses the light scheme
- **THEN** its background, text and accent all come from the light scheme's tokens

### Requirement: No logo is baked into a generated asset

A generated visual SHALL NOT include the project's logo, wordmark or icon. The
brand SHALL reach a generated asset through palette and typography only.

#### Scenario: Logo is absent
- **WHEN** any visual is generated
- **THEN** the output contains no logo, wordmark or icon mark
- **AND** the brand is still recognisable through palette and type
