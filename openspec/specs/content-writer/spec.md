# content-writer Specification

## Purpose

The article lane: `Article Content Writer` takes a queued row — topic, description, source link and
source text — and turns it into a published blog post, calling `Article Creator` to draft the body,
`Visual Studio` to author the asset set, and owning the slug, both review gates and the single
commit to `alvsanand`.

The requirement order is history rather than design: the drafting half's guarantees come first,
because this spec existed before the lane did and gained them one follow-up at a time — what
`Article Creator` must return (a reviewed draft, the rejected draft carried into each retry, the
improvement pass, the audience). The lane's own contract follows, added with
`2026-10-25-add-content-writer-agent`: intake, the asset set and its reviews, publication,
single-flight state. Read the second group as the frame the first sits in.

## Requirements

### Requirement: A draft is reviewed before it is returned

The article draft SHALL be reviewed by a second pass before it leaves `Article Creator`, against
the same committed rules the writer was given, and a draft the review rejects SHALL be regenerated
rather than returned. The review SHALL judge the draft against the writing rules the drafting pass
followed, the length budget, and the requested asset markers. A rejection SHALL carry a reason into
the next attempt, and the number of attempts SHALL be bounded, so a draft that cannot satisfy the
review reports a reason instead of being returned or retried forever.

The length budget SHALL be checked in code rather than trusted to the review: a count a model is
asked for is a count it may invent. A draft outside the budget SHALL be rejected whatever the review
says, and the reason SHALL name the real count and the budget.

#### Scenario: A draft that breaks a rule is regenerated

- **WHEN** the review rejects a draft
- **THEN** the drafting prompt is rendered again carrying the reviewer's reason
- **AND** the returned draft is not the rejected one

#### Scenario: An over-budget draft is retried, not returned

- **WHEN** the draft's body exceeds the entry's word budget
- **THEN** the draft is rejected with the count and the budget in the reason
- **AND** the run continues to another attempt instead of ending

#### Scenario: The review reads the rules the writer followed

- **WHEN** the reviewer's prompt is composed
- **THEN** it carries the committed writing-rules file the drafting pass was given
- **AND** no second copy of those rules exists for the reviewer

#### Scenario: The attempt bound is reached

- **WHEN** every attempt within the bound is rejected
- **THEN** the sub-workflow answers with a failure naming the bound and the reviewer's last reason
- **AND** the entry point reports it once, with its own context

#### Scenario: An accepted draft carries no stale reason

- **WHEN** a draft is accepted after an earlier attempt was rejected
- **THEN** the answer's error field is empty
- **AND** the earlier reason is not returned with the accepted draft

#### Scenario: Markers name the requested types

- **WHEN** a draft is written for a requested asset set
- **THEN** each requested type's marker uses that type's own id
- **AND** a requested type with no marker is a review failure

### Requirement: The published commit carries the requested asset set

The commit SHALL carry the assets the entry asked for and no others. An asset row whose type is not
in the entry's requested set — a leftover from an earlier request, or a row written by hand — SHALL
NOT be committed, and the run SHALL report the types it left out rather than dropping them
silently. The requested set SHALL be derived once and read by every consumer, so the set the draft
is written for, the set the publish gate checks and the set the commit carries cannot disagree.

#### Scenario: A leftover asset row is not committed

- **WHEN** the entry holds an approved asset row for a type it no longer requests
- **THEN** that row is not among the committed files
- **AND** the run names the type it left out

#### Scenario: The requested set has one definition

- **WHEN** any node needs the entry's requested asset types
- **THEN** it reads the set the selector derived
- **AND** no second derivation of the hero rule exists to drift from it

#### Scenario: A requested asset is still committed

- **WHEN** every requested type has an approved row
- **THEN** each of them is committed at its own marker, with the article, in one commit

### Requirement: A rejected draft is carried into the retry

A rejected draft SHALL be passed back to the drafting pass that regenerates it, so the retry edits
the draft the review just rejected rather than writing a new one from nothing. The retry SHALL carry
the most recent attempt's draft and not an earlier one, SHALL render an empty block on the first
attempt, and SHALL NOT require a second lookup for material the run already holds.

#### Scenario: The retry edits the rejected draft

- **WHEN** the review rejects a draft and the drafting prompt is rendered again
- **THEN** the prompt carries the draft that was just rejected
- **AND** the drafting rules ask for that draft to be edited rather than replaced

