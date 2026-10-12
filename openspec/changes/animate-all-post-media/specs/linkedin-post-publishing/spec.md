# Spec Delta

## MODIFIED Requirements

### Requirement: The queue carries the classified hook and visual intent

The queue SHALL carry, per article, the hook the classification returned and the
visual intent that came with it — the form and any scene count — as fields of the row.
The media kind SHALL NOT be part of the classified intent: an admitted row's media is
animated, and a still image is only the fallback when the animated asset cannot be
produced. A later reader MUST NOT recover the hook from prose the generator was given.

#### Scenario: Hook is a field

- **WHEN** an article is admitted to the queue
- **THEN** its hook is stored as a field of the row
- **AND** a reader gets it without parsing a prompt string

#### Scenario: Intent is a field

- **WHEN** an article is admitted to the queue
- **THEN** its visual form and any scene count are stored on the row
- **AND** no motion flag is stored or read

## REMOVED Requirements

### Requirement: The post's media is selected from the row's intent

**Reason**: The requirement let a classification outcome select a still, because the
row's intent carried whether motion was wanted and the media was chosen from it. The
media is now animated for every admitted row, so there is no motion intent to select
from. The selection of the forced form from the row, and the manual override, are
re-issued as "A post's media is animated unless a row overrides it".

**Migration**: The curator writes `POST_MEDIA=ANIMATED` for every row it admits or
backfills and carries no motion flag; `switch_post_media` still reads `POST_MEDIA`, so a
hand-edited `STATIC` cell keeps working.

## ADDED Requirements

### Requirement: A post's media is animated unless a row overrides it

An admitted row's media SHALL be animated: the curator SHALL write the media field as
animated for every row it admits and for every row it backfills, and a classification
MUST NOT select a still. The forced visual form and any scene count SHALL be selected
from the row's intent, so a human cell is not the default decision. A manually declared
media value on a row SHALL override the animated default, so a hand-set row keeps its
behaviour, and a still image SHALL be the fallback when the animated asset cannot be
produced.

#### Scenario: An admitted row is animated

- **WHEN** a row is admitted to the queue
- **THEN** its media field is animated
- **AND** the animated type is requested with the row's forced form

#### Scenario: A manual override still wins

- **WHEN** a row carries a manually declared media value
- **THEN** it overrides the animated default

#### Scenario: A failed animation falls back to a still

- **WHEN** the animated asset cannot be produced for a row
- **THEN** the still-image path is used
- **AND** the post is not blocked
