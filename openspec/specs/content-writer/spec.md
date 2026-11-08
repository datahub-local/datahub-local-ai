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

### Requirement: The review judges facts against the pages the writer fetched

The review gate SHALL judge a draft's facts, names, numbers, quotations and dates against the
entry's inputs, the entry's seed page, and every page the writer fetched during that run. The
fetched pages SHALL remain available to the review turn in the same session; the source ledger
continues to name the pages a fenced block was read on. A fact from a fetched page SHALL NOT be
rejected as invented merely because the seed page does not carry it.

A fact absent from the entry's inputs, the seed page and every fetched page SHALL be a failure,
and a citation of a page the writer did not fetch SHALL be a failure.

#### Scenario: A fact from a fetched page is sourced

- **WHEN** the draft states a fact that is on a page the writer fetched during the run
- **THEN** the review does not reject it for being absent from the seed page
- **AND** the seed page remains the entry's source, not the limit of the corpus

#### Scenario: A fact from nowhere is still invented

- **WHEN** the draft states a fact that is absent from the entry's inputs, the seed page and every fetched page
- **THEN** the review rejects it as invented

#### Scenario: A citation must name a fetched page

- **WHEN** the draft cites a URL the writer did not fetch during the run
- **THEN** the review rejects the citation

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

A round that carries human feedback SHALL change the draft: a returned body and title equal to the
ones it was given SHALL be reported as unchanged and SHALL NOT be reported as an improvement. A
feedback round MAY add a fenced block no fetched page carries, because the person asking for it is
the authority the ledger otherwise stands in for; such a block SHALL be counted and named to the
reviewer as unverified. A block the ledger does carry and that failed verification — not found,
failed validation, drifted excerpt — SHALL still fail on a feedback round, and a round without
human feedback SHALL keep the strict rule.

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

#### Scenario: A feedback round adds a command no fetched page carries

- **WHEN** a person asks for a command the project's documentation does not contain
- **THEN** the improvement pass writes it as a fenced block
- **AND** the block is counted and the review message names it as unverified

#### Scenario: A first-draft edit may not add such a block

- **WHEN** a round without human feedback fences a block no ledger entry carries
- **THEN** the edit fails the code re-check naming the block
- **AND** the pre-improvement draft is presented for review

#### Scenario: Feedback does not excuse a ledgered block the page lost

- **WHEN** a feedback round keeps a block whose ledger entry is `found: false`
- **THEN** the edit fails the code re-check naming the page

#### Scenario: A feedback round that changes nothing says so

- **WHEN** a feedback round returns the body and title it was given
- **THEN** the outcome is reported as unchanged, not improved
- **AND** the reviewer is told the feedback was not applied

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
improved, unchanged, fallback, failed, or nothing to apply — SHALL be visible to the human
reviewer with the draft, and an unchanged outcome SHALL say the feedback was not applied. An
aspect registry that is missing, unparsable or empty SHALL fail the run loudly rather than
improve nothing quietly.

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

#### Scenario: An unchanged round is not delivered as an improvement

- **WHEN** the improvement pass returns the draft it was given
- **THEN** the draft of record is the one that was presented before
- **AND** the outcome is named unchanged rather than improved

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

The aspects that review a draft SHALL be declared in one committed registry in the writer
adapter's image — each with an identifier and its prompt file beside it — and the adapter SHALL
derive its reviewer turns from that registry at run time. The workflow graph SHALL NOT carry an
aspect identifier of its own, so adding, removing or rewording an aspect is a registry and
prompt-file change in the image, not a workflow change. The registry SHALL be validated before
the adapter serves a turn, because a turn that runs with no aspects would improve on nothing
while looking healthy.

#### Scenario: An aspect is added without a graph edit

- **WHEN** the registry gains an aspect entry and its prompt file
- **THEN** the next image reviews the draft against that aspect too
- **AND** no workflow export changed

#### Scenario: The registry is load-bearing

- **WHEN** the registry is missing, unparsable or empty
- **THEN** the adapter refuses to start
- **AND** it does not answer aspect turns with an empty findings list

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

