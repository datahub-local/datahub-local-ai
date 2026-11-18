# Spec Delta

## ADDED Requirements

### Requirement: The article's evidence reaches the visual brief

The brief a visual is authored from SHALL carry the article's evidence — the concrete
detail the classification named — beside the post text, for the animated branch and the
still fallback alike, so the visual anchors the article's fact rather than only the
post's framing.

#### Scenario: The animated branch names the detail

- **WHEN** an animated asset is authored for a row that carries evidence
- **THEN** the composer's brief contains that evidence

#### Scenario: The still director names the detail

- **WHEN** the still fallback runs for a row that carries evidence
- **THEN** the image director's prompt contains that evidence

#### Scenario: A row without evidence degrades

- **WHEN** a row's evidence cell is blank
- **THEN** the visual briefs are built exactly as they were before the field existed

### Requirement: The post retry form offers named directives

The post retry form SHALL offer a fixed set of directives (structure or order, focus,
tone, concision, depth) beside its free-text feedback, and the chosen directive SHALL be
carried into the feedback the drafting retry reads, verbatim and ahead of the free text.

#### Scenario: A directive reaches the drafter

- **WHEN** the reviewer picks a directive and adds no free text
- **THEN** the retry's feedback block contains the directive's wording

## MODIFIED Requirements

### Requirement: The queue carries the classified hook and visual intent

The queue SHALL carry, per article, the hook the classification returned and the visual
intent that came with it — the form and any scene count — as fields of the row, and SHALL
carry the classification's angle and evidence as fields of the row too. The media kind
SHALL NOT be part of the classified intent: an admitted row's media is animated, and a
still image is only the fallback when the animated asset cannot be produced. A later
reader MUST NOT recover the hook, the angle or the evidence from prose the generator was
given.

#### Scenario: Hook is a field

- **WHEN** an article is admitted to the queue
- **THEN** its hook is stored as a field of the row
- **AND** a reader gets it without parsing a prompt string

#### Scenario: Intent is a field

- **WHEN** an article is admitted to the queue
- **THEN** its visual form and any scene count are stored on the row
- **AND** no motion flag is stored or read

#### Scenario: The angle and evidence are fields

- **WHEN** an article is admitted to the queue
- **THEN** the classification's angle and evidence are stored on the row
- **AND** a blank cell degrades to the behaviour the lane had before

### Requirement: The generated post follows the row's hook

The post generator SHALL open the post on the hook the row carries, and MUST NOT randomly
reassign a hook. The generator's brief SHALL also carry the row's angle, the direction the
classification chose, so the first lines argue the judged direction. Other aspects of the
post's shape (format, length, closing) MAY still vary between posts.

#### Scenario: The row's hook is used

- **WHEN** a queued article is drafted
- **THEN** the draft's opening follows the row's hook
- **AND** the brief the drafter reads contains the row's angle

#### Scenario: Two drafts of one article share the hook

- **WHEN** the same article is drafted twice
- **THEN** both drafts use the row's hook
