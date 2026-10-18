# Design

## Context

Two queues on the `content_planner` sheet feed the two publishing lanes, and each queue is
owned by exactly one writer today:

- `content_queue` — the post lane. `Content Feed Curator` tops it up and retires rows
  (`build_expire_rows` → `expire_auto_queue`); `LinkedIn Post Sharing` drains one row per
  run. Statuses in play: `QUEUE`, `IN_PROGRESS`, `WAITING_APPROVAL`; terminal: `PUBLISHED`,
  `ERROR`, `EXPIRED`, `CANCELED`.
- `article_queue` — the blog lane (`add-content-writer-agent`). Rows are authored by hand
  and drained by `Article Content Writer`. Statuses in play: `QUEUE`, `IN_PROGRESS`,
  `WAITING_APPROVAL`; terminal: `PUBLISHED`, `CANCELLED`, `ERROR`.

The board is the open-issue list of `datahub-local/datahub-local` filtered on the `post`
label. Four issues carry it today (#79, #80, #91, #95). A board issue is only a title, an
optional body and a URL — no category, no asset set, no budget.

`DownloadTemplate` (`qUfjfWLGEjV96ljf`) fetches any file under `agents/n8n/` from `main`
by path, so a new dataset needs no registration, only the file on `main`.

## Gate findings

Read from the running system, not from documentation or memory, on 2026-10-18.

- **The board is issues, not a Project board.** `gh search issues --owner datahub-local
  --label post` returns exactly the four issues above, each labelled `documentation` and
  `post`, body empty on three of them. The board is addressed as a repository's issues.
- **The installed GitHub node has no issue-list operation.** Read off the running image's
  `n8n-nodes-base/dist/types/nodes.json`: the `issue` resource carries only
  `create`/`createComment`/`edit`/`get`/`lock`. Listing is `resource: repository,
  operation: getIssues`, with `getRepositoryIssuesFilters` = `{assignee, creator,
  mentioned, labels, since, state, sort, direction}` and `state` defaulting to `open`. The
  first design used `resource: issue, operation: getAll`, which does not exist.
- **The two lanes spell cancellation differently.** `content_queue`'s lane writes
  `CANCELED` (one L, `linked_in_post_sharing`); `article_queue`'s lane writes `CANCELLED`
  (two Ls, `article_content_writer`'s `update_status_cancelled`, and `pick_candidate`
  checks `ARTICLE_STATUS === 'CANCELLED'` to skip a claimed row). A single spelling in
  either queue would match nothing.
- **`article_queue` has no intake writer.** Its 22 columns are `ENTRY_ID, TOPIC,
  DESCRIPTION, LINK, CATEGORIES, ASSET_TYPES, MAX_WORDS, EXTRA_PROMPT, PRIORITY, ORIGIN,
  STATUS, ARTICLE_STATUS, ARTICLE_ROUND, ARTICLE_FEEDBACK, ARTICLE_TITLE, ARTICLE_REF,
  PUBLISHED_URL, COMMIT_REF, PUBLISHED_AT, EXECUTION_ID, ERROR, UPDATE_DATE`. `ENTRY_ID`
  is the identity (the article lane keys its draft and asset tables on it) and
  `pick_candidate` ignores a row with a blank one.
- **`read_article_queue` and `Article Content Writer` tolerate a blank `EXTRA_PROMPT` and
  absent lifecycle columns**; a row needs `ENTRY_ID` and at least one of `TOPIC` /
  `DESCRIPTION` or `pick_candidate` throws.
- **`GENERIC_TIMEZONE` is `UTC` in the running n8n pod**, and the schedules here are naive
  cron interpreted in it; the "Europe/Madrid" in the notes is intent. The board intake is
  not time-sensitive, so it takes a plain cron expression like its neighbours.
- **An empty board or an empty queue must not stop the chain.** n8n does not execute a
  node that receives zero items, so both the GitHub read and the queue read carry
  `alwaysOutputData`, or the ceiling below would never run on a quiet day.

## Goals / Non-Goals

**Goals:**

- Board → `article_queue` with no retyping, once per issue, read-only on GitHub.
- One retirement rule that reaches a row no matter which phase left it stuck.
- One configured value, one write per row, no interaction between the ceiling and the TTL.

**Non-Goals:**

- Any write to GitHub; any judgement of a board idea.
- Changing the article or post lane.
- Applying live (see the proposal's Impact).

## Decisions

### D1. A new workflow owns the board and the article queue's ceiling

`Content Feed Curator` is a feed→backlog curation job with one LLM stage and a lot of
scoring; the board is a different source with a different failure surface. Adding it there
would put a GitHub read and a second sheet's writes into a workflow whose digest, caps and
prompt budget are all tuned to Miniflux. The new `Content Board Curator` owns the board
read, the `article_queue` append and the `article_queue` ceiling; the existing curator owns
the `content_queue` ceiling. Each queue keeps one writer.

*Alternatives considered:* extend the curator — rejected above. Put the ceiling in the
lane that drains the queue (`LinkedIn Post Sharing`, `Article Content Writer`) — rejected:
it would run three times a week at publish time rather than daily, and it puts a
maintenance write in a workflow whose whole job is to publish one item.

### D2. Read-only, deduped by the issue's own identity

The read is `getIssues` filtered on the configured label and state; nothing writes back.
Dedupe is `ENTRY_ID` = `gh-<number>` and `LINK` = the issue URL, both checked against every
row already in `article_queue` whatever its status. `number` is GitHub's stable identity, so
`gh-79` is the same row on every later run, and the `LINK` check catches an idea a human
added by hand. An issue therefore stays open until a person closes it.

*Alternatives considered:* close or label the issue after import — rejected: it makes the
intake a writer of someone else's board, and closing loses the "I still want this" signal a
human put there. A marker comment — same objection. Status-based dedupe (skip anything the
curator already imported by URL) — rejected: `ENTRY_ID` is what the article lane already
uses for identity, and matching on it is exact.

### D3. An imported row is the issue's own data plus the lane's defaults

`TOPIC` is the title, `DESCRIPTION` the body, `LINK` the URL; `CATEGORIES`, `ASSET_TYPES`,
`MAX_WORDS` and `PRIORITY` come from `board_intake.json` (`General`, `image,svg`, 1200,
`MEDIUM` — the same defaults a hand-authored row starts from, and `General` is one of
`blog_categories.json` or the article lane would refuse the row). `ORIGIN=BOARD` marks
where it came from. No model is consulted: the row is a person's decision.

*Alternatives considered:* have the article lane classify the issue — rejected: the lane
already reviews the draft, and a second judgement on an idea a human chose buys nothing.

### D4. The ceiling is the row's own clock, and only rows in play

The measure is the row's `UPDATE_DATE` — the last write any phase made — not the source
article's date and not the row's creation. That is what makes the rule safe: an in-flight
run rewrites `UPDATE_DATE` at every phase, so a live run is never a week old, while a run
that died mid-claim or an approval nobody answered is. Only `QUEUE`, `IN_PROGRESS` and
`WAITING_APPROVAL` are candidates; `PUBLISHED`, `EXPIRED`, `ERROR` and the two spellings of
cancelled are terminal and are never rewritten. A board-imported row is fresh by
construction (its `UPDATE_DATE` is the import time), so the ceiling cannot swallow the
intake work in the same run.

*Alternatives considered:* measure from the source article's `PUBLISHED_AT` /
the issue's creation date — rejected: a three-week-old article admitted today is a fresh
row, and a September board issue would be cancelled the moment it was imported. The row's
own age is the only clock that means "this stopped moving".

### D5. Two spellings, because the two lanes disagree

`content_queue` cancellation writes `CANCELED`; `article_queue` writes `CANCELLED` and sets
`ARTICLE_STATUS=CANCELLED` too. The article half is two fields because the lane resumes a
stale `IN_PROGRESS` claim by reading `ARTICLE_STATUS` (`pick_candidate` skips
`ARTICLE_STATUS === 'CANCELLED'`), so cancelling the queue status alone would leave the row
resumable.

### D6. One value, read by both workflows

`cancel_after_days` (default 7) lives in `curator_config.json`, next to the per-hook TTLs
it sits in front of. `Content Board Curator` fetches that same file rather than keeping its
own copy, because the ceiling is one policy for both queues and two values would be two
things to keep in step. `board_intake.json` carries only board-specific settings.

### D7. The TTL pass skips the ceiling's rows

`build_expire_rows` owns the hook TTL, the per-category cap and displacement, and it only
touches `ORIGIN=AUTO` `QUEUE` rows. A row past the ceiling is `build_cancel_rows`' job, so
`build_expire_rows` returns early and never emits it. Without the skip both passes would select
the same row on the same run and two sheet writes — `EXPIRED` and `CANCELED` — would race, with
the last write winning.

That skip MUST be measured on the ceiling's own clock, the row's `UPDATE_DATE`, not on the
`PUBLISHED_AT` the TTL check uses. `build_expire_rows` measures staleness from `PUBLISHED_AT` on
purpose (a launch note is stale ten days after the launch), so a first version that skipped on
that same age let a row escape both passes: an old article rewritten recently is past the
ceiling by `PUBLISHED_AT`, so it was skipped there, while its recent `UPDATE_DATE` keeps it off
the cancel pass — and the hook TTL that would have retired it is never applied. Two clocks for
one boundary is the bug; `test_the_expire_pass_skips_on_the_ceilings_own_clock` pins it.

## Risks

- **The export may be behind live.** The curator export is the nightly backup's output;
  live was read on 2026-10-18 and its node-name set matches the export, but the apply step
  must re-read live, diff, and apply field-level edits, not post the export.
- **The GitHub node's parameter shape is [UNVERIFIED] against a live call.** The
  operation name and filter fields were read from the installed image's own node schema,
  which is the best available offline evidence, but only a live run proves the filter
  actually restricts to the label. The tasks make that a verification step.
- **The 7-day ceiling is deliberately shorter than every hook TTL** (10–60 days), so it,
  and not the TTL, is what actually retires a queued post. That is the intent — a row that
  has waited a week has lost its slot to newer material — but it means the durable-backlog
  depth the TTL was sized for is no longer reachable, and a quiet fortnight can leave the
  post queue thin. The value is one config edit; watch `Backlog before/after` in the
  curator's digest.
- **A new create body carries no `activeVersion`.** The invariant test that compares the
  two copies skips it until it is applied and backed up, so until then nothing offline
  checks the live graph against the file. Recorded in the tasks as the apply follow-up.
- **Two records of the same morning.** The curator posts its own Slack digest; the board
  curator posts a second one. Distinct channels would hide one of them, so both go to
  `workflows`.

## Open questions

- **Does the existing `GitHub account` credential reach the board?** The board is a public
  repository and the read needs no scope, but the credential in n8n is not inspected here.
  [UNVERIFIED] until the first live run.
- **Should the ceiling also apply to a board issue that predates the label?** Today only
  labelled open issues are read; an unlabelled idea is invisible to the intake by design.
  Left as a board-discipline question, not a code one.

## Definition of done

- `openspec validate --all` passes with this change present.
- `uv run -- pytest agents/n8n/scripts/ -q` passes, and `test_content_board_curator.py`
  fails with either workflow reverted.
- The board curator's graph is tidy by the repository's own invariants (both copies as far
  as they exist, no isolated node, every `$('node')` resolves, `errorWorkflow` resolves).
- `curator_config.json` and `board_intake.json` are valid JSON and the ceiling is one value.
- The apply follow-up (live, owner-approved) reads each workflow back and diffs it against
  the export, and confirms the GitHub filter by reading which issues a run imported.
