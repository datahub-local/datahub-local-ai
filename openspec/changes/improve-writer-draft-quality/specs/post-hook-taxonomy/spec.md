# Spec Delta

## ADDED Requirements

### Requirement: A release hook states the change

The registry's release-shaped hooks (`RELEASE`, `NEWS_REACTION`) SHALL declare openings
that name the headline change — what is new, spelled as the article states it — in the
post's first lines, before the take. The classification's angle rule SHALL permit a
release's headline change as the angle's subject, so the direction the writer opens from
may be the change itself.

#### Scenario: A release post opens on the news

- **WHEN** a row hooked `RELEASE` or `NEWS_REACTION` is drafted
- **THEN** the opening lines state what changed before any judgment on it

#### Scenario: The angle may be the change

- **WHEN** the classification reads a release announcement
- **THEN** the returned angle may name the headline change and the test to watch
- **AND** it is not rejected for restating a fact of the article
