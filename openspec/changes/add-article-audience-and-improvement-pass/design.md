# Design

## Context

See `proposal.md` for motivation. Only the constraints that shape the n8n approach are recorded
here; the lane's history and traps live in `AGENTS.md` `#### Article Creator`.

- The lane today: `Article Content Writer` (entry point, 76 nodes, `settings.errorWorkflow` set)
  claims a row, calls `Article Creator` (sub-workflow: drafting agent with an internal LLM gate,
  bounded at `MAX_TRIES=3`, word budget and markers checked in `parse_article` code), then
  `derive_slug` → `store_draft` (DataTable upsert, `article_drafts`) → `draft_to_file` →
  `upload_draft_file` (Slack file) → `update_article_drafted` → `notify_article_review`
  (`sendAndWait` double) → reject → `notification_retry_or_cancel` (`sendAndWait` customForm,
  Feedback) → `switch_article_retry` → Retry re-enters `execute_article_creator`.
- Three nodes read the returned draft directly: `derive_slug` (`.first().json.title`),
  `store_draft` (`.item.json.text`), `draft_to_file` (`.first().json.text`).
- `Article Creator`'s answer is `{text, title, word_count, ERROR}` (`set_output`); `ERROR` is
  data, and the call node's second output (`onError: continueErrorOutput`) reaches
  `build_failure` for a thrown failure.
- Prompt files and datasets are fetched at run time by `DownloadTemplate` from GitHub `main`
  (`BACKUP_GITHUB_REPO_*`); it scans the whole downloaded text for a doubled-curly-brace name and
  `stop_and_error`s any name it was not handed, so a placeholder nobody supplies kills every run,
  and a file fetched with an empty vars object (like `article_structures.md`,
  `blog_categories.json`) must contain no `{{ }}` at all, comments included.
- The reader is hardcoded in `article_writer_system.md` ("new to the subject"); the writer task
  prompt, the gate prompt, the structures file and the AI-speak file are all injected via
  placeholders asserted against each other in `test_article_prompts.py` and
  `test_article_review_gate.py`.
- `Content Board Curator` imports board issues into `article_queue` with defaults from
  `datasets/board_intake.json` (`parse_board_config` defaults every key); no model is consulted.
- `saveDataSuccessExecution` on the entry point stays at its default; the entry graph carries
  no asset bytes and this change adds none.

## Gate findings

Read off the exports and the live-lane history before authoring anything:

- **The improvement must converge on one node.** `derive_slug`, `store_draft` and
  `draft_to_file` all read `execute_article_creator` directly, and the retry edge also reads it
  (`PREVIOUS_DRAFT`). A pass that produced a better draft somewhere else would leave three nodes
  storing and uploading the worse one. The chain therefore ends in one convergence node
  (`select_final_draft`) shaped like `set_output` (`{text, title, word_count, …}`) that becomes
  the single draft source for every consumer.
- **The active `carry-the-draft-into-the-human-retry` change owns the wiring being rewired.** Its
  article-half (`PREVIOUS_DRAFT` on `execute_article_creator`) becomes dead the moment the retry
  edge stops re-entering the drafting call: within one execution the sub-workflow now runs at
  most once, so the mapping is always empty when evaluated. Its requirement — a human retry is
  handed the draft the human rejected — still holds; the receiver becomes the improvement pass,
  and its test moves with it. The LinkedIn half is untouched. Coordinate: either that change
  archives first, or both deltas merge (its 5.1 behaviour task is superseded by this change's
  behaviour tasks).
- **`DownloadTemplate`'s `template_name` has only ever been a literal string here.** The aspect
  fan-out needs `template_name: "={{ $json.ASPECT_PROMPT }}"`. An expression returning a string
  is the same mechanism as the `={{ {…} }}` object every caller already passes as
  `template_vars`, but no caller in this repository does it for `template_name`, so it is
  [UNVERIFIED] until the first live run. Alternative if it proves broken: fixed download nodes
  per aspect — rejected as the primary shape because it duplicates the aspect enum into the
  graph (the FORMS trap); acceptable as a fallback with the same tests.
- **A node with zero input items does not run, and downstream stops** (the `prepare_uploads`
  failure, execution 13401). The aspect fan-out (`split_aspects`) therefore never starts from a
  possibly-empty list: `build_improvement_context` emits exactly one item carrying `ASPECTS[]`,
  and refuses an unparsable or empty registry by throwing — fatal, loud, error workflow fires
  (the semantic-registry pattern: without its definitions the pass must not run quietly).
