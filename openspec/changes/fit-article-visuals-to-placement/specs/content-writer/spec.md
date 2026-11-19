# Spec Delta

## ADDED Requirements

### Requirement: Every article asset declares the placement it fills

The asset plan SHALL carry each article asset's placement — the lead, or an inline figure
with the section it sits in — and the brief and the committed page SHALL read that field
rather than re-derive placement from the asset's type name. The committed page SHALL render
the lead at the page's text width after the opening, and each figure inside the text
column at its inline width with its section heading as alt text.

#### Scenario: A figure lands inline

- **WHEN** a draft carries a figure marker after a section
- **THEN** the plan carries that section as the figure's placement
- **AND** the committed page places the figure inside the text column, not at the lead's width

#### Scenario: The placement is one derivation

- **WHEN** the commit assembles the page
- **THEN** it reads the plan's placement field
- **AND** no consumer derives placement from the type name a second time

### Requirement: A figure is its section's mechanics, never a second thesis

The figure's brief SHALL carry the section it sits in and SHALL state that the page's lead
image already carries the article's thesis — the figure shows the section's own flow, step
or comparison row. Where a section restates the thesis, the writer SHALL place no figure
there.

#### Scenario: The lead and the figure do not restate each other

- **WHEN** an article carries both a lead and a figure
- **THEN** the figure's brief is its section, with the thesis excluded
- **AND** the two visuals illustrate different ideas

#### Scenario: A thesis-restating section gets no figure

- **WHEN** a section's job is to restate the article's thesis
- **THEN** the writer places no figure after it
- **AND** the page publishes with the lead alone

### Requirement: One moving asset per page

The lead SHALL be the page's only animated asset; inline figures SHALL be still.

#### Scenario: Figures are still

- **WHEN** a page carries a lead and one or more figures
- **THEN** the lead is the only moving asset
- **AND** every figure is a still image

### Requirement: Every requested asset commits to its own path in one commit

The publish chain SHALL carry every requested asset through to the commit — N assets in,
N blobs, N committed files — and the tree step SHALL assert the blob count against the
asset count so a collapse fails loudly instead of committing one file for two assets.

#### Scenario: Two assets, one commit

- **WHEN** an article's plan carries a lead and a figure
- **THEN** the commit creates one blob per asset
- **AND** both files are referenced in the committed post

#### Scenario: A collapsed chain fails loudly

- **WHEN** the tree step receives fewer blobs than assets
- **THEN** the run fails naming both counts
- **AND** nothing is committed