The writer SHALL be able to search for the entry's subject and to read a page it found, within a bounded number of lookups per draft, and SHALL cite only pages it fetched during that run. A retrieved source SHALL be used only when it is about the entry's subject. When a search returns nothing usable or a source cannot be reached, drafting SHALL continue from the entry's inputs alone rather than from unread material. The drafting session SHALL reach the cluster's MCP catalog as well as the allowlisted HTTPS proxy: it MUST offer the catalog's GitHub read tools (`search_code`, `search_repositories`, `get_file_contents`, `list_branches`, `list_commits`, `list_tags`) and Firecrawl read tools (`firecrawl_search`, `firecrawl_scrape`, `firecrawl_map`) directly to the model, and MUST NOT expose any write tool on those servers. Every fenced block SHALL still name a URL the session server can refetch: a file read through the catalog is ledgered by its `https://raw.githubusercontent.com/<owner>/<repo>/<ref>/<path>` address, and a documentation page by the page's own URL on a declared source host. A catalog search result is a pointer, not a source, and SHALL NOT be ledgered as one.

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

#### Scenario: A block was read through the catalog

- **WHEN** a fenced block came from `get_file_contents` or a Firecrawl read
- **THEN** its ledger URL answers the server's refetch
- **AND** a block whose ledger URL does not answer is dropped before n8n reads the ledger

#### Scenario: A write tool is named

- **WHEN** a drafting turn tries to reach a catalog write tool such as `create_or_update_file`
- **THEN** the tool is not declared to the model, because the server's exposure is `hidden` and only the read tools carry `direct` exposure

#### Scenario: The catalog does not answer

- **WHEN** a catalog server fails to connect
- **THEN** the turn continues through the allowlisted `curl` path
- **AND** the draft says in one sentence that the source could not be read when neither path answers

### Requirement: Assets are produced and reviewed as a set

The system SHALL request the entry's visual asset set from the `visual-studio` capability, naming types from that capability's registry. A raster hero SHALL always be requested and is the article's hero — the image social platforms preview when the page carries no `og:image`, which this blog does not emit; a blank `ASSET_TYPES` SHALL resolve to `image_wide,svg_wide`, and a declared list SHALL add to the hero rather than replace it. This lane SHALL request wide frames only: a row naming the portrait `image` or `svg` SHALL be normalized to `image_wide` or `svg_wide` before the set is requested, because the article is read in a text column and a 4:5 asset is a phone poster there. The request SHALL carry the entry's session identity, so a later request for the same entry continues the same authoring. Each asset SHALL be recorded as its own row in `article_assets` with a review state distinct from the article review state and from every other asset's, and SHALL be sent to Slack for that asset's approval.

#### Scenario: Asset set produced
- **WHEN** an article draft exists for the entry
- **THEN** the requested assets are produced, each with a row in `article_assets`
- **AND** each asset's review state is awaiting review
- **AND** each asset is sent to Slack for approval

#### Scenario: A portrait type is requested
- **WHEN** the entry's `ASSET_TYPES` names `image` or `svg`
- **THEN** the request asks for `image_wide` or `svg_wide` instead
- **AND** no 4:5 asset is produced for the article

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
- **AND** it is resumed before a fresh entry is started, so a stuck one cannot starve behind new work

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

The entry's length budget SHALL be enforced on the produced draft with a counting margin: a body of
at most ten percent over `MAX_WORDS` is the budget met, and a body past that limit MUST be retried
within the limit or fail loudly rather than silently overshoot. The limit SHALL be computed in the
same place the body is counted, and the review that decides acceptance SHALL be told the same limit
rather than the raw budget, so a reviewer cannot reject a draft the count accepts. The entry's
`CATEGORIES` SHALL be among the blog's existing categories or values the row explicitly declares; an
unknown category MUST be rejected before any commit.

#### Scenario: Draft inside the counting margin

- **WHEN** the produced draft is over `MAX_WORDS` but not over the ten percent limit
- **THEN** it is not rejected for length
- **AND** it is presented for review

#### Scenario: Draft over budget

- **WHEN** the produced draft is over the ten percent limit
- **THEN** the failure names the limit and the draft is retried
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

### Requirement: An article is one spine, one path and the names it created