- **An agent node needs its Chat Model and Fallback Model inputs connected or the PUT/activate
  is refused** (the `if_needs_research` lesson). The entry point gains its first model nodes
  (`improve_model`, `improve_model_fallback`), wired to both the aspect `chainLlm` and the
  improvement agent, `options.timeout: 120000` like every model node (`test_model_timeouts.py`
  sweeps both graph copies).
- **`derive_slug` freezes the slug from `ARTICLE_TITLE` on the row first** — a retry that
  changes the title must not rename committed files. An improvement round that edits the title
  hits the same rule and keeps the frozen slug; no change needed, but the re-check must not
  "restore" a title the row already froze.
- **`Article Content Writer` is deactivated live** (no `activeVersion`; runs are manual from the
  editor, which executes the draft graph). The apply therefore lands in the draft graph and the
  workflow's re-activation is not at stake; the *sub-workflows* are active and must re-publish,
  and activation re-validates every node (the 2026-10-02 lesson).

## Goals / Non-Goals

**Goals:**

- One improvement pass that makes the draft better before the human sees it, driven by findings
  from named aspects, with the human's Retry as the targeted edit loop.
- Audience as a row's decision, flowing from one committed definitions file into every pass that
  writes or judges the article.
- Degradation, never blocking: a failed aspect, a failed improver or a failed re-check leaves a
  reviewable draft and a recorded reason.
- The objective half stays in code: budget and markers are counted, never asked of a model.

**Non-Goals:** the LinkedIn lane; aspect reviewers as gates; changing the drafting gate's checks
or bound; judging the audience at intake; backfilling `AUDIENCE`; publishing without the human.

## Decisions

### D1. The improvement pass lives in the entry point, after the sub-workflow returns

`Article Creator` keeps its contract: produce a *correct* draft (facts, budget, markers, rules).
The entry point owns the human gate, so it owns the quality pass that feeds it: aspects →
improvement → code re-check → the same `store_draft` → `upload_draft_file` →
`notify_article_review` sequence, so the draft of record is always the improved one and the
review file is what the human should read. A retry enters this chain, not the drafting loop.

