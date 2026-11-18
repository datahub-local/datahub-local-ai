# Spec Delta

## ADDED Requirements

### Requirement: The article's evidence reaches the visual brief

The brief a visual is authored from SHALL carry the article's evidence — the concrete
detail the classification named, read from the row's evidence column — beside the post
text, for the animated branch and the still fallback alike, so the visual anchors the
article's fact rather than only the post's framing. No new queue columns are introduced,
and no judge-written direction reaches any consumer: the position a post argues is the
writer's own, taken from the article text.

#### Scenario: The animated branch names the detail

- **WHEN** an animated asset is authored for a row whose evidence cell is set
- **THEN** the composer's brief contains that evidence

#### Scenario: The still director names the detail

- **WHEN** the still fallback runs for a row whose evidence cell is set
- **THEN** the image director's prompt contains that evidence

#### Scenario: A row without evidence degrades

- **WHEN** a row's evidence cell is blank
- **THEN** the visual briefs are built exactly as they were before the passthrough

### Requirement: The post retry form offers named directives

The post retry form SHALL offer a fixed set of directives (structure or order, focus,
tone, concision, depth) beside its free-text feedback, and the chosen directive SHALL be
carried into the feedback the drafting retry reads, verbatim and ahead of the free text.

#### Scenario: A directive reaches the drafter

- **WHEN** the reviewer picks a directive and adds no free text
- **THEN** the retry's feedback block contains the directive's wording

## MODIFIED Requirements

### Requirement: The queue carries the classified hook and visual intent

The queue SHALL carry, per article, the hook and the visual intent — the form and any
scene count — as fields of the row, written when the drafting turn's classification is
parsed, so every later consumer reads them without recovering them from prose. At
admission the cells are blank: the admission gate selects (postability, blocked,
evidence), and the classification is the writer's own choice at drafting. The media kind
SHALL NOT be part of the classified intent: an admitted row's media is animated, and a
still image is only the fallback when the animated asset cannot be produced.

#### Scenario: Hook is a field

- **WHEN** the drafting turn chooses a hook for a row
- **THEN** the chosen hook is stored as a field of the row
- **AND** a reader gets it without parsing a prompt string

#### Scenario: Intent is a field

- **WHEN** the chosen hook's registry defaults carry a form and a scene count
- **THEN** they are stored on the row with the hook
- **AND** no motion flag is stored or read

#### Scenario: Admission does not classify

- **WHEN** an article is admitted to the queue
- **THEN** its hook and visual cells are blank
- **AND** the admission decision recorded is postability, blocked and evidence

## REMOVED Requirements

### Requirement: A queued row without a classified hook is re-judged

A queued row that carries no hook SHALL be re-classified from its article by the curator,
a bounded number per run, and its hook and visual intent SHALL be written to the row. A
row whose re-judge verdict cannot be read MUST be left unclassified, so a later run retries
it rather than recording a guess.

#### Scenario: A pre-column row is backfilled

- **WHEN** a queued row carries no hook
- **THEN** the curator re-judges it and writes its hook and visual intent
- **AND** an unreadable verdict leaves the row unclassified