The drafting pass SHALL write one article around one outcome rather than a tour of everything the
sources hold. Every shape SHALL inherit the same contract: one outcome named before the first
sentence; one path, with an alternative demoted to a sentence outside the numbered steps; every name
a later step uses created by an earlier step and spelled the same; one job per section; numbered
step headings as one sequence 1..n with no gap, duplicate or sub-step, and an unnumbered close; and a
step that ends on what the reader sees when a source carries it. The body SHALL NOT narrate the
article or the work of writing it.

The drafting gate SHALL reject a draft that breaks the contract, naming the step and the name, so the
retry receives the failure instead of passing it to the improvement pass. The structure aspect SHALL
report the same defects on the improvement pass.

#### Scenario: A later step uses a name the article never created

- **WHEN** a walk-through step names a cluster, namespace, Secret, ensemble, persona, run or URL that
  no earlier step created
- **THEN** the draft is rejected, naming the step and the name
- **AND** the retry is told to use the name the article created

#### Scenario: An alternative install sits inside the numbered path

- **WHEN** a numbered step carries a second installation route, a second tool or another page's
  example object as a sub-step
- **THEN** the draft is rejected as a second path
- **AND** the alternative is demoted to a sentence outside the steps or cut

#### Scenario: A second teaching section follows the walk-through

- **WHEN** a section after the walk-through explains material the article did not explain where it
  first appeared
- **THEN** the draft is rejected as a second job
- **AND** the explanation moves to the step that first shows the thing, or is cut

#### Scenario: Numbered steps are not one sequence

- **WHEN** the step headings are numbered and one is skipped, duplicated, or joined by a numbered
  sub-step, or the close is numbered
- **THEN** the draft is rejected
- **AND** an article that is not a walk-through numbers no heading

#### Scenario: The close narrates the writing

- **WHEN** the body says it did not run something, refers to "this section", or notes that a sample
  is missing
- **THEN** the draft is rejected
- **AND** an unknown stated as a fact about the software is accepted

#### Scenario: A coherent draft passes

- **WHEN** every section serves the one outcome, every name is created before it is used, and the
  steps are one sequence
- **THEN** the gate does not reject the draft for structure
- **AND** the comparison, the numbers and the asset markers are judged by their own checks

### Requirement: The drafting prompt belongs to the writer adapter

The article's drafting prompt, the shapes it may choose from and the audience levels SHALL live in
the writer adapter's image, and the caller SHALL send the entry's fields rather than prompt text. A
prompt edit SHALL take effect with the image, without a workflow change. The review and the
improvement pass SHALL read the same committed rules file the adapter renders, so no second copy
exists.

#### Scenario: The creator posts a turn

- **WHEN** `Article Creator` requests a draft
- **THEN** the body carries the entry's fields, the session id, the attempt and the source hosts
- **AND** it carries no prompt text

#### Scenario: A prompt file changes

- **WHEN** the adapter's prompt file changes and the image is rebuilt
- **THEN** the drafting prompt changes
- **AND** no n8n workflow changes with it

#### Scenario: The gate reads the writer's rules

- **WHEN** the reviewer's prompt is composed
- **THEN** `RULES` is the adapter's `article_writer_system.md`
- **AND** no second copy of those rules exists in `agents/n8n/prompts/`

#### Scenario: A missing entry field

- **WHEN** the brief omits a field the task template names
- **THEN** the field renders empty
- **AND** the turn still writes the article from the fields it was given

### Requirement: The writer adapter owns every article model turn

The article lane's drafting, publish gate, aspect review and improvement edit SHALL each be a
turn of the writer adapter, in one session per entry. The workflow SHALL send the session id, the
entry's fields, the draft of record and any feedback, findings or objective problem; it SHALL
carry no prompt text, no aspect registry and no model node of its own. The adapter SHALL render
every prompt from files in its image.

A human rejection SHALL re-enter the same writer session as feedback, carrying the draft the
person read, so the feedback always reaches the writer.

The deterministic gates SHALL remain in the workflow: word budget, asset markers and source
ledger fidelity SHALL be counted in code, and a gate SHALL NOT accept a verdict a second copy of
the model's own count.

