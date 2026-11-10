# Spec Delta

## ADDED Requirements

### Requirement: The drafting turn reports the body's count before answering

The adapter SHALL hand the drafting and editing turns the row's word budget, and the image SHALL
carry a command that prints the body's word count against the limit the gate enforces, computed by
the same functions the gate uses, and exits non-zero when the body is past that limit. The drafting,
article-task and editing prompts SHALL require the command before the turn answers and SHALL
require the body to be cut until it reports inside the limit. The budget SHALL be supplied per turn,
so a retry reads the row's current value rather than one stored beside the session.

#### Scenario: A draft past the limit

- **WHEN** the turn runs the command on a body past the ten percent limit
- **THEN** it prints the body's count, the limit and the words to cut
- **AND** it exits non-zero
- **AND** the turn cuts the body and runs it again before answering

#### Scenario: A draft inside the limit

- **WHEN** the turn runs the command on a body at or under the limit
- **THEN** it prints the count and the limit
- **AND** it exits zero

#### Scenario: No budget on the turn

- **WHEN** the turn carries no budget
- **THEN** the command prints no count against a limit
- **AND** it does not fail for length

## MODIFIED Requirements

### Requirement: Assets are produced and reviewed as a set

The system SHALL request the entry's visual asset set from the `visual-studio` capability, naming types from that capability's registry. A raster hero SHALL always be requested and is the article's hero — the image social platforms preview when the page carries no `og:image`, which this blog does not emit; a blank `ASSET_TYPES` SHALL resolve to `image_wide,svg_wide`, and a declared list SHALL add to the hero rather than replace it. This lane SHALL request wide frames only: a row naming the portrait `image` or `svg` SHALL be normalized to `image_wide` or `svg_wide` before the set is requested, because the article is read in a text column and a 4:5 asset is a phone poster there. The request SHALL carry the entry's session identity, so a later request for the same entry continues the same authoring. Each asset SHALL be recorded as its own row in `article_assets` with a review state distinct from the article review state and from every other asset's, and SHALL be sent to Slack for that asset's approval. A row SHALL be identified by the entry and the asset type together, and a write for one type MUST NOT change another type's row.

#### Scenario: Asset set produced
- **WHEN** an article draft exists for the entry
- **THEN** the requested assets are produced, each with a row in `article_assets`
- **AND** each asset's review state is awaiting review
- **AND** each asset is sent to Slack for approval

#### Scenario: A portrait type is requested
- **WHEN** the entry's `ASSET_TYPES` names `image` or `svg`
- **THEN** the request asks for `image_wide` or `svg_wide` instead
- **AND** no 4:5 asset is produced for the article

#### Scenario: One asset fails
- **WHEN** one asset cannot be produced
- **THEN** that asset's review state is an error state naming the failure
- **AND** every other asset and the article draft are unaffected

#### Scenario: A requested type is not in the registry
- **WHEN** the entry requests a type the registry does not declare
- **THEN** that asset's review state is an error state naming the type
- **AND** the other requested assets are produced and reviewed normally

#### Scenario: One asset's row is written
- **WHEN** an asset is stored or its review state changes
- **THEN** only the row with that entry and that asset type is written
- **AND** every other requested asset keeps its own row and review state
