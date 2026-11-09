# Proposal

## Why

The owner's model is one writer session per row: the first draft opens it, every rejection and
feedback round continues it, so the writer keeps the pages it read and the asks it already applied.
The previous change gave each attempt a session of its own to keep the transcript small, and a
retry then re-drafted from the row and the newest feedback alone — on 2026-11-09 that replaced a
whole walk-through with a provider how-to and lost the examples the owner had asked for.

## What Changes

- **One session per row.** The session id is `article-<row>` again, for the row's whole life.
- **The draft of record travels with the turn.** `DRAFT_TEXT` / `DRAFT_TITLE` still ride on the
  request, so a turn whose session is missing still edits the draft the person read.
- **The accepted cost.** A long row's transcript keeps growing and a turn gets slower; the
  compaction trigger and the derived ledger already handle it, and the alternative loses context.

## Capabilities

- `content-writer`

## Impact

- `agents/n8n/workflows/article_creator.workflow.json` and the live workflow.
- No adapter change; the image does not rebuild.

## Non-goals

- No change to the one-turn gate, the block rule or the human review.
