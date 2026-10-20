# Tasks

## 1. The audience vocabulary

- [x] 1.1 `prompts/article_audiences.md` (new): the four levels — `NONE` (today's reader, moved
  verbatim from `article_writer_system.md`), `LOW`, `MEDIUM`, `ADVANCED` — as `## <LEVEL>`
  headings with a one-paragraph reader definition each. No `{{ }}` anywhere (fetched with an
  empty vars object; `test_article_prompts.py` asserts it like `article_structures.md`).
- [x] 1.2 `prompts/article_writer_system.md`: the fixed "## The reader" paragraph becomes the
  pointer to the task prompt's Audience block, still declaring only `{{ AI_SPEAK }}`. The
  `NONE` definition moves to 1.1, not copied here.
- [x] 1.3 `prompts/article_writer.md` (edit, pushed last per D11): a `## Audience` section —
  the row's level via `{{ AUDIENCE }}` and the definitions via `{{ AUDIENCES }}`, placed above
  `## Shape` so the audience outranks the shape rules.
- [x] 1.4 `prompts/article_review.md` (edit, pushed last): the term-explanation check scales
  with `{{ AUDIENCE }}` — the level's definitions arrive as `{{ AUDIENCES }}`, and the check
  demands explanations only for what that reader does not already know.
- [x] 1.5 `agents/n8n/workflows/article_creator.workflow.json`: `main_trigger` declares
  `AUDIENCE`; `download_article_prompt` passes `AUDIENCE` and `AUDIENCES`
  (`$('download_article_audiences').first().json.output`); `download_article_audiences` (new
  node, `prompts/article_audiences.md`, empty vars) precedes it; `download_article_review_prompt`
  passes both. Both graph copies.
- [x] 1.6 `agents/n8n/workflows/article_content_writer.workflow.json`,
  `select_article_to_queue`: uppercase/trim the cell, blank → `NONE`, refuse a row whose value
  is not one of the four levels naming the value (the `CATEGORIES` refusal shape); carry
  `AUDIENCE` on the emitted item; `execute_article_creator` maps `AUDIENCE` (blank → `NONE`)
  plus its schema entry. Both graph copies.
- [x] 1.7 `datasets/board_intake.json`: `defaults` gains `"audience": "NONE"`;
  `content_board_curator.workflow.json`: `build_intake_rows` carries `AUDIENCE`,
  `append_article_queue` gains the value map entry and the `columns.schema` entry with
  `removed: false`. Both graph copies.
- [ ] 1.8 The `article_queue` page: add the `AUDIENCE` column by hand (setup step; a write to a
  column the sheet lacks is [UNVERIFIED] and not relied on).

## 2. The aspect registry and its prompts

- [x] 2.1 `datasets/article_aspects.json` (new): `aspects` listing `structure`, `clarity`,
  `flow` — each `id`, `prompt` (`prompts/article_aspect_<id>.md`), `focus`. No `{{ }}`.
- [x] 2.2 `prompts/article_aspect_structure.md`, `article_aspect_clarity.md`,
  `article_aspect_flow.md` (new): one aspect each — the job, the draft (body only, H1 separate),
  `{{ TITLE }} {{ TOPIC }} {{ DESCRIPTION }} {{ AUDIENCE }} {{ AUDIENCES }} {{ STRUCTURES }}`
  as needed (each file declares only the placeholders it uses), output one `<findings>` block of
  numbered findings — section, what, why, what to change — or `<findings>none</findings>`;
  no rewriting, no fact-checking (correctness belongs to the gate).
- [x] 2.3 `prompts/article_improver.md` (new): the edit contract of D4 — placeholders
  `{{ TITLE }} {{ DRAFT }} {{ FINDINGS }} {{ FEEDBACK }} {{ AUDIENCE }} {{ AUDIENCES }}`
  `{{ STRUCTURES }} {{ MAX_WORDS }} {{ ASSET_TYPES }}`; keep what nothing objected to; keep
  every marker exactly once; stay within budget; one `<article>` block.

## 3. The improvement pass in the entry point

All of section 3 is **both graph copies** in `article_content_writer.workflow.json`.

