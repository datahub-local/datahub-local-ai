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
visual intent that came with it — the form and any scene count — as fields of the row.
The media kind SHALL NOT be part of the classified intent: an admitted row's media is
animated, and a still image is only the fallback when the animated asset cannot be
produced. A later reader MUST NOT recover the hook from prose the generator was given.

#### Scenario: Hook is a field

- **WHEN** an article is admitted to the queue
- **THEN** its hook is stored as a field of the row
- **AND** a reader gets it without parsing a prompt string

#### Scenario: Intent is a field

- **WHEN** an article is admitted to the queue
- **THEN** its visual form and any scene count are stored on the row
- **AND** no motion flag is stored or read

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

### Requirement: A post's media is animated unless a row overrides it

An admitted row's media SHALL be animated: the curator SHALL write the media field as
animated for every row it admits and for every row it backfills, and a classification
MUST NOT select a still. The forced visual form and any scene count SHALL be selected
from the row's intent, so a human cell is not the default decision. A manually declared
media value on a row SHALL override the animated default, so a hand-set row keeps its
behaviour, and a still image SHALL be the fallback when the animated asset cannot be
produced.

#### Scenario: An admitted row is animated

- **WHEN** a row is admitted to the queue
- **THEN** its media field is animated
- **AND** the animated type is requested with the row's forced form

#### Scenario: A manual override still wins

- **WHEN** a row carries a manually declared media value
- **THEN** it overrides the animated default

#### Scenario: A failed animation falls back to a still

- **WHEN** the animated asset cannot be produced for a row
- **THEN** the still-image path is used
- **AND** the post is not blocked

### Requirement: A rejected post is carried into the retry

A rejected post SHALL be passed back to the drafting pass that regenerates it, so the retry edits
the post the review just rejected rather than writing a new one from nothing. The retry SHALL carry
the most recent attempt's post and not an earlier one, and SHALL render an empty block on the first
attempt.

#### Scenario: The retry edits the rejected post

- **WHEN** the review rejects a post and the drafting prompt is rendered again
- **THEN** the prompt carries the post that was just rejected
- **AND** the drafting rules ask for that post to be edited rather than replaced

#### Scenario: A third attempt edits the second post

- **WHEN** a run reaches a second retry
- **THEN** the prompt carries the most recent rejected post
- **AND** it does not carry the first attempt's post

#### Scenario: The first attempt carries no post

- **WHEN** the drafting prompt is rendered for the first attempt
- **THEN** the previous-post block is empty
- **AND** the drafting rules are not told to edit a post that does not exist

### Requirement: A human retry is handed the post the human rejected

When a person asks for changes to a post they read, the drafting pass that regenerates it SHALL
receive the post they were reading, so the change is an edit rather than a new post. The post SHALL
be the one that was on screen when the feedback was written and not an earlier round's, the first
pass SHALL send none, and the pass SHALL prefer a post rejected inside the same invocation over the
caller's. The post lane stores no draft of its own, so the post SHALL travel in the run.

#### Scenario: A human asks for a change to the post

- **WHEN** a person answers the approval with feedback and the graph re-enters the drafting
  sub-workflow
- **THEN** the drafting prompt carries the post they were reading
- **AND** the parts of it the feedback does not name are kept

#### Scenario: A third round edits the second post

- **WHEN** a post is sent for review a second time and rejected again
- **THEN** the drafting prompt carries the most recently reviewed post
- **AND** it does not carry the first round's post

#### Scenario: The first authoring sends nothing

- **WHEN** the drafting sub-workflow is called for the first time in a run
- **THEN** no previous post is passed
- **AND** the prompt's previous-post block is empty
