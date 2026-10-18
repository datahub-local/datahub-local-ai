# Tasks

## 1. The reviewer prompt

- [x] 1.1 Add `agents/n8n/prompts/article_review.md`: the job, the checks (length, asset markers,
  no invented fact or citation, naming, hype, shape, the `Source:` line), the writer's rules as
  `{{ RULES }}`, `{{ EXTRA_PROMPT }}`, the human feedback block, the draft and the source material,
  and the output contract `<output>true|false</output>` + `<explanation>`. ASCII only, no copied
  schema. Fetched from GitHub `main` at run time, so this half needs no apply.
  **Landed.** Twelve placeholders, all supplied by the node in 2.2; the rules are inserted, never
  restated, so the gate and the writer read one file.

- [x] 1.2 Correct the hero marker in `agents/n8n/prompts/article_writer.md`: the hero marker is the
  requested type's own id, not the literal `<!-- asset:image -->`. Required before the gate checks
  markers, because a row requesting `image_wide` matches nothing and would be rejected forever.
  **Landed.** The Asset Markers section now says "the type id verbatim from `{{ ASSET_TYPES }}`";
  `test_task_prompt_documents_the_asset_marker_contract` now asserts the literal `image` is gone.

## 2. The review-and-retry loop

- [x] 2.1 `agents/n8n/workflows/article_creator.workflow.json`: add the six nodes
  (`download_article_review_prompt`, `check_article_llm`, `parse_article_check_output`,
  `merge_article_verdict`, `switch_article_check`, `set_error_max_tries`), rewire
  `parse_article → download_article_review_prompt → check_article_llm → parse_article_check_output →
  merge_article_verdict → switch_article_check`, and give `switch_article_check` the three outputs
  (`set_output`, `set_error_max_tries`, retry → `download_article_prompt`). Both graph copies.
  **Landed.** `check_article_llm` is a `chainLlm` fed by `ai_model`/`ai_model_fallback` at
  `ai_languageModel` index 0/1; `switch_article_check`'s bound is `{{ $runIndex + 1 }} > MAX_TRIES`.

- [x] 2.2 `download_article_review_prompt` fetches `prompts/article_review.md` with exactly the
  placeholders the file declares, `RULES` read from `download_system_prompt` (the writer's own
  file), and the draft fields from `parse_article` by paired item.
  **Landed.** Asserted by `test_review_prompt_placeholders_match_the_call` and
  `test_the_reviewer_reads_the_rules_the_writer_followed`.

- [x] 2.3 `parse_article` reports `PROBLEM` as data instead of a fatal `ERROR`; `set_output` clears
  `ERROR` on the accepted branch; `set_workflow_vars` gains `MAX_TRIES = 3`;
  `download_article_prompt`'s `FEEDBACK` appends the gate's reason on a retry.
  **Landed.** `MAX_WORDS` missing still throws — a caller bug, not a draft to retry.

- [x] 2.4 `merge_article_verdict` combines the reviewer's verdict with the parser's deterministic
  `PROBLEM`, the problem winning, and names the real numbers in the reason.
  **Landed.** Asserted by `test_the_deterministic_budget_beats_the_reviewer` and
  `test_an_over_budget_draft_is_retried_not_raised`.

## 3. Offline gates

- [x] 3.1 Add `agents/n8n/scripts/test_article_review_gate.py`: the retry edge and the reason
  carried into the re-rendered prompt, the `<explanation>` extraction, the `$runIndex + 1` bound,
  the `MAX_RETRIES_EXCEEDED` report, the over-budget-as-data property, the deterministic verdict,
  the shared rules file, the reviewer wired to both models, and the prompt/node placeholder
  equality — over both graph copies.
  **Landed.** 17 cases.

- [x] 3.2 Update `agents/n8n/scripts/test_article_prompts.py` for the marker correction.
  **Landed.** The marker case now asserts `<!-- asset:<id> -->` and that the literal
  `<!-- asset:image -->` is absent.

- [x] 3.3 Run the offline gates and record the result: `test_article_review_gate.py`,
  `test_article_prompts.py`, `test_code_nodes_parse.py`, `test_workflow_invariants.py`,
  `test_workflow_expressions.py`, then the whole `agents/n8n/scripts/` suite.
  **Landed.** Focused set **243 passed, 1 skipped**; full `uv run -- pytest agents/n8n/scripts/ -q`
  **532 passed, 1 skipped**.

