# Spec Delta

## ADDED Requirements

### Requirement: An imported row names its audience

An imported row SHALL carry the article lane's audience level — one of `NONE`, `LOW`, `MEDIUM`
or `ADVANCED` — taking the configured default when the board issue says nothing about it,
because a board issue is a title and a body and nothing else. The intake SHALL NOT judge or
infer the level: no model is consulted, and the row's level is the configured default until a
person changes it on the sheet. A person SHALL be able to change the level on the row after
import and before the lane picks it up.

The default SHALL be one of the levels the article lane accepts, and the level ids SHALL agree
between the intake's configured default, the article lane's validation and the lane's committed
audience definitions, so one value changes all three or none.

#### Scenario: An imported row carries the audience default

- **WHEN** a labelled issue is appended as an article row
- **THEN** the row carries the configured audience level
- **AND** no model was consulted to choose it

#### Scenario: The default is a level the lane accepts

- **WHEN** a row is imported with the default audience level
- **THEN** that level is one the article lane's definitions describe
- **AND** the lane does not refuse the row for its audience

#### Scenario: A person sets the level before the lane picks it up

- **WHEN** the audience cell of an imported row is edited on the sheet
- **THEN** the lane drafts for the edited level
- **AND** the intake does not overwrite it on a later run, whatever the issue's status
