# Proposal

## Why

The lane now authors one turn per attempt, but `Article Creator` still ran an `audit` turn between
the parser and the branch — a second model call that could reject a draft the code gate had passed.
On 2026-11-09 it did: attempt 2 passed every counted check and was rejected by the audit, costing a
third seven-minute draft.

## What Changes

- **The parser's verdict is the branch.** A `gate_verdict` node reads `PROBLEM` and decides accept
  or retry; the review chain (`build_review_request`, `request_review`, `parse_review_verdict`,
  `merge_article_verdict`) is removed from the graph.
- **The reason still travels.** A rejection's explanation is the gate's problem, so the retry keeps
  carrying the real cause.
- **The tasks stay.** `review` and `audit` remain on the adapter for on-demand use.

## Capabilities

- `content-writer`

## Impact

- `agents/n8n/workflows/article_creator.workflow.json` and the live workflow.
- No adapter change; the image does not rebuild.

## Non-goals

- No change to the code gate's checks, the budget, the markers or the human review.
