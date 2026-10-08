# Spec Delta

## REMOVED Requirements

### Requirement: A requested static hero is produced even when every other asset fails

**Reason**: The registry no longer declares a static "hero"; its place is the `image`
type. The guarantee is re-issued for that type.

**Migration**: None — behaviour is unchanged and restated by "A requested image is
produced even when every other asset fails".

### Requirement: A declared-but-unavailable type is reported, not skipped

**Reason**: Its scenario named `motion_clip`, a type no longer in the registry; the
requirement is re-issued with a current example.

**Migration**: None — behaviour is unchanged and restated by "A declared-but-unavailable
type is reported".

### Requirement: Studio assets follow the shared brand

**Reason**: Its wording and scenarios listed retired kinds ("animated SVG") and the
retired "spec-driven" path. The guarantee is re-issued for the current kinds.

**Migration**: None — behaviour is unchanged and restated by "Studio assets follow the
brand for their kind".

## MODIFIED Requirements

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

### Requirement: One file per requested and supported type

For a given request the system SHALL produce at most one asset per requested and supported type, with content derived only from the request. It MUST NOT produce duplicate assets for the same type in one run.

#### Scenario: Asset set produced
- **WHEN** a request asks for an image and an animation
- **THEN** one file per requested supported type is produced

#### Scenario: Duplicate request deduplicated
- **WHEN** the same type is requested twice in one request
- **THEN** exactly one asset is produced for that type

### Requirement: Model output is data, not commands

The system's own writes SHALL be limited to the `visual_studio_table` DataTable; it MUST NOT write to any repository. A brief delivered to a model SHALL be treated as data: no model-authored string may be executed as a command. The composition a composer authors is the intended artifact, not a command to run.

#### Scenario: Model output is data
- **WHEN** a brief or an image prompt is handled
- **THEN** it is never executed as a command

## ADDED Requirements

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
