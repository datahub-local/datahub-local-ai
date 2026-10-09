# Spec Delta

## ADDED Requirements

### Requirement: Hooks are declared in one registry

The system SHALL define its post hooks in a single declarative registry, and each
hook MUST declare when it is eligible, the opening shape it gives the post and a
default visual intent (`form`, `motion`, `scenes`). Every consumer of a hook — the classifier, the post generator and the
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

### Requirement: One article is classified once

An article SHALL be classified by a single pass that reads it, and that pass SHALL
return the article's hook and its visual intent together. The hook that shapes the
generated post MUST be the one that pass returned; a later step MUST NOT re-derive
or randomly reassign it.

#### Scenario: The classified hook is the post's hook

- **WHEN** a post is generated for a classified article
- **THEN** its opening follows the hook the classification returned
- **AND** the same hook is not chosen again downstream

#### Scenario: Visual intent comes from the same pass

- **WHEN** the article's media is selected
- **THEN** the intent used is the one returned with the hook
- **AND** it is not inferred from a coarser signal

### Requirement: A hook declares a default visual intent

Each hook SHALL declare a default visual form (one the authoring system accepts),
whether it wants motion, and a scene count where its shape is a sequence. The
classification MAY override the default when the content warrants it, and an
override MUST be carried with the hook rather than recomputed.

#### Scenario: A sequence hook defaults to motion

- **WHEN** an article is classified with a list-shaped hook
- **THEN** its default visual intent declares motion
- **AND** its scene count reflects the number of items the article presents

#### Scenario: An override travels with the hook

- **WHEN** the classification overrides a hook's default form for a given article
- **THEN** the overridden value is the one the media selector receives

### Requirement: A list-shaped article renders as a sequence

A list-shaped hook (a roundup, a state-of, a landscape) SHALL be rendered as a
multi-scene visual, one item per scene, using an existing animation type rather
than a new media kind.

#### Scenario: One item per scene

- **WHEN** a list-shaped article is rendered
- **THEN** the visual carries one item per scene
- **AND** the item count is the scene count the classification declared
