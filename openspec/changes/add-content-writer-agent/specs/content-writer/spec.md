# Spec Delta

## Purpose

Turns a queued topic (a topic, a description, an optional source link) into a published long-form article on the personal blog with a reviewed set of visual assets including a generated hero image, taking the article and every asset through a Slack review with feedback-driven retries before publishing, and keeping the queue row and the asset rows in step with the outcome.

## ADDED Requirements

### Requirement: Queue intake selects at most one actionable entry per trigger

The system SHALL read entries from a dedicated `article_queue` page of the `content_planner` sheet. Entries are authored outside this system and carry a topic, a description, an optional source link, and a stable entry identity. Entries selected for work are those whose state is actionable: a new entry not yet drafted, an entry with a rejected artifact awaiting regeneration, or an entry with the article and every requested asset approved awaiting publication. The system SHALL select at most one actionable entry per scheduled trigger, MUST NOT invent a topic, and MUST NOT process more than one entry per trigger.

#### Scenario: Entry authored outside the system
- **WHEN** an entry exists in `article_queue` with a topic and a description
- **THEN** it is eligible for the next trigger without any action inside this system

#### Scenario: One actionable entry selected
- **WHEN** the trigger fires and more than one entry is actionable
- **THEN** exactly one entry is selected

#### Scenario: Nothing actionable
- **WHEN** the trigger fires and no entry is actionable
- **THEN** the run ends without drafting
- **AND** no entry is created or modified

#### Scenario: Missing required input
- **WHEN** the selected entry has neither a topic nor a description
- **THEN** the run ends without drafting
- **AND** the entry is marked with an error state naming the missing input

### Requirement: Source link content is used when available

WHEN the selected entry carries a source link, the system SHALL retrieve the page and use its content as context for the article. WHEN the link is absent or retrieval fails, it SHALL continue from the topic and description and MUST record that the link content was not used.

#### Scenario: Link present and reachable
- **WHEN** the entry has a source link and the page can be fetched
- **THEN** the article reflects facts drawn from that page

#### Scenario: Link unreachable
- **WHEN** the entry has a source link but the page cannot be fetched
- **THEN** drafting continues from topic and description
- **AND** the outcome records that the link content was not used

### Requirement: Article draft is produced with its own review state

The system SHALL produce one long-form article draft from the entry's topic, description, optional link content and, when present, the latest article feedback. The draft SHALL be stored by the system and referenced from the entry's row in `article_queue`, which SHALL carry an article review state distinct from every asset's review state. The draft SHALL be sent to Slack for article approval.

#### Scenario: First draft produced
- **WHEN** an entry has no article draft yet
- **THEN** one article draft is stored and referenced from the entry's row
- **AND** the article review state is awaiting review
- **AND** the draft is sent to Slack for approval

#### Scenario: Empty or failed draft
- **WHEN** no non-empty article body is produced
- **THEN** no draft is stored
- **AND** the article review state is an error state naming the failure

### Requirement: Assets are produced and reviewed as a set

The system SHALL produce a set of visual assets for the entry as defined by the `visual-studio` capability, of which the static hero is always present and placed as the article's first image — the image social platforms preview when the page carries no `og:image`, which this blog does not emit. Each asset SHALL be recorded as its own row in `article_assets`, with its own review state distinct from the article review state, and SHALL be sent to Slack for that asset's approval.

#### Scenario: Asset set produced
- **WHEN** an article draft exists for the entry
- **THEN** the requested assets are produced, each with a row in `article_assets`
- **AND** each asset's review state is awaiting review
- **AND** each asset is sent to Slack for approval

#### Scenario: One asset fails
- **WHEN** one asset cannot be produced
- **THEN** that asset's review state is an error state naming the failure
- **AND** every other asset and the article draft are unaffected

### Requirement: The article and every asset are reviewed and approved separately

The system SHALL track the article and each asset as separate review subjects, each moving independently between not-started, awaiting-review, approved and rejected states. A rejection SHALL carry human feedback for that subject. Approving one subject MUST NOT change the review state of any other.

#### Scenario: Article approved, asset rejected
- **WHEN** a reviewer approves the article and rejects one asset with feedback
- **THEN** the article review state is approved
- **AND** that asset's review state is rejected carrying that feedback

#### Scenario: Asset approved, article rejected
- **WHEN** a reviewer approves an asset and rejects the article with feedback
- **THEN** that asset's review state is approved
- **AND** the article review state is rejected carrying that feedback

