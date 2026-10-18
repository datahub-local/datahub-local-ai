# Design

## Context

Read off the committed exports, the prompts and the failing executions.

- `article_creator.workflow.json`, `download_article_prompt`: a `DownloadTemplate` call for
  `prompts/article_writer.md` with `TOPIC`, `DESCRIPTION`, `URL`, `MAX_WORDS`, `ASSET_TYPES`,
  `EXTRA_PROMPT`, `CONTENT` and `FEEDBACK`. `FEEDBACK` already appends the reviewer's reason on a
  retry — `($json.explanation ? "\nInternal review rejected the previous draft with: " + … : "")` —
  and nothing carries the draft itself.
- `prompts/article_writer.md`, the Reviewer Feedback section: "A human rejected the previous draft
  and asked for these changes. Apply every one of them." The prompt asks the model to apply changes
  to a draft it does not have.
- `parse_article` returns `{TITLE, TEXT, WORD_COUNT, MAX_WORDS, PROBLEM}` per attempt, so the
  rejected body is `$('parse_article').last().json.TEXT` on the retry path. On the first attempt
  `parse_article` has not run at all, so the reference has to be guarded.
- Execution 14020 (2026-10-18): attempt 0 used two tool calls and wrote a 1239-word draft; the
  retry used thirteen tool calls and never wrote. `Content Research`'s tool result echoes the query
  it was given, so the model could see it was repeating itself; `Download Content`'s does not echo
  the URL, so a repeated `read_page` looks new.
- Execution 13603 (2026-10-16) reached the same error at `maxIterations: 8` with 16 tool calls, so
  the bound is not what stops the spiral.
- `linked_in_post_creator.workflow.json`, `download_post_prompt`: the same shape, with `RULES`,
  `EXTRA_PROMPT`, `CONTENT`, `VARIETY_DIRECTIVES` and the same `FEEDBACK` carry. `parse_llm_output`
  returns the post as `result`, so the rejected post is `$('parse_llm_output').last().json.result`.
- `linked_in_post_creator.workflow.json`, `switch_check_rules_llm` → `download_post_prompt` is the
  retry edge; its node `notes` records the 2026-09-30 lesson that on a second pass the paired-item
  lineage runs back through this switch and `.item` silently yields `undefined` — every cross-node
  read in those `download_*` nodes uses `.first()` for that reason. A new read on this path must use
  `.last()` (the draft just rejected, not the first attempt's) and must not use `.item`.

## Gate findings

- **The retry's instruction and its input disagree, and the input is what is missing.** The reviewer
  says "apply these changes"; the drafter is handed no draft. Fixing the prompt's wording alone
  cannot close that: a model asked to edit an absent draft will write one, and on a topic whose
  search returns homonyms it will look for material first. The draft has to travel.
- **`.last()`, not `.item`, and not `.first()`.** `.item` is the failure recorded in the LinkedIn
  node's own notes. `.first()` would send the *first* attempt's draft back on every retry, so a
  three-attempt run would edit the same rejected draft twice and the loop could never converge.
  `.last()` is the draft the switch just rejected.
- **The first attempt must render an empty block, not throw.** `parse_article` / `parse_llm_output`
  have not executed when `download_*_prompt` runs from the entry point, and an unguarded
  `$('node')` reference throws at run time. `isExecuted` is the guard the LinkedIn sharing lane
  already uses for the same shape.
- **A pushed prompt with a placeholder the graph does not pass stops every run.** The article lane's
  two halves are already asserted against each other
  (`test_creator_passes_what_the_task_prompt_declares`); the LinkedIn lane has no such case, so one
  is added with this change rather than after it.
- **The bound stays at 12.** It has never stopped the spiral (13603 at 8, 14020 at 12), and a
  legitimate turn needs headroom: every model failure inside the agent loop spends an iteration,
  and the gateway is failing two to three times per run. Lowering it would trade one failure for
  another.

## Decisions

- **D1 — `PREVIOUS_DRAFT`** on `prompts/article_writer.md`, supplied as
  `$('parse_article').isExecuted ? $('parse_article').last().json.TEXT : ""`.
- **D2 — `PREVIOUS_POST`** on `prompts/linkedin_post.md`, supplied as
  `$('parse_llm_output').isExecuted ? $('parse_llm_output').last().json.result : ""`.
- **D3 — the prompt says what the block is for.** Article: edit the draft, keep what the review did
  not object to, and **do not research again on a retry** — the Source Material is what the turn
  has. LinkedIn: edit the draft, and the Final Pass runs over the edited post as before.
- **D4 — the empty block means the first attempt**, and both sections say so, so the first turn is
  not told to edit a draft it has not written.
- **D5 — `maxIterations` unchanged.**

## Risks / Trade-offs

- **A longer drafting prompt.** The previous draft is the body, so a 1200-word article adds ~1200
  words to the retry's context. That is the cost of editing rather than regenerating, and it is
  smaller than the 16 model calls the spiral spent.
- **An empty-vs-populated block is the only difference between the first attempt and a retry.** If
  `isExecuted` ever resolves true on the first attempt, the model is told to edit nothing. The
  offline cases cover the expression, not the engine's evaluation of it — that half is a live
  observation, recorded in the tasks.
- **The LinkedIn lane changes a workflow that publishes.** Its retry path is exercised only by a
  live rejection, so the wiring is asserted offline and the behaviour is left to that lane's own
  verification.

## Open Questions

- **Whether the retry should also stop researching in the LinkedIn lane.** It has no tools, so the
  spiral cannot happen there; the change is about editing rather than regenerating.
- **Whether `read_page` should echo the URL it read.** Its result carries no URL, so the model
  cannot tell a repeat from a new call. A one-field change in `Download Content`, worth doing once
  measured against its other callers.
- **Whether the article retry should carry `WORD_COUNT` too.** The reviewer's reason names the count
  already, so the prompt does not restate it; if retries keep missing the budget, giving the drafter
  its own number is the next step.

## Definition of done

- `openspec validate --all` passes with this change present.
- `agents/n8n`'s offline suite passes, and the new cases fail without the change (the retry carries
  no draft, and the LinkedIn prompt's placeholders are not held to its call).
- The export's two graph copies agree in both workflows.
- Both graphs applied live with `--require-edge`, read back, and the exports diffed against live.
- A live retry observed to edit rather than regenerate — the one thing no offline case can show.
