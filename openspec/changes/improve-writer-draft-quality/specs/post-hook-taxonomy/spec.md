# Spec Delta

## ADDED Requirements

### Requirement: A release hook states the change

The registry's release-shaped hooks (`RELEASE`, `NEWS_REACTION`) SHALL declare openings
that name the headline change — what is new, spelled as the article states it — in the
post's first lines, before the take.

#### Scenario: A release post opens on the news

- **WHEN** a row hooked `RELEASE` or `NEWS_REACTION` is drafted
- **THEN** the opening lines state what changed before any judgment on it

## MODIFIED Requirements

### Requirement: One article is classified once

An article SHALL be classified by a single pass that reads it, and that pass is the
writer's own drafting turn: it SHALL return the article's hook and the post together,
choosing exactly one hook whose eligibility the article satisfies. The hook that shapes
the generated post MUST be the one that turn returned, together with the registry's
visual defaults for it; no other step SHALL re-derive or reassign it. A row whose hook a
human already set keeps that hook — the writer writes to the assigned shape and does not
re-choose.

#### Scenario: The classified hook is the post's hook

- **WHEN** a post is generated for an article no one classified
- **THEN** its opening follows the hook the drafting turn chose
- **AND** the same hook is not chosen again downstream

#### Scenario: Visual intent comes from the same pass

- **WHEN** the article's media is selected
- **THEN** the intent used is the one returned with the hook
- **AND** it is not inferred from a coarser signal

#### Scenario: A retry does not re-choose

- **WHEN** the same article is drafted again in its session
- **THEN** the hook the session stored is the one the retry writes to

#### Scenario: A human-set hook is honoured

- **WHEN** a row carries a hook a person set
- **THEN** the drafting turn writes to that hook
- **AND** no new hook is chosen or answered
