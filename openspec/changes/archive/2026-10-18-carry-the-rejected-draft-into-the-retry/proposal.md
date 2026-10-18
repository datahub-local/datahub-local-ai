# Proposal

## Why

A retry regenerates its draft from scratch instead of editing the one that was rejected. Both review
loops re-render the drafting prompt with the reviewer's reason and nothing else: the rejected draft
is not passed back, so a model told to *"Remove or rewrite the closing paragraph"* and *"Cut 39
words"* has no draft to remove from or cut — it has to write a new one, and every reason to go
looking for material again.

That is what a live test on 2026-10-18 did. The over-budget first draft was retried correctly
(`OVER_BUDGET: 1239 words against MAX_WORDS=1200`), and the retry turn then called `research_sources`
with the same query `"Sympozium"` **seven times** and `read_page` on the same page **six times** —
13 tool calls, 16 model calls — until the drafting agent answered `Max iterations (12) reached`
(executions 14018, 14020). The run was lost. The same shape had already happened at
`maxIterations: 8` on 2026-10-16 (execution 13603: 16 tool calls, the same error), so the iteration
bound is not what stops it — it only decides how long the spiral lasts, and lowering it would kill
legitimate turns, because every model failure inside the agent loop spends an iteration
(`ai_model` failed 3× in 13603 and 2× in 14020).

The first turn behaved: two tool calls and a draft. The retry is where the behaviour changes, and
the only thing the retry has that the first turn does not is the reviewer's reason — an instruction
to edit a draft it was never given.

`LinkedIn Post Creator` has the same gap in the same place. Its retry re-renders
`prompts/linkedin_post.md` with the reviewer's `<explanation>` and no previous post, so it also
rewrites from scratch while being told to apply changes to a draft it cannot see.

## What Changes

- **The rejected draft is carried into the retry, in both lanes.** `download_article_prompt` passes
  the draft the review just rejected as `PREVIOUS_DRAFT`, read with `.last()` so the loop's
  paired-item lineage cannot resolve it to `undefined` (the 2026-09-30 `VARIETY_DIRECTIVES` failure
  in the LinkedIn lane), and guarded by `isExecuted` so the first attempt renders an empty block.
  `download_post_prompt` does the same as `PREVIOUS_POST` from `parse_llm_output`.
- **Both drafting prompts say what to do with it.** A new section names the draft, says the retry
  edits it — keep what the review did not object to, change only what the feedback names — and, in
  the article prompt, says a retry does not research again: the source material is what it has.
- **Not changed:** `maxIterations` stays 12. The bound is not the fix, and 8 is a measured floor.

## Capabilities

### Modified Capabilities

- `content-writer`: a rejected draft is carried into the retry, which edits it.
- `linkedin-post-publishing`: the same, for the post lane.

## Impact

- **`agents/n8n/workflows/article_creator.workflow.json`**: `download_article_prompt` gains one
  template var. Both graph copies.
- **`agents/n8n/workflows/linked_in_post_creator.workflow.json`**: `download_post_prompt` gains one
  template var. Both graph copies.
- **`agents/n8n/prompts/article_writer.md`** and **`agents/n8n/prompts/linkedin_post.md`**: a
  section each. Fetched from GitHub `main`, so those halves are live on push — and a pushed prompt
  with a placeholder the graph does not pass stops every run, which is why the two halves are
  asserted against each other offline before the push.
- **Not changed**: the review prompts, the review loop's bound, `MAX_TRIES`, the tools, and the
  `Source:`/`Source here:` line requirements.
- **`read_page` not echoing the URL it read** is recorded as a finding, not fixed: it is a different
  workflow (`Download Content`, shared with other callers) and wants its own measurement.
