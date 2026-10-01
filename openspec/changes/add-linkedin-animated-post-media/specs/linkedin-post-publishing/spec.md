# Spec Delta

## Purpose

The scheduled pipeline that turns a queued source into a published LinkedIn post: which queued post is chosen, how its text and media are drafted and approved in Slack, how a rejected artifact is retried with feedback, and what the queued row records when the post is published, cancelled or fails.

## ADDED Requirements

### Requirement: A post's media is chosen per queued row

The pipeline SHALL read the media kind for each post from the queued row. A blank or `STATIC` value SHALL select the still-image media the pipeline already produces, and `ANIMATED` SHALL select a studio-rendered animated infographic. A row that does not opt in MUST NOT have its media changed by this capability.

#### Scenario: Blank keeps the still image
- **WHEN** a queued row carries no media value, or `STATIC`
- **THEN** the post is published with the still image, exactly as before this capability
- **AND** no animated asset is produced for it

#### Scenario: Animated media is opt-in
- **WHEN** a queued row carries `ANIMATED`
- **THEN** the run produces an animated infographic for that post

### Requirement: Animated media is produced by the Visual Studio workflow

When a row selects animated media, the pipeline SHALL obtain it by invoking the Visual Studio workflow as a sub-workflow, passing the post text as its content and requesting the animated type declared for this platform. The pipeline MUST NOT author markup, capture frames or assemble an animation itself.

#### Scenario: Animated media comes from the studio
- **WHEN** a run produces animated media for a post
- **THEN** the asset is the one the Visual Studio workflow returned
- **AND** the pipeline requested the type declared for this platform

#### Scenario: The pipeline authors no markup
- **WHEN** animated media is produced
- **THEN** no node of the pipeline generates or edits the asset's markup or frames

### Requirement: The animation stays inside the platform's GIF limits

A published animated asset SHALL be an animated GIF. Its frame count MUST NOT exceed 500 and its total pixel count MUST NOT exceed 36,152,320, the platform's documented GIF limit, and its duration SHALL match the duration declared for the asset.

#### Scenario: The declared budget stays inside the cap
- **WHEN** the animated type declared for this platform is produced
- **THEN** the result is an animated GIF of at most 500 frames
- **AND** its frame count multiplied by its frame dimensions does not exceed 36,152,320 pixels
- **AND** its total duration matches the value declared for the asset

### Requirement: The animation is approved before it is published

The pipeline SHALL present the produced animation for the same double approval the still image receives, including the animation itself so the reviewer can see the motion. When the reviewer rejects it, the pipeline SHALL re-author the animation with the reviewer's feedback and present the result again. A cancel at that gate SHALL end the run for that row without publishing and without generating the still image.

#### Scenario: A rejected animation is re-authored with feedback
- **WHEN** the reviewer rejects the animation and submits feedback
- **THEN** the animation is produced again with that feedback
- **AND** the new result is presented for approval in the same way

#### Scenario: Cancel publishes nothing
- **WHEN** the reviewer cancels at the animation gate
- **THEN** no post is published for that row
- **AND** no still image is generated as a substitute

### Requirement: An animation that cannot be produced does not block the post

When the animation is reported unavailable or fails to render, the pipeline SHALL continue with the still-image media for that post and SHALL state in the notification channel that the animated media was not used and why. It MUST NOT block or abandon the post because the animation could not be produced, and MUST NOT treat a run status of `PARTIAL` — which a requested-but-unavailable type produces — as a failure.

#### Scenario: Unavailable falls back to the still image
- **WHEN** the animation is reported unavailable or errors
- **THEN** the run continues into the still-image media path
- **AND** the post is published with a still image

#### Scenario: The fallback is announced
- **WHEN** the still image is used because the animation could not be produced
- **THEN** the notification channel says the animated media was not used and names the reason

### Requirement: A published post carries exactly one approved media item

The pipeline SHALL publish each post with exactly one media item: the approved animation when the row opted in and the animation was produced and approved, otherwise the approved still image. The media SHALL be published with the content type it was produced as.

#### Scenario: The animation is the media when approved
- **WHEN** the row opted into animated media and the reviewer approved the animation
- **THEN** the published post carries the animation
- **AND** no still image is attached alongside it

#### Scenario: The still image is the media otherwise
- **WHEN** the row did not opt in, or the animation could not be produced
- **THEN** the published post carries the approved still image