#### Scenario: A third attempt edits the second draft

- **WHEN** a run reaches a second retry
- **THEN** the prompt carries the most recent rejected draft
- **AND** it does not carry the first attempt's draft

#### Scenario: The first attempt carries no draft

- **WHEN** the drafting prompt is rendered for the first attempt
- **THEN** the previous-draft block is empty
- **AND** the drafting rules are not told to edit a draft that does not exist

#### Scenario: A retry does not search again

- **WHEN** a drafting turn is a retry
- **THEN** it writes from the source material the run already holds
- **AND** it does not repeat a lookup the run has already made

### Requirement: The requested asset set names each type once

The entry's requested asset set SHALL name each type exactly once, whatever the row's `ASSET_TYPES`
holds. A type listed twice SHALL NOT cause two studio calls, two asset rows, or two committed files
at one path, and every consumer of the set SHALL read the de-duplicated set rather than its own copy.

#### Scenario: A duplicated type is requested once

- **WHEN** the row's `ASSET_TYPES` names the same type twice
- **THEN** the requested set carries that type once
- **AND** the pending set, the publish gate and the commit path all see one entry for it

#### Scenario: A duplicated hero is one hero

- **WHEN** the row names the hero raster twice
- **THEN** the requested set carries the hero once
- **AND** the hero rule does not prepend a second one

### Requirement: A human retry is handed the draft the human rejected

When a person asks for changes to a draft they read, the pass that regenerates it SHALL receive
the draft they were reading, so the change is an edit rather than a fresh article. In this lane
that pass is the improvement pass: the retry SHALL NOT re-enter the drafting sub-workflow, and the
draft of record SHALL be resolved in this order — the converged draft of this run, then the
drafting call's own answer, then the stored draft row — so a review resumed in a later execution
still improves the draft the person read. The draft SHALL be the one that was on screen when the
feedback was written and not an earlier round's, the first pass SHALL send none, and a drafting
pass re-rendered inside one invocation SHALL prefer the draft its own gate just rejected.

#### Scenario: A human asks for one change

- **WHEN** a person answers the review with feedback and the graph re-enters the improvement pass
- **THEN** the improvement prompt carries the draft they were reading and the feedback
- **AND** the parts of it the feedback does not name are kept

#### Scenario: A review resumed in a later execution still edits the reviewed draft

- **WHEN** the approval is answered after the run that presented the draft has ended
- **THEN** the draft of record is read from the stored draft row
- **AND** the improvement edits that draft rather than drafting from nothing

#### Scenario: A third round edits the second draft

- **WHEN** a draft is sent for review a second time and rejected again
- **THEN** the improvement pass carries the most recently reviewed draft
- **AND** it does not carry the first round's draft

#### Scenario: The first authoring sends nothing

- **WHEN** a draft is produced for the first time in a run
- **THEN** no previous draft or human feedback is applied
- **AND** the prompt's previous-draft block is empty

#### Scenario: The internal review loop is unaffected

- **WHEN** the drafting pass is re-rendered by the internal review gate inside one invocation
- **THEN** it edits the draft that gate just rejected
- **AND** the improvement pass's draft of record does not displace it

### Requirement: A draft is improved before it reaches a human review

A gate-passed draft SHALL be improved before it is presented for human review. One reviewer
per aspect — structure, clarity and flow at minimum — SHALL review the draft and return
advisory findings, and an improvement pass SHALL edit the draft applying those findings and any
human feedback. The aspect reviewers SHALL NOT reject a draft, gate a round, or spend a retry
bound: their findings are input to the improvement pass, and the only gates SHALL remain the
drafting gate's objective checks, the code re-check, and the human approval.

The improvement SHALL be verified in code before it is delivered: the improved draft's body
SHALL be within the entry's word budget and SHALL carry every requested asset marker exactly
once. An improved draft that fails either SHALL be retried with the objective problem stated,
at most once, and the run SHALL then fall back to the gate-passed pre-improvement draft with the
reason recorded. A count SHALL be taken in code, never asked of a model.

A failure inside the improvement pass SHALL degrade rather than block: an aspect reviewer that
cannot answer records no findings for its aspect and the rest run; an improvement pass that
fails records the reason and falls back to the gate-passed draft. The improvement outcome —
improved, fallback, failed, or nothing to apply — SHALL be visible to the human reviewer with
the draft. An aspect registry that is missing, unparsable or empty SHALL fail the run loudly
rather than improve nothing quietly.

