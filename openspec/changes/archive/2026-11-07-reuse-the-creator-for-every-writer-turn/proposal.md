# Proposal

## Why

Owner instruction, 2026-11-07: the entry point must reuse the `Article Creator` sub-workflow
instead of posting to the writer adapter itself. After
`2026-11-07-move-all-article-turns-into-the-writer`, the drafting and review turns went through
`execute_article_creator`, but the aspect and edit turns were still two direct HTTP nodes in
`Article Content Writer`. The owner read those calls as a bypass: one writer, two call styles,
and an endpoint that a second workflow had to know.

## What Changes

- **`Article Creator` gains a `TASK` input.** `draft` (the default), `aspects` or `improve`;
  `switch_task` sends the run to the matching branch and an unknown value to `bad_task`, which
  fails instead of spending a draft. `set_workflow_vars` normalises the value and defaults it to
  `draft`, so an existing caller needs no change.
- **The aspect and edit turns move inside the sub-workflow.**
  `build_aspects_request` → `request_aspects` and `build_improve_request` → `request_improve`
  leave `Article Content Writer` and land in `Article Creator`, beside the review turn. One
  `noOp` per branch returns the adapter's response item, so the entry point's parsers keep the
  `statusCode`/`body` shape they already read.
- **The entry point calls the sub-workflow twice more.** `execute_article_aspects` and
  `execute_article_improve` replace the four HTTP nodes and their request builders; they pass the
  draft of record, the merged findings and the objective problem as trigger fields.
- **The entry point loses the writer endpoint.** `build_improvement_context` no longer reads
  `$env.ARTICLE_WRITER_URL` or derives a session id; `Article Creator` owns both for every turn.
- **The deterministic gates stay in the entry point.** `merge_aspect_findings`,
  `check_improved_draft` and `select_final_draft` are unchanged in behaviour: they still parse the
  turn's answer, count the budget and markers in code, and converge every branch.

## Capabilities

`content-writer`.

## Out of scope

- No prompt, adapter or request-schema change: this is the n8n call boundary only.
- No change to the drafting loop, the retry bounds or the human review.
- The live apply is reported separately; the pull request carries the graph change and the
  committed exports.