- [x] 3.1 Insert between `check_draft_error` (ok output) and `derive_slug`, in order:
  `download_article_aspects` (dataset) → `download_article_audiences` →
  `download_article_structures` → `download_ai_speak` → `download_writer_rules`
  (`article_writer_system.md` with `AI_SPEAK`) → `build_improvement_context` (Code) →
  `split_aspects` (Code) → `download_aspect_prompt` (`template_name:
  "={{ $json.ASPECT_PROMPT }}"`, one shared `template_vars` for every aspect) →
  `review_aspect_llm` (chainLlm, `retryOnFail: true`, `maxTries: 5`, `waitBetweenTries: 5000`,
  `options.timeout: 120000`, `onError: continueRegularOutput`) → `merge_aspect_findings`
  (Code, `alwaysOutputData`) → `if_has_findings` (findings or feedback) → true:
  `download_improver_prompt` → `improve_article` (agent, **no tools**, `maxIterations: 8`,
  `onError: continueErrorOutput`, text composes `download_writer_rules` +
  `download_improver_prompt`) → `check_improved_draft` (Code: word count + marker counts) →
  `switch_improved_ok` (ok / retry-under-bound → `download_improver_prompt` with the problem
  appended / over-bound → fallback) → `select_final_draft`; false: `select_final_draft`
  (passthrough).
- [x] 3.2 `build_improvement_context`: one item always; throws on a missing, unparsable or empty
  aspect registry (fatal — D6); reads the draft and title from `$('select_final_draft')`'s own
  last run when the chain has run in this execution, else `$('execute_article_creator')`, else
  the stored row via the `article_drafts` upsert (the resumed-review case); reads `FEEDBACK`
  from `$('notification_retry_or_cancel')` guarded by `isExecuted`; carries the row fields,
  `MAX_WORDS`, `REQUESTED_ASSETS`, `AUDIENCE`, `IMPROVE_MAX_TRIES: 2`.
- [x] 3.3 `improve_model` + `improve_model_fallback` (lmChatOpenAi, `options.timeout: 120000`),
  wired by `ai_languageModel` connections to both `review_aspect_llm` and `improve_article`
  (an agent without both connected refuses the PUT).
- [x] 3.4 `select_final_draft` (the convergence node): outputs `{text, title, word_count,
  IMPROVED, IMPROVEMENT_NOTE, FINDINGS_SUMMARY}` shaped like `set_output`, resolved by
  precedence in code (improved-passed > fallback/failed > passthrough; D6).
- [x] 3.5 `derive_slug`, `store_draft`, `draft_to_file`: the draft source becomes
  `select_final_draft` (same field names, one expression swap per node). `notify_article_review`:
  the message gains the improvement line (`IMPROVED` + findings count per aspect).
- [x] 3.6 `switch_article_retry`'s retry edge: `execute_article_creator` →
  `build_improvement_context`. `execute_article_creator`: remove the now-dead `PREVIOUS_DRAFT`
  mapping and its schema entry; `FEEDBACK` mapping unchanged (evaluated only on the first pass).
- [x] 3.7 No switch node between `split_aspects` and `merge_aspect_findings` (paired-item
  lineage reads `$('split_aspects').item.json.ASPECT`); cross-branch reads use `.last()`, never
  `.item` (the 2026-09-30 lesson).

## 4. Offline tests

- [x] 4.1 `test_article_aspects.py` (new): the registry parses, every aspect's prompt file
  exists, the entry graph fans out from the dataset (`split_aspects` reads the downloaded
  registry; no aspect id literal anywhere in the graph).
- [x] 4.2 `test_article_prompts.py`: `TRIGGER_VARS`/`CALLER_VARS` grow `AUDIENCE`;
  `article_audiences.md` has no placeholders and defines exactly the four levels; each aspect
  prompt's placeholders are a subset of what `download_aspect_prompt` supplies;
  `article_improver.md`'s placeholders are what `download_improver_prompt` supplies; the
  human-retry carry test moves to the entry point (the sub-workflow keeps only its internal
  `parse_article`-based `PREVIOUS_DRAFT`).
- [x] 4.3 `test_article_entry_point.py`: the improvement chain's edges and guards; the retry
  edge → `build_improvement_context`; the three draft consumers read `select_final_draft`;
  `check_improved_draft`'s and `select_final_draft`'s committed `jsCode` executed against
  items shaped like the live ones (the run-14259 lesson: a textual assertion cannot see a
  placeholder or a wrong verdict); `AUDIENCE` validation (blank → `NONE`, invalid refused naming
  the value) executed; the graph's level `const` equals the levels in `article_audiences.md`.
- [x] 4.4 `test_article_review_gate.py`: `article_review.md`'s new placeholders are supplied by
  `download_article_review_prompt`, and the audience check references the level.
- [x] 4.5 `test_content_board_curator.py`: the intake default is one of the four levels;
  `append_article_queue` writes `AUDIENCE` with a schema entry, `removed: false`.
- [x] 4.6 `test_model_timeouts.py` sweeps the new model nodes in both copies (no edit; confirm
  the sweep catches them). Prove the new cases fail without the change: stash the exports and
  prompt files, run, record, restore.
- [x] 4.7 Run the gates: `uv run -- pytest agents/n8n/scripts/ -q` and
  `ruff check agents/n8n/` and `openspec validate --all`; record the numbers.

