# Proposal

## Why

The homelab keeps its post ideas on the GitHub board: open issues labelled `post` in
`datahub-local/datahub-local`. Nothing reads it. An idea has to be typed into the
`content_planner` sheet by hand before either publishing lane can see it, so the board and
the queues drift — the board is where a person actually parks an idea, and the sheet is
where work has to appear.

The two queues also only ever grow. A row that a run claimed and never finished, or an
approval nobody answered, stays in play forever: the curator's TTL is per-hook and runs
10–60 days, so nothing retires a row inside a week, and the article queue has no
retirement rule at all. A stale row is indistinguishable from a fresh one when it is
picked up next, and a stuck `IN_PROGRESS` claim can starve fresh work.

## What Changes

- **A new `Content Board Curator` workflow** (daily 12:15) reads the board and imports
  every open issue labelled `post` that the article queue does not already carry: one
  `article_queue` row per issue, `ENTRY_ID` `gh-<number>`, the issue title as `TOPIC`,
  the body as `DESCRIPTION`, the issue URL as `LINK`, and the lane's defaults for
  `CATEGORIES` / `ASSET_TYPES` / `MAX_WORDS` / `PRIORITY`, `ORIGIN=BOARD`,
  `STATUS=QUEUE`. The read is **read-only** — the board is never labelled, commented on
  or closed — and dedupe is by `ENTRY_ID` and `LINK`, so an issue stays open until a
  human closes it and is still imported exactly once.
- **A one-week ceiling on both queues.** Any row still in play — `QUEUE`, `IN_PROGRESS`
  or `WAITING_APPROVAL` — whose last update is older than the configured number of days
  is cancelled. `Content Feed Curator` cancels `content_queue` rows (this lane spells it
  `CANCELED`); the new workflow cancels `article_queue` rows (`STATUS=CANCELLED` and
  `ARTICLE_STATUS=CANCELLED`, which is what stops the article lane resuming a claim it
  never finished). Terminal rows are never touched.
- **One configurable value, one exclusion.** `cancel_after_days` (default 7) lives in
  `datasets/curator_config.json` and is read by both workflows, so there is one ceiling
  rather than two. The curator's TTL pass skips every row past the ceiling, so the two
  passes never write the same row.
- **A new `datasets/board_intake.json`** holds the board (owner, repo, label, state) and
  the defaults an imported row carries, so a new label or default is a config edit rather
  than a workflow edit.

## Capabilities

### New Capabilities

- `content-backlog`: how a row enters the two publishing queues and when one leaves. The
  board is one intake into `article_queue` without a human retyping it; the age ceiling is
  the one retirement rule both queues share, for rows still in play.

### Modified Capabilities

<!-- None. The post and article lanes are unchanged; only where their rows come from and
     when a stuck one is retired. -->

## Impact

- **`agents/n8n/workflows/content_board_curator.workflow.json`** (new): authored as a create
  body (name, nodes, connections, settings), then created live on 2026-10-18 as
  `RCSPaKMKsckAnJ9B` and activated. The committed file stays a create body until the nightly
  backup rewrites it as a full export, so it carries no id or `activeVersion`. It points
  `settings.errorWorkflow` at the existing `Catch Errors` and carries a manual trigger beside
  the schedule so a run can be forced from the editor.
- **`agents/n8n/workflows/content_feed_curator.workflow.json`**: two nodes added
  (`build_cancel_rows`, `cancel_stale_queue`), `if_write_to_sheet` fans out to the new
  pass, and `build_expire_rows` skips rows past the ceiling.
- **`agents/n8n/datasets/board_intake.json`** (new) and **`curator_config.json`**
  (`cancel_after_days` added).
- **`agents/n8n/scripts/test_content_board_curator.py`** (new): the graph, the config and
  both Code nodes' decisions, executed against stubs.
- **GitHub**: the existing `GitHub account` credential is reused; the board is a public
  repository, so no new scope is expected. [UNVERIFIED] until a live run reads it.
- **`article_queue`** (cross-change): its columns are `add-content-writer-agent`'s. A
  board row carries the same fields a hand-authored row does.
- **No live apply** in this change. Applying the new workflow and backing it up are a
  follow-up with the owner's go-ahead, per the repository rule that a source edit nothing
  reconciles is not done when it is merged.

## Non-Goals

- Writing to the board. No label, comment, close, or project-field change.
- Classifying or judging a board idea. A person put it on the board, so it enters the
  queue as it is; the article lane's own review is what judges the draft.
- Changing the article lane, the post lane, or their prompts.
- Making the ceiling replace the per-hook TTL. TTL and the caps still decide which
  *publishable* rows stay; the ceiling only retires a row that has stopped moving.