#### Scenario: Findings are applied and the draft is improved

- **WHEN** the aspect reviewers return findings
- **THEN** the improvement pass edits the draft applying them
- **AND** the draft presented for review is the improved one, with the outcome named

#### Scenario: Nothing to apply leaves the draft unchanged

- **WHEN** every aspect returns no findings and there is no human feedback
- **THEN** no improvement pass runs
- **AND** the draft presented for review is the drafting pass's own, with the outcome named

#### Scenario: An improved draft outside the objective checks is not delivered

- **WHEN** the improved draft exceeds the word budget or drifts a requested asset marker
- **THEN** the failure is counted in code and the improvement is retried once with the problem
- **AND** the draft presented for review is the gate-passed one, with the fallback recorded

#### Scenario: A failed improvement pass does not lose the draft

- **WHEN** the improvement pass fails after its retries
- **THEN** the gate-passed draft is presented for review
- **AND** the reason is recorded and named to the reviewer

#### Scenario: A failed aspect reviewer does not fail the others

- **WHEN** one aspect's review cannot answer
- **THEN** that aspect records no findings
- **AND** the remaining aspects' findings still reach the improvement pass

#### Scenario: A human retry edits the draft the human read

- **WHEN** a person answers the review with feedback
- **THEN** the improvement pass re-enters with that feedback and the draft the person was reading
- **AND** the parts of it the feedback does not name are kept

### Requirement: An article is written for the row's audience

An entry SHALL carry an audience level — `NONE`, `LOW`, `MEDIUM` or `ADVANCED` — and the
drafting pass, the internal review gate, the aspect reviewers and the improvement pass SHALL
all be told that level and one committed definitions file describing what each level's reader
already knows. The gate SHALL scale its term-explanation expectation with the level, so it
never demands explanations the level's reader does not need.

A level that is blank or missing SHALL read as `NONE`, the general reader new to the subject,
so an existing row needs no backfill and behaves exactly as before this change. A level that
is not one of the four SHALL refuse the row before it drafts, naming the value, rather than
being read as a default. The definitions SHALL exist in one committed file and SHALL NOT be
restated in any prompt, gate check or workflow code, and the level ids SHALL agree between that
file, the entry point's validation and the board intake's configured default.

#### Scenario: The level reaches every pass

- **WHEN** a row carries an audience level
- **THEN** the drafting prompt, the gate's prompt, the aspect prompts and the improvement prompt all carry it
- **AND** all four read the same committed definitions

#### Scenario: The gate scales with the level

- **WHEN** a draft for an `ADVANCED` row explains the field's basics anyway
- **THEN** the gate does not reject for lacking term explanations
- **AND** a draft for a `NONE` row that uses a subject term unexplained is still rejected

#### Scenario: A blank level is today's reader

- **WHEN** a row carries no audience level
- **THEN** the drafting pass is told `NONE`
- **AND** the article is written for a reader new to the subject, as before this change

#### Scenario: An invalid level is refused, not defaulted

- **WHEN** a row's audience cell is not one of the four levels
- **THEN** the row is refused before drafting, with the value named in the reason

### Requirement: The aspect registry is the single list of aspects

The aspects that review a draft SHALL be declared in one committed registry — each with an
identifier and its prompt file — and the improvement chain SHALL derive its work from that
registry at run time. The workflow graph SHALL NOT carry an aspect identifier of its own, so
adding, removing or rewording an aspect is a registry and prompt-file change, not a graph
change. A prompt file the registry names SHALL exist in the repository before the graph is
applied, because a fetch of a missing file fails the run.

#### Scenario: An aspect is added without a graph edit

- **WHEN** the registry gains an aspect entry and its prompt file
- **THEN** the next run reviews the draft against that aspect too
- **AND** no workflow export changed

#### Scenario: The registry is load-bearing

- **WHEN** the registry is missing, unparsable or empty
- **THEN** the run fails loudly before any improvement
- **AND** it does not silently present an unimproved draft as improved

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

The system SHALL produce one long-form article draft from the entry's topic, description, optional link content, sources the writer retrieved during that run and, when present, the latest article feedback. The draft SHALL be stored by the system and referenced from the entry's row in `article_queue`, which SHALL carry an article review state distinct from every asset's review state. The draft SHALL be sent to Slack for article approval.

