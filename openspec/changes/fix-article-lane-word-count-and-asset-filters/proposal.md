# Proposal

## Why

Two failures on 2026-11-10 came from the article lane reading counts and identity from the wrong
place.

**The writer was never given a word count.** The drafting turn is told "at most `MAX_WORDS`" and
nothing else, and a model cannot count prose. Row 4 (execution 16323) produced 1,377 words against a
1,320 limit, and every retry it spent landed past the limit, so the run ended
`MAX_RETRIES_EXCEEDED: OVER_BUDGET: 1377 words against a limit of 1320 (MAX_WORDS=1200)`. The gate
counts in code and is right to; the writer simply had no way to see the number it had to stay under,
even though the writing sandbox has `wc`, `grep` and `jq`.

**An asset upsert rewrote a different asset's row.** n8n 2.47's Data Table node defaults
`matchType` to `anyCondition`, and the four nodes carrying two conditions (`store_assets`,
`mark_asset_approved`, `mark_asset_cancelled`, `record_asset_paths`) never set it. So
`ENTRY_ID = gh-80` **or** `ASSET_TYPE = svg_wide` matched every row for the entry: the `svg_wide`
upsert updated the `image_wide` row and wrote `ASSET_TYPE: svg_wide` into it. The publish gate then
found no `image_wide` row and stopped the run with `image_wide=MISSING` (row 3).

## What Changes

- **The drafting and editing turns get the budget as a number.** The server passes the row's
  `max_words` to the turn as `PI_WRITER_MAX_WORDS`; `check-article` prints
  `WORDS: <n> of <limit> (budget <max>) — cut at least <k> words` using `articleWordCount` and
  `articleWordLimit`, the same functions the gate uses, and exits non-zero when the body is past the
  limit. The prompts require running it before answering and cutting until it passes.
- **The image carries the shell tools the prompts name.** `wc`, `grep` and `jq` were already there;
  `rg` was named by `article_audit.md` and missing, so it is installed.
- **Every multi-condition Data Table filter sets `matchType: allConditions`** in the export and in
  the live instance.

## Capabilities

### Modified Capabilities

- `content-writer`: the drafting turn reports the body's count against the gate's limit before it
  answers, and an asset write is scoped to that asset's own row.

## Impact

- `agents/adapters/pi-writer/session-server.mjs` — the turn budget as a per-turn env var.
- `agents/adapters/pi-writer/bin/check-article.mjs` — the word-count verdict.
- `agents/adapters/pi-writer/prompts/{writing,article_task,article_improver}.md` — run the count and
  cut until inside.
- `agents/adapters/pi-writer/Dockerfile` — `ripgrep`.
- `agents/adapters/pi-writer/test/check-article.test.mjs` — the over/inside/no-budget cases.
- `agents/n8n/workflows/article_content_writer.workflow.json` — the four `matchType` fields, applied
  live in the same change.
- `docs/agent/n8n.md` — the count and the `matchType` trap.

## Non-goals

- No server-side trim turn: the writer fixes its own draft with the count in hand.
- No change to the gate's 10% margin, the row's `MAX_WORDS`, or the retry bound.
- No rewrite of the publish gate: a genuinely missing asset still blocks the commit.