- [x] 3.4 Prove the new cases fail without the change: revert `article_creator.workflow.json` to
  HEAD, run `test_article_review_gate.py`, record the failures, restore. A test that passes with the
  loop absent asserts nothing.
  **Landed.** With the export at HEAD: **17 failed** (every case in the file — the loop, the reason
  carry, the bound, the report, the verdict, the shared rules, the model wiring, the placeholder
  equality). Restored: 17 pass.

## 4. Apply to the live instance

- [ ] 4.1 Ask the owner before writing, per the repository rule: present the diff of the graph and
  the two prompt files, and get an explicit answer.
  **Asked 2026-10-18; the answer was "dry run first, then stop".** The diff was presented: live has
  11 nodes against the export's 17, `parse_article → set_output` is replaced by the six-node loop,
  and the two prompt files are already on `origin/main` (4.2).
- [x] 4.2 Push the two prompt files first — `article_review.md` and `article_writer.md` are fetched
  from GitHub `main`, and a `DownloadTemplate` call for a file that is not there stops the run.
  **Already satisfied, nothing pushed by this change.** `HEAD == origin/main` and both files are on
  it: `article_review.md` is present and `article_writer.md` carries the `{{ ASSET_TYPES }}` marker
  line. So the prompt half is live now and the graph half is not — consistent, because nothing
  fetches `article_review.md` until the apply.
- [x] 4.3 Dry run with `scripts/apply_workflow_changes.py`, guarded by `--require-edge` for the
  edges the change assumes, read from the export's own connection graph
  (`parse_article>download_article_review_prompt`, `merge_article_verdict>switch_article_check`,
  `switch_article_check>download_article_prompt`). Record the guards and confirm each premise held.
  **Landed 2026-10-18, and the three guards above were wrong — they cannot hold.** `--require-edge`
  reads the *live* graph before any edit, and those three edges are the ones the change **creates**,
  so the first one answered `DRIFT: parse_article -> ['set_output']` and the script stopped. They
  are post-apply idempotency guards, not premises; re-run them after 4.4 (the script then reports
  `nothing to change`). The premises that do hold live were used instead:
  `parse_article>set_output` (the edge being replaced), `set_workflow_vars>download_article_prompt`
  (the retry re-enters the prompt chain), `ai_model>create_article_ai` and
  `ai_model_fallback>create_article_ai` (the reviewer shares the model nodes). All four answered
  `edge ok`. The plan: 6 nodes added, 8 connection sources rewritten, 4 nodes' parameters set.
  Live was re-read after the dry run — 11 nodes, `versionId 83d2696a…` unchanged, nothing written.
  **The spec was proven complete offline before it is trusted**: applying it in memory to the live
  read yields `nodes` and `connections` byte-identical to the export, so the PUT cannot leave live
  short of the export (a spec that misses a field is invisible until the nightly backup reverts it).
- [ ] 4.4 Apply (`--changes` with the field-level paths, `addNodes` and the rewritten connections;
  never a whole exported body), then
  re-read: `activeVersion` carries the edit, `active` is still true, and the export's node-name set,
  connections and touched nodes match the live read-back. `Article Creator` is active, so publish
  the draft and confirm the published version carries it.

## 5. Behaviour verification

- [ ] 5.1 An over-budget draft is retried: drive one run whose first draft exceeds `MAX_WORDS`, and
  confirm the second draft is inside the budget and the run publishes, rather than failing. Record
  the attempt count and both drafts' counts.
- [ ] 5.2 A draft that never satisfies the gate reports `MAX_RETRIES_EXCEEDED: <reason>` with the
  reviewer's own words, and the run's error notice names it.
- [ ] 5.3 The reviewer reads the committed rules: read the run's own
  `download_article_review_prompt` output and confirm it carries `article_writer_system.md`
  verbatim.
- [ ] 5.4 The hero marker matches the requested type: a row requesting `image_wide` produces a
  draft carrying `<!-- asset:image_wide -->`, and the published file references the hero at its
  marker rather than at the fallback position.

## 6. Documentation

- [ ] 6.1 Update the `Article Creator` paragraph of `AGENTS.md` (the n8n section) with the review
  loop, the deterministic-budget rule and the marker correction.
- [ ] 6.2 Leave every `[UNVERIFIED]` in `design.md` honest after 5.1–5.4.
- [ ] 6.3 Archive only when the graph is live, the prompts are pushed and 5.1–5.4 have run:
  `openspec archive add-article-review-gate`.
