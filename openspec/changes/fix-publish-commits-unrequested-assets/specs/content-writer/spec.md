# Spec Delta

## ADDED Requirements

### Requirement: The published commit carries the requested asset set

The commit SHALL carry the assets the entry asked for and no others. An asset row whose type is not
in the entry's requested set — a leftover from an earlier request, or a row written by hand — SHALL
NOT be committed, and the run SHALL report the types it left out rather than dropping them
silently. The requested set SHALL be derived once and read by every consumer, so the set the draft
is written for, the set the publish gate checks and the set the commit carries cannot disagree.

#### Scenario: A leftover asset row is not committed

- **WHEN** the entry holds an approved asset row for a type it no longer requests
- **THEN** that row is not among the committed files
- **AND** the run names the type it left out

#### Scenario: The requested set has one definition

- **WHEN** any node needs the entry's requested asset types
- **THEN** it reads the set the selector derived
- **AND** no second derivation of the hero rule exists to drift from it

#### Scenario: A requested asset is still committed

- **WHEN** every requested type has an approved row
- **THEN** each of them is committed at its own marker, with the article, in one commit
