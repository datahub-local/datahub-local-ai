# Tasks

## 1. The audience vocabulary

- [ ] 1.1 `prompts/article_audiences.md` (new): the four levels — `NONE` (today's reader, moved
  verbatim from `article_writer_system.md`), `LOW`, `MEDIUM`, `ADVANCED` — as `## <LEVEL>`
  headings with a one-paragraph reader definition each. No `{{ }}` anywhere (fetched with an
  empty vars object; `test_article_prompts.py` asserts it like `article_structures.md`).
- [ ] 1.2 `prompts/article_writer_system.md`: the fixed "## The reader" paragraph becomes the
  pointer to the task prompt's Audience block, still declaring only `{{ AI_SPEAK }}`. The
  `NONE` definition moves to 1.1, not copied here.
- [ ] 1.3 `prompts/article_writer.md` (edit, pushed last per D11): a `## Audience` section —
  the row's level via `{{ AUDIENCE }}` and the definitions via `{{ AUDIENCES }}`, placed above
  `## Shape` so the audience outranks the shape rules.
- [ ] 1.4 `prompts/article_review.md` (edit, pushed last): the term-explanation check scales
  with `{{ AUDIENCE }}` — the level's definitions arrive as `{{ AUDIENCES }}`, and the check
  demands explanations only for what that reader does not already know.
- [ ] 1.5 `agents/n8n/workflows/article_creator.workflow.json`: `main_trigger` declares
  `AUDIENCE`; `download_article_prompt` passes `AUDIENCE` and `AUDIENCES`
  (`$('download_article_audiences').first().json.output`); `download_article_audiences` (new
  node, `prompts/article_audiences.md`, empty vars) precedes it; `download_article_review_prompt`
  passes both. Both graph copies.
- [ ] 1.6 `agents/n8n/workflows/article_content_writer.workflow.json`,
  `select_article_to_queue`: uppercase/trim the cell, blank → `NONE`, refuse a row whose value
  is not one of the four levels naming the value (the `CATEGORIES` refusal shape); carry
  `AUDIENCE` on the emitted item; `execute_article_creator` maps `AUDIENCE` (blank → `NONE`)
  plus its schema entry. Both graph copies.
- [ ] 1.7 `datasets/board_intake.json`: `defaults` gains `"audience": "NONE"`;
  `content_board_curator.workflow.json`: `build_intake_rows` carries `AUDIENCE`,
  `append_article_queue` gains the value map entry and the `columns.schema` entry with
  `removed: false`. Both graph copies.
- [ ] 1.8 The `article_queue` page: add the `AUDIENCE` column by hand (setup step; a write to a
  column the sheet lacks is [UNVERIFIED] and not relied on).

## 2. The aspect registry and its prompts

- [ ] 2.1 `datasets/article_aspects.json` (new): `aspects` listing `structure`, `clarity`,
  `flow` — each `id`, `prompt` (`prompts/article_aspect_<id>.md`), `focus`. No `{{ }}`.
- [ ] 2.2 `prompts/article_aspect_structure.md`, `article_aspect_clarity.md`,
  `article_aspect_flow.md` (new): one aspect each — the job, the draft (body only, H1 separate),
  `{{ TITLE }} {{ TOPIC }} {{ DESCRIPTION }} {{ AUDIENCE }} {{ AUDIENCES }} {{ STRUCTURES }}`
  as needed (each file declares only the placeholders it uses), output one `<findings>` block of
  numbered findings — section, what, why, what to change — or `<findings>none</findings>`;
  no rewriting, no fact-checking (correctness belongs to the gate).
- [ ] 2.3 `prompts/article_improver.md` (new): the edit contract of D4 — placeholders
  `{{ TITLE }} {{ DRAFT }} {{ FINDINGS }} {{ FEEDBACK }} {{ AUDIENCE }} {{ AUDIENCES }}`
  `{{ STRUCTURES }} {{ MAX_WORDS }} {{ ASSET_TYPES }}`; keep what nothing objected to; keep
  every marker exactly once; stay within budget; one `<article>` block.

## 3. The improvement pass in the entry point

All of section 3 is **both graph copies** in `article_content_writer.workflow.json`.

- [ ] 3.1 Insert between `check_draft_error` (ok output) and `derive_slug`, in order:
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
- [ ] 3.2 `build_improvement_context`: one item always; throws on a missing, unparsable or empty
  aspect registry (fatal — D6); reads the draft and title from `$('select_final_draft')`'s own
  last run when the chain has run in this execution, else `$('execute_article_creator')`, else
  the stored row via the `article_drafts` upsert (the resumed-review case); reads `FEEDBACK`
  from `$('notification_retry_or_cancel')` guarded by `isExecuted`; carries the row fields,
  `MAX_WORDS`, `REQUESTED_ASSETS`, `AUDIENCE`, `IMPROVE_MAX_TRIES: 2`.
- [ ] 3.3 `improve_model` + `improve_model_fallback` (lmChatOpenAi, `options.timeout: 120000`),
  wired by `ai_languageModel` connections to both `review_aspect_llm` and `improve_article`
  (an agent without both connected refuses the PUT).
- [ ] 3.4 `select_final_draft` (the convergence node): outputs `{text, title, word_count,
  IMPROVED, IMPROVEMENT_NOTE, FINDINGS_SUMMARY}` shaped like `set_output`, resolved by
  precedence in code (improved-passed > fallback/failed > passthrough; D6).