### Requirement: A rejected artifact is regenerated from its feedback

WHEN an artifact is rejected with feedback, the next actionable run SHALL regenerate only that artifact, applying its feedback, and SHALL re-present it for review. An approval already recorded for any other artifact MUST be preserved.

#### Scenario: Article rejected and regenerated
- **WHEN** the article is rejected with feedback and no other work is pending
- **THEN** a new article draft is produced from that feedback
- **AND** the article returns to awaiting review
- **AND** a previously approved asset remains approved

#### Scenario: Asset rejected and regenerated
- **WHEN** an asset is rejected with feedback and no other work is pending
- **THEN** a new version of that asset is produced from that feedback
- **AND** the asset returns to awaiting review
- **AND** a previously approved article remains approved

### Requirement: Publication requires the article and every requested asset approved

The system SHALL commit the article and all of its approved assets to the `alvsanand` repository's default branch **only** when the article and every requested supported asset are approved. The commit MUST place the article at `docs/blog/posts/<YYYYMM>-<slug>.md` with the repository's front-matter (`date`, `authors: [alvsanand]`, `categories`), commit each asset to the repository's image location, and reference each asset from the article at its asset marker with alt text, in a single commit. The slug MUST be unique.

#### Scenario: All approved
- **WHEN** the article and every requested supported asset are approved
- **THEN** the article and all its assets are committed together in one commit to the default branch
- **AND** the article references each committed asset with non-empty alt text

#### Scenario: Any artifact unapproved
- **WHEN** the article or any requested supported asset is not approved
- **THEN** nothing is committed to the repository

#### Scenario: Slug collision
- **WHEN** the derived slug already exists at the target path
- **THEN** the system disambiguates the slug rather than overwriting an existing post

#### Scenario: Commit fails
- **WHEN** the commit fails after all artifacts are approved
- **THEN** the entry is not marked published
- **AND** the failure is surfaced with the reason

#### Scenario: Concurrent commit on the default branch
- **WHEN** the commit is rejected because the default branch advanced during the run
- **THEN** the system re-reads the branch and retries once without force-pushing
- **AND** a second rejection is surfaced as a commit error, not retried indefinitely

### Requirement: Queue row carries exactly one terminal outcome

On success the entry SHALL be marked published and carry the published URL and the commit reference, and each asset SHALL carry its committed path. On failure the entry SHALL carry an error state and a human-readable reason. An entry MUST NOT hold more than one terminal state, and approvals MUST NOT be lost by a failed publication attempt.

#### Scenario: Successful outcome recorded
- **WHEN** the article and its assets are committed
- **THEN** the entry state is published
- **AND** it carries the article URL and the commit reference
- **AND** each asset row carries its committed path

#### Scenario: Failed outcome recorded
- **WHEN** any required step fails
- **THEN** the entry carries an error state naming the failed step
- **AND** the recorded approvals remain intact for a retry

#### Scenario: Cancelled entry retires its assets
- **WHEN** an entry is cancelled while it has non-terminal asset rows
- **THEN** those asset rows are cancelled in the same step
- **AND** no cancelled asset row is re-presented or committed

### Requirement: Runs are single-flight and review resumes from state

Two runs MUST NOT work the same entry: an actionable entry is claimed before any model call, and a run that finds an entry already claimed by a live run MUST skip it. Review state is persisted per artifact so a run that ends while an artifact awaits review is resumed by a later run from the stored state rather than restarted; a claim that is stale, because no run is live, SHALL be recoverable.

#### Scenario: Overlapping trigger
- **WHEN** a trigger fires while another run holds the entry
- **THEN** the second run skips the entry and modifies nothing

#### Scenario: Resumed review
- **WHEN** a run starts for an entry whose article or asset is awaiting review and no run is live
- **THEN** the pending review is re-presented from the stored state
- **AND** no already-approved artifact is regenerated

#### Scenario: Stale claim recovered
- **WHEN** an entry is claimed but no run is live
- **THEN** the claim is recoverable so the entry becomes actionable again

### Requirement: Pending work is determined by a defined predicate

The system SHALL determine the next action for an entry from a defined predicate over the entry's lifecycle status, the article's review status and the states of the entry's assets, and MUST NOT infer pending work from whichever field appears unfinished. Every state transition SHALL persist the state the predicate reads, so a resumed run reaches the same next action as an uninterrupted one.

