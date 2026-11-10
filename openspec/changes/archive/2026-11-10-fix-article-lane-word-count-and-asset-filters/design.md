# Design

## Context

The article lane has two ownership boundaries. The Pi writer owns the prose and the files and runs in
a sandbox with a shell; the server owns every fact about the output (paths, the ledger, the word
count). The n8n graph owns the row state and the asset table. Both failures are a fact owned by one
side that the other side could not read.

## Gate findings

- `parse_article` already computed `limit = Math.ceil(max * 11 / 10)` and `words` from the body
  (markers stripped), and the adapter's `articleWordLimit` / `articleWordCount` are the same rule.
  The number existed; it was only ever sent back as a rejection string after the turn had finished.
- The base image is `node:22-bookworm-slim`: `wc`, `grep`, `awk`, `sed` are present, `jq` is
  installed by the Dockerfile, and `rg` was not — while `article_audit.md` tells the auditor `rg` is
  installed.
- `data_table_user_1eE2kWVNSlS1fM25` (live, via the n8n Postgres) held two `svg_wide` rows for
  `gh-80` and no `image_wide` row. Execution 16320 ran `store_assets` with only `svg_wide` and the
  gate reported `image_wide=MISSING`. The Data Table node source sets `matchType` default to
  `anyCondition`; none of the four two-condition nodes wrote it, and the upsert updates every
  matching row.

## Decisions

- **Expose the count in the turn, not a trim turn on the server.** The writer already runs
  `check-article` for its fences; the budget is one more line on the same command and one more
  instruction to cut until it passes. A server-side corrective turn would spend a second model turn
  (minutes) on every over-budget draft and still depend on the model counting.
- **The limit, not the budget, is printed.** The gate rejects past `ceil(MAX_WORDS * 1.1)`; printing
  `MAX_WORDS` would make the writer cut more than the gate needs and would disagree with
  `article_review.md`, which is already told `{{ WORD_LIMIT }}`.
- **The budget rides on the turn's env, not a file.** The run directory outlives a row edit, and a
  stale `budget.json` would survive a retry with a changed `MAX_WORDS`; env is per turn by
  construction.
- **`wc -w` is named but not trusted.** It counts the H1 and the marker words, so the prompt says it
  is a rough guide and `check-article` is the number the gate uses.
- **`matchType: allConditions` on the four nodes only.** A single-condition filter has nothing to
  combine; adding the field everywhere would be noise.

## Risks

- A writer can still ignore `check-article`, exactly as it can ignore the fence check. The gate is
  unchanged, so the worst case is the old behaviour, and the prompt now names the failure it must
  fix before answering.
- The image must be rebuilt and its digest pinned before the prompt change reaches the cluster; the
  n8n `matchType` fix is live already and independent of it.

## Open questions

- None blocking. Whether a future retry should be handed the *count* rather than a whole new draft
  is a cost question for the writer lane, not a correctness one.

## Definition of done

- A 120-word body against `MAX_WORDS=100` makes `check-article` exit 1 and print
  `WORDS: 120 of 110 (budget 100) — cut at least 10 words`; 100 words passes; no budget prints no
  `WORDS:` line and does not fail.
- The four Data Table nodes carry `matchType: allConditions` in the export and in the live workflow.
- `node --test 'agents/adapters/pi-writer/test/*.test.mjs'` passes, and `openspec validate --all`
  passes.