*Alternatives considered:* inside `Article Creator` after the gate — rejected: every human retry
would re-run the whole drafting loop (up to four drafts plus the gate plus the aspects), and the
sub-workflow's contract would grow a findings mechanism it cannot use for itself. A separate
improvement workflow called as a sub-workflow — rejected: the chain needs the row, the draft, the
feedback and the audience, all of which the entry already holds, and it must converge on the
node the entry's consumers read; a sub-workflow would return through one more indirection for no
isolation benefit (it shares the entry's failure surface anyway).

### D2. The aspect reviewers advise; nothing rejects but the objective checks and the human

Each aspect returns numbered findings — section, what, why, what to change — or `none`. The
findings are data merged into the improvement prompt. No aspect can reject a draft, gate a round,
or burn a retry bound.

This is the direct lesson of the two gate incidents: a rule a gate enforces that the drafter
cannot read is unfixable by construction (2026-09-30, the LinkedIn harness ban), and a judgement
gate burned four drafts and twenty minutes on "simplicity" for a subject whose vocabulary is
custom resources (execution 14055). The improvement pass exists to *apply* judgement, which is
only safe on the advisory side of that line.

### D3. The aspects come from a registry, and the graph holds no aspect ids

`datasets/article_aspects.json` (fetched via `DownloadTemplate` like `board_intake.json`) lists
the aspects: `id`, `prompt` (the prompt file), `focus`. `split_aspects` fans the registry out to
one item per aspect; `download_aspect_prompt` fetches that item's file by expression
(`template_name: "={{ $json.ASPECT_PROMPT }}"`); `review_aspect_llm` (one `chainLlm`, runs per
item) reviews the draft against that aspect; `merge_aspect_findings` collects the `<findings>`
blocks, tagged by aspect. Adding an aspect is a dataset entry plus a prompt file — no graph edit
(the sympozium shape: textual change, no committed generated artifact).

Three ship: `structure` (plot and arc — does the body fit the shape the writer chose, does every
section earn its place, is the order right), `clarity` (terms explained and plain language *at
the row's audience level*), `flow` (redundancy, transitions, pacing, section length). Correctness
is deliberately absent: facts, budget and markers stay with the drafting gate and the code
re-check, so an aspect finding can never contradict a correctness check.

*Alternatives considered:* fixed nodes per aspect (three download + three chain nodes) —
rejected: the enum duplicated into the graph is the FORMS trap (three copies that must change
together); acceptable only as the fallback if the dynamic template name proves broken
([UNVERIFIED], Gate findings). One reviewer call covering all aspects — rejected by the
requester: separate agents per aspect. A dataset-driven *model* per aspect — rejected: one
gateway, one fallback, the fleet's shape.

### D4. The improvement agent edits the draft and never researches

`improve_article` is an `agent` node with **no tools** and `maxIterations: 8` (the no-tools floor
measured for `create_article_ai_plain`; a gateway failure spends an iteration). Its prompt
composes the same committed rules the writer was given (`download_ai_speak` +
`download_writer_rules`, fetching `article_writer_system.md` — one copy of the writing rules for
writer, gate and improver, the same satisfiability property the gate already has) plus the
improvement task prompt (`prompts/article_improver.md`) carrying the draft, the merged findings,
any human feedback (verbatim, highest priority), the audience level and definitions, the
structures, the word budget and the requested asset types.

The edit contract: keep what nothing objected to; change only what a finding or the feedback
names; keep every requested marker exactly once, alone on its own line; stay within the budget;
keep the title unless a finding names it; answer one `<article>` block. No research, ever — the
draft is the material.

*Alternatives considered:* a second researching agent — rejected: the 14147 spiral is the
measured failure mode, and an editor handed the draft has nothing to look up. Reusing the
writer's task prompt with a findings block appended — rejected: its Research and Previous Draft
sections would lie to the improver.

### D5. The objective re-check is in code, in the entry point

`check_improved_draft` counts the improved body's words (markers excluded) and its
`<!-- asset:<type> -->` markers (exactly once per requested type) — the `parse_article` logic
re-implemented where the entry needs it. An improved draft over budget, or with a drifted
marker, is not delivered: the improvement re-renders once with the objective problem appended
to its feedback (bound 2, the `$runIndex` switch shape the drafting loop uses), then the run
falls back to the gate-passed pre-improvement draft and records why.

A count is a count: asked of a model it gets invented (the `parse_article` lesson), so the check
is a twin of the sub-workflow's counter held in step by a test that runs both against the same
fixture and asserts the same verdicts. *Alternative considered:* asking the improver to
self-report counts — rejected for the same reason `parse_article` counts.

### D6. Degradation never blocks; a broken registry is fatal

The failure taxonomy, each tier chosen from a paid incident:

| What fails | Behaviour | Pattern |
| --- | --- | --- |
| `article_aspects.json` missing, unparsable or empty | `build_improvement_context` throws; error workflow fires | the semantic-registry-is-fatal rule |
| An aspect's prompt file missing on GitHub | the download fails; run fails loudly | the 404 `download_template` probe |
| An aspect's model call exhausted (`retryOnFail` 5 × 5000 ms) | `onError: continueRegularOutput`; that aspect records no findings; the rest run | the visual critic must not fail the run it checks |
| `improve_article` fails | `onError: continueErrorOutput`; fallback to the gate-passed draft, `IMPROVED: FAILED` + reason | a failed animation never blocks the post |
| The improved draft fails the re-check after the bound | fallback to the gate-passed draft, `IMPROVED: FALLBACK` + reason | same |

`select_final_draft` (the convergence node) resolves precedence in code: the improved draft when
the re-check passed it; otherwise the gate-passed draft with the reason riding on the item. Every
outcome — `IMPROVED`, `FALLBACK`, `FAILED`, `NONE` (no findings and no feedback: the improver is
skipped, the draft passes through unchanged) — rides to `notify_article_review`, whose message
gains one line naming it and the findings count, because the reviewer sees the motion (the
reviewer-sees-the-motion rule).

### D7. The Slack Retry re-enters the improvement pass

`switch_article_retry`'s retry edge rewires from `execute_article_creator` to
`build_improvement_context`, which reads the feedback from `$('notification_retry_or_cancel')`
guarded by `isExecuted` (the same shape the drafting call's mapping uses today) and the draft of
record from `$('select_final_draft')`'s own last run when the chain has run in this execution,
falling back to `$('execute_article_creator')`'s answer on the first pass. The drafting call
itself runs at most once per execution, so its `PREVIOUS_DRAFT` mapping is removed (dead code —
the tidy rule), and `test_article_prompts.py`'s human-retry fallback test moves with it: the
sub-workflow keeps its internal `parse_article`-based `PREVIOUS_DRAFT` untouched, and the
caller-side carry now lands on the improvement context. A re-presented review in a *new*
execution (the D14/D15 resume path) re-enters through `switch_phase`, and the human retry then
finds `select_final_draft` not executed in that execution — the fallback to the draft row via
`store_draft`'s upsert (already read by `read_draft_for_assets`/`read_draft_for_publish`) covers
the resumed case; this is the `carry-the-draft` pattern generalized to the new receiver.

Cancel is unchanged. `ARTICLE_ROUND` counts improvement rounds exactly as it counted drafting
rounds: every round, improved or not, waits for the human.

### D8. The audience is one column, four levels, one definitions file

`prompts/article_audiences.md` is the only copy of what each level means:

- `NONE` — the general reader, new to the subject: an engineer from another field. Explain
  every term the first time it appears. (Today's reader, moved verbatim from
  `article_writer_system.md`; blank rows keep today's articles.)
- `LOW` — knows the field, new to this subject: explain the subject's own words; the field's
  basics need no introduction.
- `MEDIUM` — a practitioner in the subject's area: explain only what is specific to this thing;
  the area's basics are assumed.
- `ADVANCED` — works with this daily: no orientation; the depth, the trade-offs, the internals.

The file carries no `{{ }}` (it is fetched with an empty vars object, like
`article_structures.md`). The level id travels separately: `{{ AUDIENCE }}` in
`article_writer.md` (a new `## Audience` section: "The row's audience level is {{ AUDIENCE }}"
plus `{{ AUDIENCES }}`), in `article_review.md` (the gate's term-explanation check scales with
the level — the satisfiability rule: the gate must not demand explanations the level says the
reader already has), in each aspect prompt, and in `article_improver.md`.
`article_writer_system.md`'s fixed reader paragraph becomes a pointer ("the task prompt's
Audience section defines this article's reader; write for that reader; when the level is `NONE`
the reader is new to the subject"), still declaring only `{{ AI_SPEAK }}`.

The level enum exists in three places by necessity — the definitions file's four headings, the
entry point's validation `const` in `select_article_to_queue`, and the board default — and the
tests hold them together (the FORMS pattern: a change fails offline until every copy agrees).

*Alternatives considered:* a numeric level — rejected: the cell is hand-edited, and `ADVANCED`
reads without a legend. A free-text audience column — rejected: the definitions file could not
be selected by expression, and every consumer would re-interpret prose.

### D9. Invalid `AUDIENCE` refused loudly; blank is `NONE`; no backfill

`select_article_to_queue` uppercases and trims the cell, treats blank as `NONE`, and refuses a
row whose value is not one of the four levels, naming the value — the `CATEGORIES` refusal shape
(a mistyped level silently read as `NONE` would publish ADVANCED orientation to a general reader
and nothing would ever say so). `execute_article_creator` maps `AUDIENCE` (blank → `NONE`);
`main_trigger` declares it; `TRIGGER_VARS`/`CALLER_VARS` grow it; existing rows and the live test
row need nothing — blank already behaves as today.

### D10. The board intake writes the default; a person edits the cell

`board_intake.json` `defaults` gains `"audience": "NONE"`; `parse_board_config` defaults every
key so a partial file degrades; `build_intake_rows` carries `AUDIENCE`; `append_article_queue`
gains the value map entry and the `columns.schema` entry with `removed: false` (the
Content-Board-Curator lesson: without the schema entry the column is silently not written). No
model is consulted — the audience is a person's decision, like the board idea itself.

### D11. Push order: new files, then the graph, then the prompt edits

1. Push the **new** files (`article_audiences.md`, `article_improver.md`, the three aspect
   prompts, `article_aspects.json`). Nothing fetches them yet; they are inert — but they must
   exist before the graph that fetches them is applied, or the first run dies at the 404.
2. Apply the graphs (curator + sub-workflow + entry, one `--changes` batch). A graph passing a
   var the old prompts do not use is harmless (the push-order rule).
3. Push the **edits** to existing prompts (`article_writer.md`, `article_writer_system.md`,
   `article_review.md`) — placeholders land only after the graph passes them, because a pushed
   prompt naming a placeholder the graph does not pass stops every run.
4. The `AUDIENCE` column is added to the `article_queue` page by hand before the first run of
   the new append; writing a column the sheet lacks is [UNVERIFIED] and is not relied on.

### D12. Cost and budget

+4 model calls per accepted draft in the common case (3 aspects + 1 improver; +1 more on an
objective retry), each a single call on the 120 s timeout with `retryOnFail` for the `chainLlm`.
The improver is skipped when there is nothing to apply (no findings, no feedback) — the cheapest
case is +3. Every new payload is prose (tens of kB); no binary, no data URL, no asset bytes —
the queue-mode placeholder trap does not apply, and the studio storage rule is untouched.

## Risks / Trade-offs

- **Two to four minutes more before the human sees a draft.** → Aspects are single calls; the
  improver is skipped when there is nothing to apply; every call retries and degrades rather
  than blocking. The human gate is minutes anyway.
- **An aggressive improver rewrites what the writer got right.** → The edit contract names it;
  findings must name the section they object to; the re-check bounds drift; the human still
  gates, and `ARTICLE_ROUND` names the round. The fallback draft is one rejection away.
- **Advisory findings push the draft over budget or drop a marker.** → The code re-check
  (D5) catches both, retries once with the problem, falls back recorded. Objective, in code.
- **The level enum drifts between the file, the graph const and the board default.** → The tests
  assert the three agree (the FORMS pattern); a new level fails offline until all copies carry it.
- **The dynamic `template_name` is unproven.** → [UNVERIFIED] until the first live run; the
  fallback shape (fixed download nodes per aspect) is documented and testable.
- **The UI rewrites exports and may drop default-valued params.** → Tests assert effective
  values (`get("x", default)`), never presence (the 2026-10-17 backup lesson); the nightly backup
  is the reconciler, and apply is field-level with `--require-edge` guards.
- **The improvement chain adds ~13 nodes to a 76-node entry graph.** → Accepted: the entry owns
  review, so it owns improvement; every node is one of four already-proven shapes (download,
  code, chain, agent). `test_workflow_invariants.py` sweeps names, edges and positions.
- **Interaction with the active `carry-the-draft-into-the-human-retry` change.** → Its
  article-half test is rewritten here and its requirement still holds (Gate findings); its
  LinkedIn half is untouched. Its unarchived 5.1 task is superseded by this change's behaviour
  tasks; note that in its `tasks.md` when archiving.
- **A person sets `ADVANCED` on a row whose subject still needs orientation.** → The audience is
  the row's own decision, visible on the sheet; the human review still reads the draft.

## Migration Plan

1. Add the `AUDIENCE` column to the `article_queue` page by hand; set one row's cell to a
   non-`NONE` level for the live behaviour check.
2. Push the new prompt and dataset files (inert until fetched).
3. Extend the offline tests; prove the new cases fail against the current exports (stash, run,
   record, restore — the section-3.1 pattern).
4. Owner go-ahead, then apply `content_board_curator`, `article_creator`,
   `article_content_writer` in one `--changes` batch with `--require-edge` guards (e.g.
   `check_draft_error>download_article_aspects`, `switch_article_retry>build_improvement_context`,
   `review_aspect_llm>merge_aspect_findings`), re-read each and diff against the exports, confirm
   the active sub-workflows re-published (`activeVersion` carries the edit).
5. Push the prompt edits (`article_writer.md`, `article_writer_system.md`, `article_review.md`).
6. Drive one run per path with the manual trigger: findings applied / no findings / retry with
   feedback / over-budget improvement (force with an `EXTRA_PROMPT` pushing past `MAX_WORDS`) /
   improver failure. Record the measurements in `tasks.md`.
7. Rollback: deactivate nothing (the entry is manual-inactive live), set the live row back to
   `QUEUE`, revert the prompt pushes. The graph changes are field-level and revert through the
   same script.

## Open Questions

- Whether the merged findings should also post to the Slack review thread (today: one summary
  line in the review message; the full findings ride on the run and the improvement prompt).
- Whether an aspect should be skippable per row (no column; a data change if ever wanted).
- Whether `ADVANCED` should raise the row's `MAX_WORDS` default (currently no — the two knobs are
  independent and a row can raise its own budget).

## Definition of Done

- `openspec validate --all` green.
- `uv run -- pytest agents/n8n/scripts/ -q` green, with every new case proven to fail against the
  pre-change exports; `ruff check agents/n8n/` no new errors.
- The graphs applied live (field-level, guarded, re-read, diffed, sub-workflows re-published) with
  the owner's go-ahead recorded in `tasks.md`.
- One live run per path measured and recorded (findings applied, no findings, retry with
  feedback, objective fallback).
- `AGENTS.md` `#### Article Creator` carries the improvement pass, the audience flow and the
  push order; the change archived with `openspec archive add-article-audience-and-improvement-pass`.
