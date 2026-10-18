# Tasks

## 1. The article lane

- [ ] 1.1 `prompts/article_writer.md` gains a Previous Draft section carrying `{{ PREVIOUS_DRAFT }}`:
  what it is, that a retry edits it and keeps what the review did not object to, that a retry does
  not research again, and that an empty block means the first attempt.
- [ ] 1.2 `download_article_prompt` supplies `PREVIOUS_DRAFT` as
  `$('parse_article').isExecuted ? $('parse_article').last().json.TEXT : ""` — `.last()` for the
  draft just rejected, never `.item`. Both graph copies.
- [ ] 1.3 `agents/n8n/scripts/test_article_prompts.py`: add `PREVIOUS_DRAFT` to `CALLER_VARS`, and a
  case asserting the node's expression reads `parse_article` with `.last()` and is guarded by
  `isExecuted` — the two properties no offline case can see from the prompt alone.

## 2. The LinkedIn lane

- [ ] 2.1 `prompts/linkedin_post.md` gains a Previous Post section carrying `{{ PREVIOUS_POST }}`
  with the same shape of instruction, and the Final Pass runs over the edited post.
- [ ] 2.2 `download_post_prompt` supplies `PREVIOUS_POST` as
  `$('parse_llm_output').isExecuted ? $('parse_llm_output').last().json.result : ""`. Both graph
  copies.
- [ ] 2.3 `agents/n8n/scripts/test_linkedin_post_review_gate.py`: add a case holding the prompt's
  placeholders to the vars the node supplies — the guard the article lane already has and this one
  does not — plus the `.last()`/`isExecuted` properties for `PREVIOUS_POST`.

## 3. Offline gates

- [x] 3.1 Prove the new cases fail without the change: revert each export to HEAD, run, record the
  failures, restore.
  **Landed.** With both exports at HEAD, all three cases fail: the article one on
  `PREVIOUS_DRAFT` absent from the node's vars, and both LinkedIn copies on the placeholder sets
  disagreeing (`Extra items in the right set: 'PREVIOUS_POST'`). Restored: all pass.
- [x] 3.2 Run the gates and record the result: both touched test files, `test_code_nodes_parse.py`,
  `test_workflow_invariants.py`, `test_linkedin_post_review_gate.py`, then the whole
  `agents/n8n/scripts/` suite and `ruff`.
  **Landed.** Full suite **543 passed** (540 before this change). `ruff` reports one error,
  pre-existing and unrelated (`FURB167` in `test_visual_studio_registry.py`).

## 4. Apply to the live instance

- [ ] 4.1 Ask the owner before writing, presenting both diffs. **The graph goes first and the push
  second** — the reverse order is a window in which the pushed prompt names a placeholder the
  graph does not pass, and `DownloadTemplate` stops every run in that window. A graph that passes a
  var the prompt does not use is harmless, so apply, then push.
- [ ] 4.2 Apply `Article Creator` and `LinkedIn Post Creator` with `--changes` and `--require-edge`,
  then re-read both and diff against the exports.
- [ ] 4.3 Confirm both workflows stay `active`, and that the published version carries the edit —
  the article path runs the published sub-workflow, not the draft.

## 5. Behaviour

- [ ] 5.1 Drive one article retry and read the run's own `download_article_prompt` output on the
  retry attempt: the previous-draft block carries the rejected draft, and the turn writes instead of
  searching. This is the one property no offline case can show.
- [ ] 5.2 Record what the retry cost, against the thirteen tool calls execution 14020 spent.

## 6. Documentation

- [ ] 6.1 Record in `AGENTS.md`: the retry carries the rejected draft in both lanes, the `.last()`
  reason, and the finding that the drafting agent's iteration bound is a cost cap rather than a
  spiral fix (13603 at 8, 14020 at 12).
- [ ] 6.2 Record the manual-execution fact in the n8n section: n8n does not invoke
  `settings.errorWorkflow` for a manual execution, so a manual test that fails is silent — which is
  why `Article Content Writer Error` has never run.
- [ ] 6.3 Archive when both graphs are live, the prompts are pushed and 5.1 has run:
  `openspec archive carry-the-rejected-draft-into-the-retry`.
