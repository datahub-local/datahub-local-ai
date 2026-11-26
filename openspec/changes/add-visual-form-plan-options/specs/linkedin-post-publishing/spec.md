# Spec Delta

## ADDED Requirements

### Requirement: The writer's form is a hint, not the decision

The post writer's form answer SHALL be passed to the visual studio as a suggestion. It
SHALL NOT be written back to the row as a force, and it SHALL NOT decide the studio's form.
A non-empty `VISUAL_FORM` on the row SHALL be read as a human pin and SHALL win.

#### Scenario: A writer-only form is not a pin
- **WHEN** the writer answers `story` and the row carries no human form
- **THEN** the studio's form stage runs with `story` as one suggestion
- **AND** a later run does not read the previous run's answer as a human pin

#### Scenario: A human pins a form
- **WHEN** a person writes `story` into the row's `VISUAL_FORM`
- **THEN** the form stage is skipped and `story` is used

### Requirement: An animated post requests the video type

For `POST_MEDIA=ANIMATED` the post lane SHALL request `animation_linkedin_video` (30 s,
4:5) rather than map the form to the 6-second `poster_gif`. `poster_gif` SHALL remain a
supported type for an explicit poster request.

#### Scenario: A news reaction with features
- **WHEN** a news-reaction post is approved for animated media
- **THEN** the studio is asked for the 30-second video, and the form stage decides among
  the forms that fit the announcement

#### Scenario: A one-claim poster is wanted
- **WHEN** a caller explicitly requests `poster_gif`
- **THEN** the 6-second poster remains available and its declared `poster` form is used
