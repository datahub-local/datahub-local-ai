# Proposal

## Why

The article gate enforces `MAX_WORDS` exactly, and a drafting model cannot count words. Row 3
(`2026-10-30`) died on it: four drafts, every other check passed, the last one **1248 words against
`MAX_WORDS=1200`** — 48 words, 4% — and the run ended `MAX_RETRIES_EXCEEDED` with no article. The
count is right and stays in code; what was wrong is treating a 4% counting slip as a rule violation.

The cost is asymmetric. A draft 4% long is an article. A rejected run is a lost article, four model
calls and a human noticing.

## What Changes

- **The gate allows a 10% counting margin.** `parse_article` (drafting) and `check_improved_draft`
  (improvement re-check) compute `limit = ceil(MAX_WORDS * 1.1)` and reject only past it, reporting
  the limit the retry must cut to.
- **The reviewer is told the same limit.** `article_review.md` reads `{{ WORD_LIMIT }}` instead of
  `{{ MAX_WORDS }}` in its length check, because a reviewer rejecting at 1200 would reject a draft
  the code accepts — and its `true` is required for acceptance.
- **What the writer is told does not change.** `article_writer.md` and `article_improver.md` still
  aim at `MAX_WORDS`; the margin is a tolerance on the gate, not a longer article.

## Capabilities

### Modified Capabilities

- `content-writer`: the length budget is enforced with a counting margin rather than exactly.

## Impact

- `agents/n8n/workflows/article_creator.workflow.json` — `parse_article` and the review prompt's
  vars, both graph copies.
- `agents/n8n/workflows/article_content_writer.workflow.json` — `check_improved_draft`, both copies.
- `agents/n8n/prompts/article_review.md` — the length check names the limit.
- `agents/n8n/scripts/` — the margin, its boundary and the prompt/code agreement.
- **Not changed**: the drafting budget in the writer and improver prompts, `MAX_WORDS` on the row,
  `MAX_TRIES`, the improvement pass's one-retry-then-fall-back behaviour.
