# Spec Delta

## ADDED Requirements

### Requirement: The queue carries the classified hook and visual intent

The queue SHALL carry, per article, the hook the classification returned and the
visual intent that came with it — the form, whether motion is wanted and any scene
count — as fields of the row. A later reader MUST NOT recover the hook from prose
the generator was given.

#### Scenario: Hook is a field

- **WHEN** an article is admitted to the queue
- **THEN** its hook is stored as a field of the row
- **AND** a reader gets it without parsing a prompt string

#### Scenario: Intent is a field

- **WHEN** an article is admitted to the queue
- **THEN** its visual form and whether it is animated are stored on the row

### Requirement: The generated post follows the row's hook

The post generator SHALL open the post on the hook the row carries, and MUST NOT
randomly reassign a hook. Other aspects of the post's shape (format, length,
closing) MAY still vary between posts.

#### Scenario: The row's hook is used

- **WHEN** a queued article is drafted
- **THEN** the draft's opening follows the row's hook

#### Scenario: Two drafts of one article share the hook

- **WHEN** the same article is drafted twice
- **THEN** both drafts use the row's hook

### Requirement: The post's media is selected from the row's intent

The post's media kind and its forced visual form SHALL be selected from the row's
visual intent, so a human cell is not the default decision. A manually declared
media value on a row SHALL override the intent, so a hand-set row keeps its
behaviour.

#### Scenario: Intent selects the media

- **WHEN** a row declares motion and a visual form
- **THEN** the animated type is requested with that form forced

#### Scenario: A static intent does not request animation

- **WHEN** a row declares no motion
- **THEN** the still-image path is used

#### Scenario: A manual override still wins

- **WHEN** a row carries a manually declared media value
- **THEN** it overrides the row's intent
