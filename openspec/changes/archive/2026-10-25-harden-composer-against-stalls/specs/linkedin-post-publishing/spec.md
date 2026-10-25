# Spec Delta

## MODIFIED Requirements

### Requirement: A post's media is animated unless a row overrides it

An admitted row's media SHALL be animated: the curator SHALL write the media field as
animated for every row it admits and for every row it backfills, and a classification
MUST NOT select a still. The forced visual form and any scene count SHALL be selected
from the row's intent, so a human cell is not the default decision. A manually declared
media value on a row SHALL override the animated default, so a hand-set row keeps its
behaviour, and a still image SHALL be the fallback when the animated asset cannot be
produced. A failed animated asset SHALL be reported to the reviewer with the reason it
failed, and the reviewer MAY ask for it to be re-authored. That ask SHALL be bounded in
time, and a report that is not answered within its bound SHALL take the still fallback, so
an unanswered failure MUST NOT hold the post.

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

#### Scenario: The reviewer may ask for the failed animation again

- **WHEN** the animated asset could not be produced for a row
- **THEN** the report names the reason it failed and offers a re-author
- **AND** a re-author request produces the asset for the same article

#### Scenario: An unanswered report takes the still

- **WHEN** the failure report is not answered within its bound
- **THEN** the still-image path is used
- **AND** the post is not held by the unanswered report

## ADDED Requirements

### Requirement: A failed animated asset is re-authored under its own reason and session

A re-author of a failed animated asset SHALL carry the asset's own failure reason as the
feedback of the request, and SHALL use the same session identifier the first request used,
so the composer continues one thread rather than starting another. The branch that
re-authors a failed asset SHALL be reachable only through the bounded failure report, so no
path re-authors an asset without an answer, and every path from that branch SHALL return to
the same result check.

#### Scenario: The failure reason reaches the next turn

- **WHEN** a failed animated asset is re-authored
- **THEN** the request carries the asset's recorded failure reason as its feedback
- **AND** the next attempt is authored against that reason

#### Scenario: One session across the failure

- **WHEN** a failed animated asset is re-authored for the same article
- **THEN** the request carries the same session identifier as the failed attempt

#### Scenario: No unattended re-author

- **WHEN** the animated asset fails and the failure report is never answered
- **THEN** no re-author is requested
- **AND** the still-image path is taken

#### Scenario: A retry is checked like the first attempt

- **WHEN** a failed animated asset is re-authored
- **THEN** its result passes the same result check the first attempt did
- **AND** the still-image path remains available to it
