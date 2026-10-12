# Spec Delta

## MODIFIED Requirements

### Requirement: Hooks are declared in one registry

The system SHALL define its post hooks in a single declarative registry, and each
hook MUST declare when it is eligible, the opening shape it gives the post and a
default visual intent (`form`, `scenes`). Every consumer of a hook — the classifier, the post generator and the
media selector — SHALL read that one registry, and MUST NOT carry its own copy of
the hook list. Adding or changing a hook MUST be a registry change, not a change
to a workflow.

#### Scenario: One list, many readers

- **WHEN** the hook list is needed by the classifier, the generator or the media selector
- **THEN** each reads the registry
- **AND** no consumer holds a second copy of the ids

#### Scenario: A hook id appears once

- **WHEN** a hook id is declared
- **THEN** it appears in the registry and nowhere else as a list

## REMOVED Requirements

### Requirement: A hook declares a default visual intent

**Reason**: The requirement made whether a hook wants motion a per-hook declaration
that the classification could override, so a still image was a classification outcome.
The media is now animated for every hook and the still image is only the fallback when
the animated asset cannot be produced, so the motion flag is dead data. The
form-and-scene half of the requirement is re-issued as "A hook's visual intent declares
a form and a scene count".

**Migration**: `motion` is removed from every hook's `visual` in
`datasets/hook_types.json` and from the judge's `visual` contract; no consumer reads it.

## ADDED Requirements

### Requirement: A hook's visual intent declares a form and a scene count

Each hook SHALL declare a default visual form (one the authoring system accepts)
and a scene count where its shape is a sequence. The visual intent SHALL NOT carry a
motion flag: the post's media is animated for every hook. The classification MAY
override the default form or the scene count when the content warrants it, and an
override MUST be carried with the hook rather than recomputed.

#### Scenario: A sequence hook declares a scene count

- **WHEN** an article is classified with a list-shaped hook
- **THEN** its default visual intent carries a scene count
- **AND** the scene count reflects the number of items the article presents

#### Scenario: A hook carries no motion flag

- **WHEN** a hook's default visual intent is declared
- **THEN** it declares a form and a scene count
- **AND** it declares no motion flag

#### Scenario: An override travels with the hook

- **WHEN** the classification overrides a hook's default form for a given article
- **THEN** the overridden value is the one the media selector receives