## 5. Apply to the live instance

- [x] 5.1 Ask the owner before writing, presenting the plan and the push order (D11).
- [x] 5.2 Push the new files (inert), then apply `content_board_curator`, `article_creator`,
  `article_content_writer` in one `--changes` batch with `--require-edge` guards
  (`check_draft_error>download_article_aspects`, `switch_article_retry>build_improvement_context`,
  `review_aspect_llm>merge_aspect_findings`), re-read each, diff against the exports, confirm
  the active sub-workflows re-published.
- [x] 5.3 Push the prompt edits (`article_writer.md`, `article_writer_system.md`,
  `article_review.md`) — after the graphs, per D11.
- [x] 5.4 Add the `AUDIENCE` column to the live `article_queue` page; set one test row's cell to
  `ADVANCED`.

## 6. Behaviour

- [x] 6.1 First pass with findings: three aspect calls answer, the improver edits, the re-check
   passes, the review message names `IMPROVED` and the findings count.
- [ ] 6.2 A human retry: the edge re-enters `build_improvement_context`, the improvement
   prompt carries the draft the human read and the feedback, and the next draft keeps what the
   feedback did not name.
- [ ] 6.3 An over-budget improvement (force with `EXTRA_PROMPT` pushing past `MAX_WORDS`): the
   re-check rejects in code, one retry, then `IMPROVED: FALLBACK` with the gate-passed draft.
- [x] 6.4 An `ADVANCED` row: the drafting prompt carries the level, the gate does not demand
   field-basics explanations, the clarity aspect reviews at the level.
- [ ] 6.5 A blank `AUDIENCE` row: the article reads exactly as today (`NONE` default), and an
   invalid value refuses the row naming the value.

## 7. Documentation

- [x] 7.1 `AGENTS.md` `#### Article Creator`: the improvement pass (registry, advisory findings,
  code re-check, degradation taxonomy), the audience flow (one file, three enum copies held by
  tests, push order), and the moved carry-the-draft test. Note in
  `carry-the-draft-into-the-human-retry/tasks.md` that its 5.1 is superseded here.
- [ ] 7.2 Archive once 4.7, 5.2 and 6.1–6.3 have landed:
  `openspec archive add-article-audience-and-improvement-pass`.

## Implementation notes (offline half, 2026-10-19)

- **4.6 measured.** With the exports, prompts and datasets stashed to their pre-change state, the
  new and extended cases fail: **28 failed, 95 passed** across the five touched test files
  (`test_article_aspects`, `test_article_entry_point`, `test_article_prompts`,
  `test_article_review_gate`, `test_content_board_curator`). Restored, the whole suite is
  **815 passed, 1 skipped** (the skip is the `node`-guarded case in this environment),
  `ruff check agents/n8n/` reports only the pre-existing `FURB167` in
  `test_visual_studio_registry.py`, and `openspec validate --all` is **18 passed, 0 failed**.
  `test_model_timeouts.py` sweeps the two new model nodes in `article_content_writer` and
  `EXPECTED_FILES` now names the file, so a workflow that loses its model nodes fails loudly.
- **The objective problem is a prompt slot, not feedback text appended in the graph.** Task 2.3
  did not list it, but the prompt policy puts every instruction a model reads in a prompt file:
  `prompts/article_improver.md` carries `{{ PROBLEM }}` and the graph only supplies the
  re-check's reason. The findings/feedback already have their own sections.
- **The stored draft is a node, not a read inside the Code block.** Task 3.2 says
  `build_improvement_context` reads the `article_drafts` row for the resumed-review case; Code
  nodes cannot read a Data Table, so `read_draft_for_improvement` (a `dataTable` get,
  `alwaysOutputData: true`) precedes the chain and the context node resolves
  `select_final_draft` → `execute_article_creator` → that row.
- **The improvement bound is `IMPROVE_MAX_ATTEMPTS = 2` with `$runIndex + 1 gte`**, not
  `gt`/`MAX_TRIES`: two *attempts* (one retry), rather than the drafting loop's four-drafts-for-`3`
  shape.
- **`review_aspect_llm` → `merge_aspect_findings` uses index pairing over
  `$('split_aspects').all()`**, not `$('split_aspects').item`: the merge runs once for all items
  and a per-item read would need a second aggregation node. A failed reviewer contributes no
  findings; a count mismatch is logged.
- **Applied live 2026-10-19.** New files pushed to `main` (`2bed75a`) before the graphs, as D11
  requires. Read back live, diffed against the pre-change export: identical, so the apply was
  the whole delta. `Article Content Writer` (`sKsjxDDW40TATaS6`, `active: false`, 100 nodes),
  `Article Creator` (`nPBkIpeObC1Om0LH`, active, 24) and `Content Board Curator`
  (`RCSPaKMKsckAnJ9B`, active, 15) now match their exports, and both active ones' `activeVersion`
  carries the same nodes, parameters and connections — checked node by node, not by name count.
  Apply log: no `MISMATCH`, no `DRIFT`, `active` unchanged on both. The entry point stays
  inactive by design (manual runs from the editor).