#### Scenario: First draft produced
- **WHEN** an entry has no article draft yet
- **THEN** one article draft is stored and referenced from the entry's row
- **AND** the article review state is awaiting review
- **AND** the draft is sent to Slack for approval

#### Scenario: Empty or failed draft
- **WHEN** no non-empty article body is produced
- **THEN** no draft is stored
- **AND** the article review state is an error state naming the failure

### Requirement: The writer researches within a bound and attributes what it read

The writer SHALL be able to search for the entry's subject and to read a page it found, within a bounded number of lookups per draft, and SHALL cite only pages it fetched during that run. A retrieved source SHALL be used only when it is about the entry's subject. When a search returns nothing usable or a source cannot be reached, drafting SHALL continue from the entry's inputs alone rather than from unread material.

#### Scenario: A search finds a usable source
- **WHEN** the writer searches for the entry's subject and a result is about that subject
- **THEN** the writer reads the page before relying on it
- **AND** the draft cites it, and cites nothing it did not fetch

#### Scenario: Results are about a different subject
- **WHEN** every result shares the subject's name but is a different thing
- **THEN** the writer stops searching instead of hunting for a match
- **AND** the draft is written from the entry's inputs and cites no source

#### Scenario: A search source is unavailable
- **WHEN** one of the search sources cannot be reached in that run
- **THEN** the writer is told which source did not answer
- **AND** drafting continues from the sources that did
- **AND** when none answered, the draft is written from the entry's inputs alone

### Requirement: Assets are produced and reviewed as a set

The system SHALL request the entry's visual asset set from the `visual-studio` capability, naming types from that capability's registry. The `image` type SHALL always be requested and is the article's hero — the image social platforms preview when the page carries no `og:image`, which this blog does not emit; a blank `ASSET_TYPES` SHALL resolve to `image,svg`, and a declared list SHALL add to the hero rather than replace it. The request SHALL carry the entry's session identity, so a later request for the same entry continues the same authoring. Each asset SHALL be recorded as its own row in `article_assets` with a review state distinct from the article review state and from every other asset's, and SHALL be sent to Slack for that asset's approval.

#### Scenario: Asset set produced
- **WHEN** an article draft exists for the entry
- **THEN** the requested assets are produced, each with a row in `article_assets`
- **AND** each asset's review state is awaiting review
- **AND** each asset is sent to Slack for approval

#### Scenario: One asset fails
- **WHEN** one asset cannot be produced
- **THEN** that asset's review state is an error state naming the failure
- **AND** every other asset and the article draft are unaffected

#### Scenario: A requested type is not in the registry
- **WHEN** the entry requests a type the registry does not declare
- **THEN** that asset's review state is an error state naming the type
- **AND** the other requested assets are produced and reviewed normally

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

WHEN an artifact is rejected with feedback, the next actionable run SHALL regenerate only that artifact, applying its feedback, and SHALL re-present it for review. A rejected asset SHALL be regenerated by requesting that type again within the entry's session, so the correction lands on the composition the rejection named rather than on a new one. An approval already recorded for any other artifact MUST be preserved.

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

#### Scenario: A blocked publish is reported rather than silent
- **WHEN** the gate finds a requested asset that is not approved, including one with no row at all
- **THEN** nothing is committed
- **AND** a notice naming the entry and the blocking assets is delivered to Slack
- **AND** the run ends without waiting on a review

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

### Requirement: The hero asset is framed for a screen

The article's hero asset SHALL be produced at a landscape frame suited to reading on a screen. The frame SHALL come from the asset type's own declaration rather than from a value fixed in the workflow, and it SHALL reach both the image request and the prompt that directs the model, so the composition and the generated frame agree. Types bound to a platform feed keep that platform's frame.

#### Scenario: The hero is landscape
- **WHEN** a run requests the default asset set for an entry
- **THEN** the raster hero type it asks for is the 16:9 one
- **AND** the composer-authored diagram is requested at the same frame

#### Scenario: The frame reaches the raster request and its prompt
- **WHEN** a raster type is authored
- **THEN** the image request asks for the type's declared aspect
- **AND** the prompt that directs the model is told the same frame

#### Scenario: A platform type keeps its own frame
- **WHEN** a type bound to a platform feed is authored
- **THEN** its declared frame is unchanged by this requirement

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