- [ ] 3.5 `derive_slug`, `store_draft`, `draft_to_file`: the draft source becomes
  `select_final_draft` (same field names, one expression swap per node). `notify_article_review`:
  the message gains the improvement line (`IMPROVED` + findings count per aspect).
- [ ] 3.6 `switch_article_retry`'s retry edge: `execute_article_creator` →
  `build_improvement_context`. `execute_article_creator`: remove the now-dead `PREVIOUS_DRAFT`
  mapping and its schema entry; `FEEDBACK` mapping unchanged (evaluated only on the first pass).
- [ ] 3.7 No switch node between `split_aspects` and `merge_aspect_findings` (paired-item
  lineage reads `$('split_aspects').item.json.ASPECT`); cross-branch reads use `.last()`, never
  `.item` (the 2026-09-30 lesson).

## 4. Offline tests

- [ ] 4.1 `test_article_aspects.py` (new): the registry parses, every aspect's prompt file
  exists, the entry graph fans out from the dataset (`split_aspects` reads the downloaded
  registry; no aspect id literal anywhere in the graph).
- [ ] 4.2 `test_article_prompts.py`: `TRIGGER_VARS`/`CALLER_VARS` grow `AUDIENCE`;
  `article_audiences.md` has no placeholders and defines exactly the four levels; each aspect
  prompt's placeholders are a subset of what `download_aspect_prompt` supplies;
  `article_improver.md`'s placeholders are what `download_improver_prompt` supplies; the
  human-retry carry test moves to the entry point (the sub-workflow keeps only its internal
  `parse_article`-based `PREVIOUS_DRAFT`).
- [ ] 4.3 `test_article_entry_point.py`: the improvement chain's edges and guards; the retry
  edge → `build_improvement_context`; the three draft consumers read `select_final_draft`;
  `check_improved_draft`'s and `select_final_draft`'s committed `jsCode` executed against
  items shaped like the live ones (the run-14259 lesson: a textual assertion cannot see a
  placeholder or a wrong verdict); `AUDIENCE` validation (blank → `NONE`, invalid refused naming
  the value) executed; the graph's level `const` equals the levels in `article_audiences.md`.
- [ ] 4.4 `test_article_review_gate.py`: `article_review.md`'s new placeholders are supplied by
  `download_article_review_prompt`, and the audience check references the level.
- [ ] 4.5 `test_content_board_curator.py`: the intake default is one of the four levels;
  `append_article_queue` writes `AUDIENCE` with a schema entry, `removed: false`.
- [ ] 4.6 `test_model_timeouts.py` sweeps the new model nodes in both copies (no edit; confirm
  the sweep catches them). Prove the new cases fail without the change: stash the exports and
  prompt files, run, record, restore.
- [ ] 4.7 Run the gates: `uv run -- pytest agents/n8n/scripts/ -q` and
  `ruff check agents/n8n/` and `openspec validate --all`; record the numbers.

## 5. Apply to the live instance

- [ ] 5.1 Ask the owner before writing, presenting the plan and the push order (D11).
- [ ] 5.2 Push the new files (inert), then apply `content_board_curator`, `article_creator`,
  `article_content_writer` in one `--changes` batch with `--require-edge` guards
  (`check_draft_error>download_article_aspects`, `switch_article_retry>build_improvement_context`,
  `review_aspect_llm>merge_aspect_findings`), re-read each, diff against the exports, confirm
  the active sub-workflows re-published.
- [ ] 5.3 Push the prompt edits (`article_writer.md`, `article_writer_system.md`,
  `article_review.md`) — after the graphs, per D11.
- [ ] 5.4 Add the `AUDIENCE` column to the live `article_queue` page; set one test row's cell to
  `ADVANCED`.

## 6. Behaviour

- [ ] 6.1 First pass with findings: three aspect calls answer, the improver edits, the re-check
   passes, the review message names `IMPROVED` and the findings count.
- [ ] 6.2 A human retry: the edge re-enters `build_improvement_context`, the improvement
   prompt carries the draft the human read and the feedback, and the next draft keeps what the
   feedback did not name.
- [ ] 6.3 An over-budget improvement (force with `EXTRA_PROMPT` pushing past `MAX_WORDS`): the
   re-check rejects in code, one retry, then `IMPROVED: FALLBACK` with the gate-passed draft.
- [ ] 6.4 An `ADVANCED` row: the drafting prompt carries the level, the gate does not demand
   field-basics explanations, the clarity aspect reviews at the level.
- [ ] 6.5 A blank `AUDIENCE` row: the article reads exactly as today (`NONE` default), and an
   invalid value refuses the row naming the value.

## 7. Documentation

- [ ] 7.1 `AGENTS.md` `#### Article Creator`: the improvement pass (registry, advisory findings,
  code re-check, degradation taxonomy), the audience flow (one file, three enum copies held by
  tests, push order), and the moved carry-the-draft test. Note in
  `carry-the-draft-into-the-human-retry/tasks.md` that its 5.1 is superseded here.
- [ ] 7.2 Archive once 4.7, 5.2 and 6.1–6.3 have landed:
  `openspec archive add-article-audience-and-improvement-pass`.
