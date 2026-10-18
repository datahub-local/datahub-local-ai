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

- [x] 4.1 Ask the owner before writing, per the repository rule: present the diff of the graph and
  the two prompt files, and get an explicit answer.
  **Asked 2026-10-18 and answered.** The diff was presented: live had 11 nodes against the export's
  17, `parse_article → set_output` was replaced by the six-node loop, and the two prompt files were
  already on `origin/main` (4.2). The owner asked for the dry run first and then said go.
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
- [x] 4.4 Apply (`--changes` with the field-level paths, `addNodes` and the rewritten connections;
  never a whole exported body), then
  re-read: `activeVersion` carries the edit, `active` is still true, and the export's node-name set,
  connections and touched nodes match the live read-back. `Article Creator` is active, so publish
  the draft and confirm the published version carries it.
  **Landed 2026-10-18.** The `--changes` spec was proven complete before the write by applying it
  in memory to the live read and diffing against the export. All 18 writes landed with no
  `MISMATCH`, `active` stayed `True`, and the PUT republished on its own — `versionId` and
  `activeVersionId` moved together from `83d2696a…` to `feb7865e…` with all 17 nodes, so no
  deactivate/activate cycle was needed. Re-read after: both copies 17 nodes, node sets and
  connections equal to the export. One export defect was found and fixed in the same step: the two
  copies disagreed on the `MAX_TRIES` assignment's `id` (`a25233cd…` at the top level against
  `e4b03332…` in `activeVersion`), and live's own two copies agreed, so the export was reconciled to
  live. A later field-level apply added the reviewer's retry settings (see 5.4).

## 5. Behaviour verification

Driven live 2026-10-18 through a temporary probe workflow (`Article Creator Probe`,
`rpqx0u1MDgcn4fCw`) — a `webhook → executeWorkflow` shell, because the public API cannot fire a
sub-workflow's `executeWorkflowTrigger`. Deleted after the runs.

- [x] 5.1 An over-budget draft is retried: drive one run whose first draft exceeds `MAX_WORDS`, and
  confirm the second draft is inside the budget and the run publishes, rather than failing. Record
  the attempt count and both drafts' counts.
  **Landed — execution 13994.** Four attempts' worth of bound, three drafts: **462/400** →
  `PROBLEM = OVER_BUDGET: 462 words against MAX_WORDS=400` → retried; **412/400** → retried, the
  reason carried as `Internal review rejected the previous draft with: OVER_BUDGET: 462 words
  against MAX_WORDS=400 Body is 462 words, so cut 62 words to meet the 400-word limit.`; **345/400**
  → the reviewer answered `true`, `set_output` ran with `ERROR=''` and `word_count=345`, and the run
  published. Two earlier runs measured the same path without publishing: 13975 (489/400 and 547/400
  retried, 371/400 and 353/400 inside the budget) ended on a 30 s reviewer timeout — see the retry
  finding below — and 13913 showed the budget is *not* hit when the writer can comply (150/148/132/133
  against 150), so the overshoot has to be driven, not waited for.
- [x] 5.2 A draft that never satisfies the gate reports `MAX_RETRIES_EXCEEDED: <reason>` with the
  reviewer's own words, and the run's error notice names it.
  **Landed — executions 13892 and 13913.** `set_error_max_tries` wrote
  `MAX_RETRIES_EXCEEDED: <the last attempt's explanation verbatim>` (13892: the closing-restatement
  finding; 13913: the `nothing reads bronze` paraphrase). The sub-workflow's own status is
  `success` — the reason is data — so the entry point's `check_draft_error` is what fails the article
  run: one report, as designed.
- [x] 5.3 The reviewer reads the committed rules: read the run's own
  `download_article_review_prompt` output and confirm it carries `article_writer_system.md`
  verbatim.
  **Landed — execution 13892.** All four attempts' reviewer prompt contain the committed
  `prompts/article_writer_system.md` (1449 bytes) **verbatim**, so the gate and the drafter read one
  file, not two.
- [x] 5.4 The hero marker matches the requested type: a row requesting `image_wide` produces a
  draft carrying `<!-- asset:image_wide -->`, and the published file references the hero at its
  marker rather than at the fallback position.
  **Landed, with the publish path exercised offline.** Every draft of 13892, 13913 and 13994 carries
  `<!-- asset:image_wide -->` alone on its own line, and no attempt's reviewer found a marker
  problem once the check named the form (the runs before that fix are the finding below).
  `test_the_hero_reference_replaces_the_marker_where_the_writer_put_it` executes the committed
  `build_commit_files` jsCode with **13994's own published draft** and asserts the hero reference
  lands before the first `## ` heading with no `placed without a marker` log, plus a control case on
  the stale `<!-- asset:image -->` marker that must take the fallback — so the assertion cannot pass
  vacuously. A live publish was **not** run: it writes a commit to the blog repository, and the
  placement decision is a pure function of the draft and the asset rows, both of which the test
  takes from the run.
  **Found and fixed in this section:** the gate's own model call carried no retries, unlike the
  `check_rules_llm` it mirrors, so one 30 s LiteLLM timeout ended a run that already had four drafts
  (execution 13975). `retryOnFail: true, maxTries: 5, waitBetweenTries: 5000` was applied live and
  pinned by `test_the_reviewer_retries_a_transient_model_failure`.

## 6. Documentation

- [x] 6.1 Update the `Article Creator` paragraph of `AGENTS.md` (the n8n section) with the review
  loop, the deterministic-budget rule and the marker correction.
  **Landed as a new `#### Article Creator` subsection.** There was no paragraph to update — the
  lane was documented only through the incident bullets in *seven structural things* — so the
  subsection is new, sitting after `#### LinkedIn post media`, and carries the two workflows and
  the creator's input contract, the review loop and its bound, the deterministic budget, the shared
  rules file, the reviewer's retries, the marker-form rule, the `EXTRA_PROMPT` conflict, what CI
  does and does not cover, and the two traps in reading the lane's history (the `OVER_BUDGET`
  substring, and 13844).
- [x] 6.2 Leave every `[UNVERIFIED]` in `design.md` honest after 5.1–5.4.
  **Landed.** Both `[UNVERIFIED]`s are resolved into measurements: the bound is reachable (13994)
  and the reviewer's rejections were all fact checks that need `CONTENT`. The `EXTRA_PROMPT`
  conflict and the broken `glm-5.3-flash` fallback are added as open questions, and the dropped
  retries as a gate finding.
- [x] 6.3 Archive only when the graph is live, the prompts are pushed and 5.1–5.4 have run:
  `openspec archive add-article-review-gate`.
  **Conditions met and archived 2026-10-18** — graph applied and read back equal to the export in
  both copies, prompts on `origin/main`, 5.1–5.4 driven. Archived now rather than after
  `add-content-writer-agent`: that change is still open against the same `content-writer`
  capability, so this archive creates `openspec/specs/content-writer/spec.md` from the review
  requirement alone and the sibling's archive appends its own requirements to it. The owner chose
  that order deliberately.