#### Scenario: Resume after the article is approved
- **WHEN** a run starts for an entry whose article is approved and whose assets are not all produced
- **THEN** the next action is to produce or re-present the missing assets

#### Scenario: Resume before commit
- **WHEN** a run starts for an entry whose article and every requested supported asset are approved
- **THEN** the next action is to publish

#### Scenario: No work remains
- **WHEN** a run starts for a published, cancelled or errored entry
- **THEN** the next action is none

### Requirement: Inputs are validated before drafting

The entry's length budget SHALL be enforced on the produced draft: a draft exceeding `MAX_WORDS` MUST be produced within budget or fail loudly rather than silently overshoot. The entry's `CATEGORIES` SHALL be among the blog's existing categories or values the row explicitly declares; an unknown category MUST be rejected before any commit.

#### Scenario: Draft over budget
- **WHEN** the produced draft exceeds `MAX_WORDS`
- **THEN** the failure names the budget
- **AND** nothing is presented for review with an out-of-budget draft

#### Scenario: Unknown category
- **WHEN** the draft names a category the blog does not define
- **THEN** the run records an error naming the category
- **AND** nothing is committed

### Requirement: No review is ever skipped

A re-run that changes only prose MUST NOT skip the review of any artifact still pending, and MUST NOT declare its own fast path.

#### Scenario: Text-only tweak
- **WHEN** an entry is retried with prose-only changes
- **THEN** every pending review is still presented
- **AND** no already-approved artifact is regenerated

### Requirement: Post identity is frozen at first draft

The system SHALL derive the post slug once, at first draft, and freeze it. A later retry that changes the title MUST update the article's H1 only and MUST NOT change the slug, the published URL path or any asset filename.

#### Scenario: Title changed on retry
- **WHEN** an article is retried with a different title
- **THEN** the H1 changes
- **AND** the slug, the URL path and the asset filenames are unchanged

### Requirement: Asset references are placed at draft markers

The article draft SHALL carry one `<!-- asset:<type> -->` marker per requested asset type. The publish step SHALL replace each marker with that asset's reference and alt text. A requested type whose marker is absent from the draft MUST be placed at a default position rather than dropped.

#### Scenario: Marker present
- **WHEN** the draft contains a marker for a requested asset
- **THEN** the published article references the asset at that position with non-empty alt text

#### Scenario: Marker absent
- **WHEN** the draft omits a marker for a requested asset
- **THEN** the asset is referenced at the default position
- **AND** the asset is still committed

### Requirement: Publication is idempotent per entry

The system SHALL commit at most once for a given entry. A run against an entry already marked published MUST publish nothing and modify no row.

#### Scenario: Re-run of a published entry
- **WHEN** a run starts for an entry already marked published
- **THEN** no commit, image or row change occurs

### Requirement: Write capability is bounded

The system's write capability SHALL be limited to the `alvsanand` repository contents, the `article_queue` page, and the Slack review messages. It MUST NOT require or grant general GitHub write access to other repositories.

#### Scenario: Undeclared write target
- **WHEN** the workflow attempts a write outside the allowed targets
- **THEN** that action is not performed

### Requirement: Every review request, outcome and failure reaches a human

Each artifact awaiting review SHALL produce a Slack approval request naming the entry and the artifact. Each terminal outcome SHALL be reported to Slack. A failed run MUST surface as a failure notice rather than silence.

#### Scenario: Review requests are delivered
- **WHEN** a draft or a regenerated artifact is ready
- **THEN** Slack carries an approval request naming the entry and the artifact

#### Scenario: A long draft is reviewed without truncation
- **WHEN** the article to review exceeds the Slack message text limit
- **THEN** it is delivered complete (as a file or a snippet plus a link)
- **AND** the reviewer is not shown a truncated draft

#### Scenario: A resumed review is not ambiguous
- **WHEN** a review is re-presented after a run ended
- **THEN** it carries the artifact's round number and posts into the same review thread
- **AND** an already-approved artifact is not re-presented

#### Scenario: Failure is delivered
- **WHEN** a run fails
- **THEN** a failure notice naming the entry and the failed step is delivered to Slack

#### Scenario: Success is delivered
- **WHEN** a post is published
- **THEN** a notice carrying the published URL is delivered to Slack
