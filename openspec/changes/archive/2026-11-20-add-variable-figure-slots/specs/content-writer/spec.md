# Spec Delta

## ADDED Requirements

### Requirement: The approved draft is the asset plan

The number of images an article carries SHALL be derived from the approved draft, not from the
entry's declared type list. A draft MAY carry zero or more section figures, each written as
`<!-- asset:figure -->` directly after the section it illustrates, and the entry's `MAX_FIGURES`
(blank reads as three, total ceiling five with the hero) SHALL cap how many the draft may carry. The
requested set for the assets and publish phases SHALL be derived once from the stored draft as the
declared hero plus one slot per figure marker, in document order, and every consumer that authors,
reviews, gates or commits an asset SHALL read that one derivation.

#### Scenario: A short article carries no figures

- **WHEN** the approved draft carries only the hero marker
- **THEN** the asset plan is the hero alone
- **AND** no figure is authored or reviewed

#### Scenario: A walk-through carries several figures

- **WHEN** the approved draft carries four figure markers and the cap is four
- **THEN** the plan names `figure_1` to `figure_4` in document order
- **AND** each is authored, reviewed and committed at its own marker

#### Scenario: The cap is exceeded

- **WHEN** the draft carries more figure markers than the entry's cap
- **THEN** the drafting gate rejects it naming the count and the cap
- **AND** no asset is authored for the excess

#### Scenario: The plan changes on a new draft

- **WHEN** an article that already had figures is re-drafted and approved
- **THEN** every `figure_*` row for the entry is retired before the new plan is authored
- **AND** the hero keeps its existing approval

### Requirement: A figure is authored from its own section

A figure slot SHALL name the heading and the text of the section it sits in, and the studio request
for that slot SHALL carry them as the brief, so a figure illustrates its own section rather than a
second reading of the opening. A figure slot SHALL be requested as the registry's `figure` type and
stored as `figure_<k>`, and its committed reference SHALL be
`/img/<slug>-figure-<k>.<ext>` with the section heading as alt text.

#### Scenario: Two figures in different sections

- **WHEN** the plan carries two figure slots in different sections
- **THEN** each studio request carries its own section's heading and text
- **AND** the two committed references name different slots

## MODIFIED Requirements

### Requirement: Assets are produced and reviewed as a set

The system SHALL request the entry's visual asset set from the `visual-studio` capability, naming types from that capability's registry. The default hero SHALL be the composer-authored `svg_wide`, and a blank `ASSET_TYPES` SHALL resolve to it; a row that explicitly names `image` or `image_wide` keeps that raster, and a declared list is the set rather than an addition to a second hero. This lane SHALL request wide frames only: a row naming the portrait `image` or `svg` SHALL be normalized to `image_wide` or `svg_wide` before the set is requested, because the article is read in a text column and a 4:5 asset is a phone poster there. Section figures SHALL be added to the set from the approved draft as positional slots, never from `ASSET_TYPES`. The request SHALL carry the entry's session identity, so a later request for the same entry continues the same authoring. Each asset SHALL be recorded as its own row in `article_assets` — `figure_<k>` for a figure — with a review state distinct from the article review state and from every other asset's, and SHALL be sent to Slack for that asset's approval.

#### Scenario: Asset set produced
- **WHEN** an article draft exists for the entry
- **THEN** the requested assets are produced, each with a row in `article_assets`
- **AND** each asset's review state is awaiting review
- **AND** each asset is sent to Slack for approval

#### Scenario: A portrait type is requested
- **WHEN** the entry's `ASSET_TYPES` names `image` or `svg`
- **THEN** the request asks for `image_wide` or `svg_wide` instead
- **AND** no 4:5 asset is produced for the article

#### Scenario: No hero is declared
- **WHEN** the entry's `ASSET_TYPES` is blank
- **THEN** the requested hero is `svg_wide`
- **AND** no image-model call is made

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

### Requirement: The published commit carries the requested asset set

The commit SHALL carry the assets the entry asked for and the figure slots its approved draft carries, and no others. An asset row whose type is not in that set — a leftover from an earlier request, a retired figure slot, or a row written by hand — SHALL NOT be committed, and the run SHALL report the types it left out rather than dropping them silently. The requested set SHALL be derived once and read by every consumer, so the set the draft is written for, the set the publish gate checks and the set the commit carries cannot disagree. The k-th figure marker SHALL become the `figure_<k>` reference at that position, with the section heading as alt text.

#### Scenario: A leftover asset row is not committed

- **WHEN** the entry holds an approved asset row for a type it no longer requests
- **THEN** that row is not among the committed files
- **AND** the run names the type it left out

#### Scenario: The requested set has one definition

- **WHEN** any node needs the entry's requested asset types or figure slots
- **THEN** it reads the set the plan derivation produced
- **AND** no second derivation exists to drift from it

#### Scenario: A requested asset is still committed

- **WHEN** every requested type and figure slot has an approved row
- **THEN** each of them is committed at its own marker, with the article, in one commit

#### Scenario: A figure marker and its row disagree

- **WHEN** a figure marker has no row or a figure row has no marker
- **THEN** the run fails loudly before committing
- **AND** nothing is committed
