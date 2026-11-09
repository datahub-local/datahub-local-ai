# Proposal

## Why

Ten fixes moved the same failure instead of removing it. The gate accepted a fenced block only as
a **byte-for-byte** copy of a scraped page, while an article about a product shows resources the
docs *describe*. Every draft therefore ended the same way: compose YAML, get `UNQUOTED`, and — with
the audit, the aspect pass and the re-check all teaching the model to avoid the rejection — delete
the fence and publish an article with no code.

The round had four model turns, each with its own timeout and its own failure: draft, audit, three
aspect reviewers, edit. Three of the last six failed runs failed at one of those seams, not in the
draft. And every attempt continued the same Pi session, which grew past 7 MB, so compaction
dropped the pages the ledger depends on and a turn took half an hour.

## What Changes

- **Verify a block by its names.** A block is accepted when it is a byte copy of a page (unchanged)
  or when **every name it uses** — field, flag, image, kind, object name — appears on a page the
  session read. An invented name still fails, and the reason names it.
- **One authoring turn.** The lane calls the writer once, gates the answer in code, and presents it.
  The audit, the aspect pass and the edit are out of the automatic path.
- **One retry, in a fresh session.** A rejected draft is retried once, in its own session, carrying
  the previous draft and the gate's reason; no 7 MB context, no compaction losing evidence.
- **The gate trusts the ledger's mode.** `parse_article` accepts a `derived` entry by its names and
  keeps the excerpt comparison for `quoted` ones.

## Capabilities

- `content-writer`

## Impact

- `agents/adapters/pi-writer/`: `session-lib.mjs` (name extraction and verification),
  `session-server.mjs`, `prompts/writing.md`, `prompts/article_audit.md`,
  `prompts/article_improver.md`, `bin/check-article.mjs`, tests.
- `agents/n8n/workflows/article_content_writer.workflow.json`: the improvement pass is removed
  from the path, `first_draft` replaces `select_final_draft`, the review message drops the
  improvement line.
- `agents/n8n/workflows/article_creator.workflow.json`: `MAX_TRIES` 3 → 2, session id per round
  and attempt.
- No change to the publishing path, the sheet schema or the human review.

## Non-goals

- The audit, aspect and edit tasks stay in the adapter for on-demand use; they are not deleted.
- No change to the word budget, the asset markers or the publishing gate.