A turn that cannot answer SHALL be reported rather than silently pass. A gate turn SHALL reject
the draft with its transport failure named, so the retry carries the cause. An aspect turn that
fails SHALL contribute no findings and leave the other aspects running. An edit turn that
returns no article SHALL be reported failed, distinct from nothing to apply.

#### Scenario: A round's turns share one session

- **WHEN** a draft is reviewed, an aspect pass runs, or an edit is applied
- **THEN** each turn names the same session id as the draft
- **AND** the adapter renders the turn's prompt from its own files

#### Scenario: A human rejection reaches the writer

- **WHEN** a person answers the review with feedback
- **THEN** the aspect and edit turns run in the draft's session with that feedback
- **AND** the edit carries the draft the person was reading

#### Scenario: A gate turn that cannot answer is a rejection with its reason

- **WHEN** the review request fails or answers no verdict
- **THEN** the drafting loop retries with the failure named in the explanation
- **AND** the run does not end on the failed reviewer

#### Scenario: An edit turn that cannot answer is failed, not empty

- **WHEN** the edit request fails or returns no article
- **THEN** the outcome is reported failed with the reason
- **AND** the gate-passed draft is used and named to the reviewer

#### Scenario: The article workflows carry no model node

- **WHEN** either article workflow is exported
- **THEN** it contains no language-model node and no model credential
- **AND** the only model calls leave it as HTTP requests to the writer adapter

#### Scenario: The prompts exist once

- **WHEN** the gate, aspect or improvement prompt is rendered
- **THEN** it is read from the adapter image
- **AND** no copy exists under `agents/n8n/`

### Requirement: The entry point reaches the writer through Article Creator

Every article writer turn SHALL run inside `Article Creator`. The entry point SHALL select the
turn with a `TASK` input whose values are `draft`, `aspects` and `improve`, defaulting to `draft`,
and SHALL NOT post to the writer adapter itself. The entry point SHALL pass the draft of record,
the merged findings and, on a retry, the objective problem named by its code re-check into the
sub-workflow; the sub-workflow SHALL answer the adapter's result, so the entry point reads one
response shape for a direct call and for a sub-workflow answer.

A task the sub-workflow does not implement SHALL fail the run naming the task, and SHALL NOT fall
back to drafting.

#### Scenario: The aspect pass is a call to the sub-workflow

- **WHEN** the improvement pass starts
- **THEN** the entry point calls `Article Creator` with `TASK` `aspects` and the draft of record
- **AND** the entry point contains no HTTP node that posts to the writer adapter

#### Scenario: The edit pass is a call to the sub-workflow

- **WHEN** the findings or human feedback call for an edit
- **THEN** the entry point calls `Article Creator` with `TASK` `improve`, the draft of record and the merged findings
- **AND** a retry also carries the objective problem the code re-check named

#### Scenario: An unimplemented task does not draft

- **WHEN** a caller asks `Article Creator` for a task it does not implement
- **THEN** the run fails naming the task
- **AND** no draft is spent

#### Scenario: The answer crosses the boundary unchanged

- **WHEN** the sub-workflow returns an aspect or edit answer
- **THEN** the entry point's parser reads the same status and body it would read from a direct call
- **AND** a transport failure is still an error item, not a missing answer

### Requirement: An article that teaches a tool shows a block the reader can run

A draft whose shape teaches a tool SHALL carry at least one fenced block quoted from a page the run
fetched and ledgered. The block SHALL be verbatim: a name it needs is introduced in the prose above
it, because the ledger matches the block's words against the page and an edited block loses its
entry. A block that cannot run as written — elided lines, a missing import, an undefined name — is
a fragment and SHALL be written whole or left out.

The drafting prompt SHALL also ask for the failure the reader will meet, quoted from a fetched page
with its cause and fix, and for the version the article was checked against, as the source spells
it, in the section that first depends on one.

#### Scenario: A draft with no block where the shape teaches a tool

- **WHEN** the draft walks the reader through commands and fences nothing
- **THEN** the drafting prompt's block rule is the rule that was broken
- **AND** the retry carries the requirement

#### Scenario: A block is a fragment

- **WHEN** a fenced block carries an undefined name or an elided line
- **THEN** it is written whole with the name introduced in the prose above it, or it is cut

#### Scenario: No page states a version

