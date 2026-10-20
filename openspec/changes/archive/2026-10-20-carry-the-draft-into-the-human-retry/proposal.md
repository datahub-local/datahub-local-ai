# Proposal

## Why

A **human** retry regenerates the draft instead of editing the one that was rejected, in both lanes.

`PREVIOUS_DRAFT` is `$('parse_article').isExecuted ? $('parse_article').last().json.TEXT : ""` inside
`Article Creator`, and `PREVIOUS_POST` is the same shape inside `LinkedIn Post Creator`. Both only
span **one invocation** of the sub-workflow. A human retry is a *new* invocation — the approval
switch loops back into the same `executeWorkflow` node — so `parse_article` / `parse_llm_output` have
not run, the block renders empty, and both prompts then say *"When the block is empty this is the
first attempt: write a fresh draft."* The feedback arrives; the draft does not. The 2026-10-18 change
(`carry-the-rejected-draft-into-the-retry`) wired the internal review loop and left this one.

Measured on run 14178 (`Article Content Writer`, still `waiting`), an introduction to Sympozium:

| execution | what it is | `## Previous Draft` in the drafting prompt |
| --- | --- | --- |
| 14180 attempt 0 | first authoring | empty (correct) |
| 14180 attempt 1 | internal reviewer retry | the rejected draft, 24,675-char prompt |
| 14187 | human feedback: "Make it simpler and for everyone…" | **empty** |
| 14191 | human feedback: "Features: i would like a top 5 features" | **empty** |

Both human rounds wrote a fresh draft. Round 2 asked for one section; there is no reason for the
other eleven paragraphs to change.

## What Changes

- **The entry point passes the draft the human read.** On the retry edge, the sub-workflow's own
  previous run is the draft that was approved on screen: `$('execute_article_creator').last().json.text`
  in the article lane, `$('execute_post_creator').last().json.text` in the post lane, guarded by
  `isExecuted` so the first pass sends nothing.
- **The sub-workflow prefers the in-run draft and falls back to the caller's.** `PREVIOUS_DRAFT`
  becomes `parse_article.isExecuted ? parse_article.last().TEXT : main_trigger.PREVIOUS_DRAFT`, so the
  internal review loop behaves exactly as it does today and the human retry stops writing from
  scratch. Same for `PREVIOUS_POST` with `parse_llm_output`.
- **No prompt file changes.** Both prompts already declare the placeholder, already say the block is
  the draft to edit, and already say a retry does not research again — `article_writer.md` and
  `linkedin_post.md` need no edit, so there is no push-order window to manage this time.

## Capabilities

### Modified Capabilities

- `content-writer`: a human retry edits the draft the human rejected, not a fresh one.
- `linkedin-post-publishing`: the same, for the post lane.

## Impact

- **`agents/n8n/workflows/article_content_writer.workflow.json`** and
  **`agents/n8n/workflows/linked_in_post_sharing.workflow.json`**: the sub-workflow call node gains
  one mapped field. Both graph copies.
- **`agents/n8n/workflows/article_creator.workflow.json`** and
  **`agents/n8n/workflows/linked_in_post_creator.workflow.json`**: the trigger declares the new input
  and `download_*_prompt` gains the fallback. Both graph copies.
- **`agents/n8n/scripts/`**: the entry-point side of the contract gains a case in each lane — nothing
  asserted it, which is why the empty block went unnoticed.
- **Not changed**: the prompts, the internal review loops, `MAX_TRIES` / `maxIterations`, the
  `article_drafts` DataTable, and the post lane's (absent) storage. The draft travels in the run.
