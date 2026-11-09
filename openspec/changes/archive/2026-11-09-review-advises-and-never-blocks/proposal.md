# Proposal

## Why

Eleven commits and six spec changes in six days all moved the same boundary: what makes a fenced
block "sourced". Every new document shape broke the rule — a heredoc, a composed manifest, then a
quoted sentence (`"You are a data analyst."` was read as three names that had to be on a page). Each
false rejection costs a whole round, and the thing the rule protected against, an invented name, is
what a reviewer with the transcript in hand names in one pass.

## What Changes

- **Code gates only counts.** Shape (H1 and a body), the word budget with its margin, the asset
  markers, and transport or session failures. None of these can reject a correct draft.
- **The reviewer decides sourcing.** One audit turn runs after the gate, with the ledger, the
  transcript and the pages. Its findings are shown to the human next to the draft. They cannot
  reject the draft, cannot trigger a retry, and a failed review is a note, not a failed round.
- **The ledger stays data.** `sources.json` and the sheet's `SOURCES` column keep the block-to-page
  map; `check-article` stays as the writer's own pre-answer check.

## Capabilities

- `content-writer`

## Impact

- `agents/adapters/pi-writer/prompts/article_audit.md`: findings are advice, never a blocker.
- `agents/n8n/workflows/article_creator.workflow.json`: `parse_article` stops treating the ledger as
  a problem; `build_review_request` / `request_review` / `review_note` return the audit after the
  gate and before the answer.
- `agents/n8n/workflows/article_content_writer.workflow.json`: the review message carries the
  reviewer's notes.

## Non-goals

- The budget and marker counts stay blocking; they are cheap and deterministic.
- The human review is unchanged apart from receiving the notes.
