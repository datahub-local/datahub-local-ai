# Tasks

## 1. The article lane

- [x] 1.1 `article_content_writer.workflow.json`, `execute_article_creator`: map `PREVIOUS_DRAFT` as
  `$('execute_article_creator').isExecuted ? ($('execute_article_creator').last().json.text || "") : ""`,
  and add it to the node's `workflowInputs.schema`. Both graph copies. **Landed.**
- [x] 1.2 `article_creator.workflow.json`, `main_trigger`: declare `PREVIOUS_DRAFT`. Both graph copies.
  **Landed.**
- [x] 1.3 `article_creator.workflow.json`, `download_article_prompt`: `PREVIOUS_DRAFT` falls back to
  `$('main_trigger').first().json.PREVIOUS_DRAFT || ""` when `parse_article` has not run. Both copies.
  **Landed.**
- [x] 1.4 `agents/n8n/scripts/test_article_entry_point.py`:
  `test_the_human_retry_passes_the_draft_the_human_rejected` — the retry edge re-enters the call node,
  the mapping reads that node's own last run, guarded by `isExecuted`, never `.item`/`.first()`.
  **Landed.**
- [x] 1.5 `agents/n8n/scripts/test_article_prompts.py`: `PREVIOUS_DRAFT` joined `TRIGGER_VARS`, and
  `test_the_human_retry_falls_back_to_the_draft_the_caller_sent` asserts the fallback and that the
  in-run read still wins. **Landed.**

## 2. The LinkedIn lane

- [x] 2.1 `linked_in_post_sharing.workflow.json`, `execute_post_creator`: `PREVIOUS_POST` mapped from
  the call node's own last run, plus the schema entry. Both copies. **Landed** — the image call in the
  same file is untouched, asserted in the test.
- [x] 2.2 `linked_in_post_creator.workflow.json`, `main_trigger` declares `PREVIOUS_POST` and
  `download_post_prompt` falls back to it. Both copies. **Landed.**
- [x] 2.3 `agents/n8n/scripts/test_linkedin_post_review_gate.py`: the sharing side's mapping, and the
  `PREVIOUS_POST` fallback. **Landed.**

## 3. Offline gates

- [x] 3.1 Prove the new cases fail without the change: stash the four exports, run, record, restore.
  **Landed.** With the exports at HEAD the three touched files report **7 failed, 66 passed** — every
  new case (the article mapping, the article fallback, the post fallback in both copies, the sharing
  mapping in both copies) plus `test_creator_declares_every_input_the_entry_point_sends` on the moved
  `TRIGGER_VARS`. Restored: all pass.
- [x] 3.2 Run the gates and record the result. **Landed.** `uv run -- pytest agents/n8n/scripts/ -q`:
  **591 passed, 1 skipped** (585 cases before this change, +6 new). `ruff check agents/n8n/` reports
  one error, pre-existing and unrelated (`FURB167` in `test_visual_studio_registry.py`).
  `openspec validate --all`: 16 passed.

## 4. Apply to the live instance

- [x] 4.1 Ask the owner before writing, presenting the diffs. Graph only — no prompt file changed, so
  no push order applies. **Landed** — the owner chose to apply all four.
- [x] 4.2 Apply `Article Creator`, `Article Content Writer`, `LinkedIn Post Creator` and
  `LinkedIn Post Sharing` with `--changes` and `--require-edge`, re-read each and diff against the
  exports. **Landed 2026-10-18.** Eight guards held (two per workflow). Before writing, live was
  compared field by field against the intended values: **the only delta in every touched field was
  the added one** — no live-only key would have been reverted by setting a whole mapping or schema
  array. Both writes landed per workflow, and a re-run reports `nothing to change`. The first dry run
  aborted on one guard (`download_article_prompt -> create_article_ai` is not the live edge; it
  fetches `download_system_prompt`), which is the guard doing its job.
- [x] 4.3 Confirm `active` is unchanged on each, and that the published version of the active
  sub-workflows carries the edit. **Landed.** `Article Creator` `True`, `LinkedIn Post Creator`
  `True`, `LinkedIn Post Sharing` `True`, `Article Content Writer` `False` — all unchanged, and the
  three active ones carry the new field in `activeVersion` as well as in the draft. The entry point
  has no `activeVersion` at all (it was deactivated), and its runs are manual from the editor, which
  executes the draft graph.

## 5. Behaviour

- [ ] 5.1 Drive one article human retry and read the retry's `download_article_prompt` output: the
  previous-draft block carries the draft, and the new draft keeps what the feedback did not name.
  **Superseded** by `add-article-audience-and-improvement-pass`: the article human retry no longer
  re-enters `execute_article_creator` at all — its edge goes to `build_improvement_context`, which
  is handed the draft of record (`select_final_draft`'s own last run, else the stored
  `article_drafts` row), so the sub-workflow's caller-side `PREVIOUS_DRAFT` mapping is removed and
  this behaviour is exercised by that change's 6.2 instead. The requirement itself still holds
  (a human retry is handed the draft the human rejected), with the improvement pass as receiver;
  the LinkedIn half of this change is untouched.

## 6. Documentation

- [x] 6.1 Record in `AGENTS.md`: the human retry regenerated from scratch, why (the draft lives inside
  one invocation), the run 14178 measurements, the probe that proved a node reads its own earlier
  runs, and that no prompt file changed so no push order applies. **Landed** beside the retry
  paragraph in the `#### Article Creator` subsection.
- [x] 6.2 Archive once 4.2 and 5.1 have landed:
  `openspec archive carry-the-draft-into-the-human-retry`.
