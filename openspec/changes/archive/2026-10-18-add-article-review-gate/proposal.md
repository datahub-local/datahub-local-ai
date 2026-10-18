# Proposal

## Why

`Article Creator` returns its first draft. Nothing reviews it, and the one check it does make is
fatal: `parse_article` reports `OVER_BUDGET` as data, the entry point's `check_draft_error` reads a
non-empty `ERROR` as a hard failure, and the run ends having spent the model time and produced
nothing. Execution 13849 on 2026-10-17 is the case: the draft ran 1276 words against
`MAX_WORDS=1200`, `parse_article` reported `OVER_BUDGET: 1276 words against MAX_WORDS=1200`, and
the reason came back as the answer with no second attempt. Executions 13622 (369 against 350) and
13491 (331 against 50) are the same shape. The proposal first cited 13844; re-read live on
2026-10-18, that execution is an *authorization* failure in `create_article_ai`
(`Authorization failed - please check your credentials`) which produced no draft at all, so it is
not evidence for this change. The same is true of every other rule the draft can break — the
review state on the row is a human's, and there is no automated pass between the writer and the
reviewer.

`LinkedIn Post Creator` already has the shape this needs and has carried it since 2026-09-30: a
second model pass (`check_rules_llm`) reviews the draft against the committed rules, a rejection
re-renders the drafting prompt carrying the gate's own `<explanation>`, and the loop is bounded by
`MAX_TRIES` so a draft that cannot be satisfied reports `MAX_RETRIES_EXCEEDED: <reason>` instead of
spinning. The article lane has no equivalent, so an over-budget or off-rules draft is a dead run.

## What Changes

- Add a bounded review-and-retry loop to `Article Creator`, mirroring `LinkedIn Post Creator`:
  the draft is reviewed by a second model pass against the **same** committed rules file the
  writer followed (`prompts/article_writer_system.md`, fetched once), a rejection returns through
  `download_article_prompt` with the reviewer's reason in the Reviewer Feedback block, and the
  loop is bounded by `MAX_TRIES` (3).
- Make an over-budget draft retryable rather than fatal. `parse_article` keeps computing the count
  in code — a count asked of a model is a count that gets invented — but reports it as `PROBLEM`
  data; `merge_article_verdict` rejects the draft on that problem whatever the reviewer said, and
  the reason names the real numbers. Only an exhausted loop reports `MAX_RETRIES_EXCEEDED`.
- Add `prompts/article_review.md`, the reviewer's task prompt, and assert its placeholders equal
  what `Article Creator` passes, the way `prompts/article_writer.md` is already guarded.
- Correct the hero marker instruction in `prompts/article_writer.md`: it hardcoded
  `<!-- asset:image -->`, which no row requests now that the wide pair exists (`image_wide`). The
  publish step hid it by placing the hero at its fallback position, but a marker check in the new
  gate would reject every draft, so the marker is now the requested type's own id.

## Capabilities

### New Capabilities

<!-- None. -->

### Modified Capabilities

- `content-writer`: a new requirement — a draft is reviewed by a second pass against the rules the
  writer followed, and regenerated from the reviewer's reason until it satisfies them or the
  attempt bound is reached.

## Impact

- **`agents/n8n/workflows/article_creator.workflow.json`**: six nodes added
  (`download_article_review_prompt`, `check_article_llm`, `parse_article_check_output`,
  `merge_article_verdict`, `switch_article_check`, `set_error_max_tries`), `parse_article` reports
  `PROBLEM` instead of a fatal `ERROR`, `set_output` clears `ERROR` on the accepted branch,
  `set_workflow_vars` gains `MAX_TRIES`, and the drafting prompt node carries the gate reason. Both
  graph copies are edited. Per the repo rule the export is the backup's output, so the change is
  live only once applied with `scripts/apply_workflow_changes.py`.
- **`agents/n8n/prompts/article_review.md`** (new) and **`agents/n8n/prompts/article_writer.md`**
  (the marker line). Both are fetched from GitHub `main`, so those halves are live on push.
- **Not changed**: the entry point (`check_draft_error` still reads a non-empty `ERROR`, which now
  only an exhausted loop sets), `Article Creator`'s inputs, `settings.errorWorkflow` (a sub-workflow
  leaves it unset), the model nodes, and `datahub-local-core`.
