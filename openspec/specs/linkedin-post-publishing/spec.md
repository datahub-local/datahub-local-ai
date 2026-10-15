# linkedin-post-publishing Specification

## Purpose
The scheduled pipeline that turns a queued source article into a published LinkedIn post, and specifically the internal review gate that decides whether a generated draft may go on to human review: which rules it may reject on, how a rejected draft is regenerated, how many attempts it is given, and how a gate failure is recorded and reported.

## Requirements

### Requirement: Every rejection reason is a rule a compliant draft can satisfy

The gate's compliance rules and the drafting rules SHALL be jointly satisfiable for every source. A rule MUST NOT reject a draft for using a word that another rule requires the draft to contain. In particular, the AI-speak rule SHALL apply to a listed word in its hype usage, and MUST NOT reject a draft that uses the word as the name of the technology, component or product the draft is about.

#### Scenario: Listed word is the subject of the draft

- **WHEN** the source content is about a component the drafting rules require the draft to name, and that component's name is on the AI-speak list
- **THEN** the gate does not reject the draft on the AI-speak rule
- **AND** the draft proceeds to the remaining checks

#### Scenario: Listed word is used as hype

- **WHEN** a draft uses a listed word as filler or hype rather than as the name of its subject
- **THEN** the gate rejects the draft on the AI-speak rule
- **AND** its explanation names the word

### Requirement: A rejected draft is regenerated from the rejection reason

When the gate rejects a draft, the next attempt SHALL be produced from a prompt that includes the gate's explanation of that rejection, and MUST NOT be a resampling of the unchanged prompt. The first attempt for an entry carries no gate explanation.

#### Scenario: Second attempt applies the rejection reason

- **WHEN** the gate rejects a draft with an explanation
- **THEN** the next attempt's instructions include that explanation
- **AND** the next attempt is submitted to the gate again

#### Scenario: First attempt

- **WHEN** no draft has been submitted yet for the entry
- **THEN** the drafting instructions carry author-supplied feedback only

#### Scenario: Author feedback and gate feedback are both present

- **WHEN** a submission carries human feedback for the entry and the gate has rejected a previous attempt
- **THEN** the next attempt's instructions carry both, and the human feedback keeps its precedence

#### Scenario: Rejected for a reason the explanation cannot fix

- **WHEN** every attempt is rejected for the same reason
- **THEN** the pipeline stops on the attempt bound rather than repeating attempts indefinitely

### Requirement: The attempt bound counts drafts

The pipeline SHALL produce at most `MAX_TRIES` drafts for one entry, where `MAX_TRIES` is the configured maximum number of drafts. A rejected final attempt SHALL end the run as a gate failure without producing a further draft.

#### Scenario: Bound reached

- **WHEN** the gate rejects the `MAX_TRIES`-th draft
- **THEN** no further draft is produced
- **AND** the run ends as a gate failure

#### Scenario: Accepted before the bound

- **WHEN** the gate accepts a draft before the bound is reached
- **THEN** no further draft is produced
- **AND** the accepted draft is returned as the run's result

#### Scenario: Review disabled for a call

- **WHEN** the caller disables the internal review
- **THEN** the first draft is returned without any gate call

### Requirement: A gate failure names its reason and reaches a human

A run that ends without an accepted draft SHALL publish nothing, SHALL record an error state on the queue row carrying the gate's reason for the final rejection, and SHALL send a notification that names both the article and that reason. A generic marker that discards the reason MUST NOT be recorded or reported in place of it.

#### Scenario: Gate failure is recorded

- **WHEN** the run ends as a gate failure
- **THEN** the queue row's state is an error state
- **AND** the recorded reason identifies the failure and carries the gate's explanation for the final rejection

#### Scenario: Gate failure is reported

- **WHEN** the run ends as a gate failure
- **THEN** a notification is delivered naming the article the run was working on and the reason
- **AND** no post is published

#### Scenario: Nothing is published on any failed run

- **WHEN** any step of the run fails
- **THEN** no post is published to LinkedIn
- **AND** the failure reaches a human

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

### Requirement: A queued row without a classified hook is re-judged

A queued row that carries no hook SHALL be re-classified from its article by the curator,
a bounded number per run, and its hook and visual intent SHALL be written to the row. A
row whose re-judge verdict cannot be read MUST be left unclassified, so a later run retries
it rather than recording a guess.

#### Scenario: A pre-column row is backfilled

- **WHEN** a queued row carries no hook
- **THEN** its article is re-classified
- **AND** the row's hook and visual intent are written to it

#### Scenario: An unreadable verdict is not recorded

- **WHEN** the re-judge verdict cannot be parsed
- **THEN** the row is left unclassified
- **AND** a later run retries it

### Requirement: A rejected animated asset continues its authoring session

The animated media branch SHALL request its asset under a session identifier derived
from the article it is publishing, so the first authoring and any later retry share
one session and a retry edits the composition the rejection named rather than
authoring a new one. The identifier SHALL NOT depend on the run that produced the
asset.

#### Scenario: A retry edits the rejected asset

- **WHEN** an animated asset is rejected and re-requested for the same article
- **THEN** the request carries the same session identifier as the first
- **AND** the composer continues from the composition it already produced

#### Scenario: The identifier does not depend on the run

- **WHEN** the animated asset is requested more than once for one article
- **THEN** the session identifier is the same each time

### Requirement: A video asset is published as a video post

When the media attached to a post is a video, the system SHALL publish it as a video
post, and when the media is an image or an animated image it SHALL publish it as an
image post. A single decision point SHALL choose the path from the asset's own media
type rather than from the requested type name. The node path handles images and
animated images; a video SHALL be uploaded through the LinkedIn API directly, because
the installed LinkedIn node supports only image and article posts. There SHALL be no
path that publishes by guessing the media type. The video upload path is
**[UNVERIFIED]** against LinkedIn — it is recorded as designed and has not been
exercised by a live public publish.

#### Scenario: A video asset publishes as video
- **WHEN** the approved asset's content type is `video/mp4`
- **THEN** the post is published with a video
- **AND** the asset is uploaded through the LinkedIn API video path

#### Scenario: An image asset still publishes as image
- **WHEN** the approved asset's content type is `image/gif` or `image/png`
- **THEN** the post is published with that image through the node
- **AND** the existing image path is unchanged

#### Scenario: The decision is the asset's media type
- **WHEN** the publish path is chosen
- **THEN** it is chosen from the asset's content type
- **AND** not from the requested type name

#### Scenario: The reviewer sees the video before approval
- **WHEN** a video asset is waiting for approval
- **THEN** it is uploaded for review before the approval decision
- **AND** the approval notice names the run and the media type

### Requirement: An approved asset is read from where the run stored it

The publish path SHALL read an approved asset's bytes from the object the run named, and
MUST NOT depend on the response carrying them. It SHALL obtain a short-lived signed URL
from the service that holds the bucket credential, so the workflow needs no bucket
credential of its own.

#### Scenario: An animated asset is fetched for publishing

- **WHEN** an approved animated asset is published
- **THEN** a signed URL is obtained for the key the run returned
- **AND** the bytes are fetched from it as binary for the upload
- **AND** no data URL is decoded anywhere in the path

#### Scenario: The media type is the asset's own

- **WHEN** the publish path chooses between the video and image paths
- **THEN** it reads the media type the run recorded for the asset
- **AND** it does not read it from the node that downloaded the bytes, which carries no
  JSON of its own

#### Scenario: A missing object fails the publish

- **WHEN** the named object cannot be read
- **THEN** the publish fails with that reason
- **AND** it does not publish an empty or substituted media item