- **The column is live** (5.4): `article_queue` carries `AUDIENCE`, and the test row 2 reads
  `ADVANCED`.
- **6.1 measured live — and 6.4 with it.** The Sympozium entry (row 2, `ADVANCED`) was cleared
  from the blog (`alvsanand` `c0b56bf`) and re-run as execution **14402** (2026-10-19): the three
  aspect calls answered, `structure` returned 4 findings and `clarity`/`flow` none, the improver
  edited the draft to 994 words, `check_improved_draft` found no problem, `select_final_draft`
  reported `IMPROVED` with `structure: 4, clarity: none, flow: none`, the draft was stored,
  uploaded and posted for review, and the execution sits `waiting` on `notify_article_review`.
  The dynamic `template_name` is therefore **verified**: `download_aspect_prompt` fetched each
  registry path by expression.
- **The first live run found a graph bug the offline suite could not see.** Execution 14382
  improved the draft (structure 3 findings, 1090 words, `IMPROVED`) and then ended at
  `select_final_draft` as `success`: the improvement chain replaced
  `check_draft_error -> derive_slug` and nothing wired `select_final_draft` to it. `derive_slug`
  kept its own outgoing edges, so the isolation check counted it as touched.
  - Fixed in the export and live (`7c73c4d`), and `test_workflow_invariants.py` gained
    `test_every_node_is_reachable_from_a_trigger` — a forward walk over every edge type from
    every trigger, with `ai_*` sub-nodes excluded because they are reached from their consumer.
    It fails on execution 14382's graph and passes on this one.
- **A second run fired too early and drafted a different row.** While 14382's successor was still
  being recovered (the queue recovery had marked the `waitForSubWorkflow: false` child `crashed`,
  then it resumed to `waiting`), a sync probe started execution 14417, which `pick_candidate`
  pointed at the lowest `QUEUE` row — row 200, a different pending idea — because row 2 was
  already `WAITING_APPROVAL`. The drafting gate rejected four drafts there (`MAX_RETRIES_EXCEEDED`:
  it never explained the subject and invented a fact) and the failure path recorded row 200 as
  `ERROR`. That is the 2026-10-18 reporter working, not a regression; row 200 waits for a person.
- **Two more live runs, both informative.** The review of 14402 could not be resumed: a
  `sendAndWait` inside a **sub-execution** (started by the probe's `executeWorkflow`) never
  received the Slack callback, and the execution stayed `waiting` after the approval. Cancelled
  with `POST /executions/{id}/stop`, and the lane re-run as a **top-level** execution by a
  temporary `webhook` trigger connected to `read_article_queue` — the shape a real trigger takes.
  - Execution 14450 (top level) recorded `IMPROVED: FAILED — Request timed out.`: the improver
    exceeded the 120 s model budget on the full-draft edit, fell back to the gate-passed draft,
    and still stored and posted it — the degradation path working end to end. Both improvement
    models were raised to `options.timeout: 240000` (the AGENTS floor is a floor, not a cap).
  - Execution 14468 (top level, 240 s) recorded `IMPROVED` with `structure: 5, clarity: none,
    flow: none`, 1153 words, a clean re-check, and waited on `notify_article_review`. The human
    approval **resumed it** (`waiting` → `running`) and it advanced through
    `switch_article_accept`, `update_article_approved` and `split_pending_types` before the run
    was cancelled on a stale `lastNodeExecuted` read (the API's persisted data lags a resumed
    run by minutes — recorded in AGENTS). The asset phase therefore started but did not finish,
    and the publish half is still unmeasured; the approval mechanism itself is proven for a
    top-level execution.
- **Still open:** 6.2 (a human retry with feedback), 6.3 (an over-budget improvement falling
  back), 6.5 (a blank row reads `NONE`, an invalid value is refused — the refusal is covered
  offline), and the publish half after the review is approved.
- **The retry requirement is `MODIFIED` here, not only `ADDED`.** Archiving
  `carry-the-draft-into-the-human-retry` on 2026-10-20 merged its requirement into
  `openspec/specs/content-writer/spec.md` verbatim, which states that a human retry re-enters the
  drafting sub-workflow — true when it was written, false since this change moved the retry edge
  to `build_improvement_context` (5.2's guard names exactly that edge). The delta here rewrites it
  to the shipped behaviour, so the spec converges when this change archives; without it the spec
  describes a graph that no longer exists.