- **WHEN** no fetched page carries a version string
- **THEN** the draft says nothing about versions

### Requirement: The title, a figure and a recommendation are held to a rule

The title SHALL name the subject and the specific thing the article settles, in at most twelve
words, and SHALL NOT be "A Guide to X" or a colon followed by a slogan. A number SHALL state what
was measured, on what, and where the figure comes from; a rounded figure used to sound large and a
range extrapolated from one data point SHALL NOT be written. When the body recommends a tool or an
approach it SHALL name where that choice is wrong and what to use instead. The close SHALL name the
page with the URL the run fetched, or the command to run now, and "see the documentation" SHALL NOT
serve as one.

#### Scenario: A title that fits another project

- **WHEN** the draft's title could headline an article about a different project
- **THEN** the review rejects the draft naming the title
- **AND** the improvement rewrites the title to the subject and its outcome

#### Scenario: A recommendation with no boundary

- **WHEN** the body recommends a tool and never says when not to use it
- **THEN** the review rejects the draft naming the recommendation
- **AND** the finding asks for the one line on the wrong choice

#### Scenario: A close that points nowhere

- **WHEN** the close says to read the documentation without naming the page
- **THEN** the review rejects the draft naming the close

### Requirement: A retry's lookups answer the feedback, not the old brief

A drafting retry SHALL fetch at most four pages, and only to answer a claim the reviewer feedback
names that the pages already held do not. A lookup the run has already answered SHALL NOT be
repeated.

#### Scenario: Feedback names a claim the run cannot source

- **WHEN** the feedback asks for a command the run never fetched
- **THEN** the retry fetches the page that carries it, within two lookups
- **AND** the block it writes is ledgered against that page

#### Scenario: Feedback asks for a restructure

- **WHEN** the feedback is about the article's shape and not about a fact
- **THEN** the retry fetches nothing

### Requirement: The ledger is re-read through the one path that leaves the pod

The session server SHALL verify a ledger through the Firecrawl MCP server when its endpoint is
configured, by calling `firecrawl_scrape` for each cited URL and matching the block on the scraped
markdown. It SHALL apply the source-host policy to the citation before any read, so the reader
widens the pod's reach and not what may be cited. With no endpoint configured it SHALL fall back to
the direct fetch and SHALL log at boot which path it uses.

#### Scenario: A pod with no internet egress

- **WHEN** the deployment carries only the MCP servers in the pod's egress policy
- **THEN** a ledgered URL is verified through the Firecrawl server, not a direct fetch
- **AND** a block the scraped page carries keeps its entry

#### Scenario: A scrape answers an error

- **WHEN** the Firecrawl call fails or answers unusable text
- **THEN** the entry is dropped with the failure named in the reason
- **AND** the drafting gate rejects the fence whose entry was dropped

#### Scenario: A citation off the declared hosts

- **WHEN** the ledger cites a host the request did not declare
- **THEN** the entry is dropped without a scrape being attempted

### Requirement: A writer session is compacted well inside the model window

The writer SHALL write Pi's `compaction` settings rather than leave them to the vendor default: it
SHALL keep compaction enabled, SHALL express the trigger as a percentage of the context window so a
change of model needs no configuration change, and SHALL resolve that percentage into the token
reserve Pi expects, floored so the output cap and the summariser's own request still fit. It SHALL
refuse a percentage that is not between 0 and 100 or a kept-recent share at or above the trigger,
and SHALL log the resolved trigger with the window at boot.

#### Scenario: A session that has grown across retries

- **WHEN** a resumed session is larger than the trigger
- **THEN** Pi compacts it before the next request
- **AND** the request the gateway receives is the summary plus the recent tokens, not the whole history

#### Scenario: The model window changes

- **WHEN** the deployment points the writer at a model with a different input limit
- **THEN** only the context window is set
- **AND** the trigger stays the same share of it

#### Scenario: An unusable share

- **WHEN** the trigger is not between 0 and 100, or the kept-recent share is at or above it
- **THEN** the server refuses to write the settings file
- **AND** the pod does not start on a configuration that cannot compact

#### Scenario: Evidence of the bound

- **WHEN** the session server starts
- **THEN** it logs the resolved trigger, its percentage and the context window it fits inside
