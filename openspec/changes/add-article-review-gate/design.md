# Design

## Context

Read off this repository's own exports and tests; each path is where the claim comes from.

- `article_creator.workflow.json`, node `parse_article`: computes `WORD_COUNT` in code and returns
  `ERROR = 'OVER_BUDGET: <n> words against MAX_WORDS=<m>'` (or `EMPTY_DRAFT` / `EMPTY_TITLE`).
  `MAX_WORDS` missing throws, deliberately — the caller resolves the budget and the 1200 default.
- `article_creator.workflow.json`, node `set_output`: maps `text`, `title`, `word_count`, `ERROR`
  straight from `parse_article`, so a problem on the first draft is what the caller receives.
- `article_content_writer.workflow.json`, node `check_draft_error`: switches on `$json.ERROR` being
  empty; a non-empty value routes to `stop_and_error`. That is the fatal half.
- `linked_in_post_creator.workflow.json` is the shape being mirrored: `create_post_ai` →
  `parse_llm_output` → `if_enabled_check` → `download_post_review_prompt` → `check_rules_llm` →
  `parse_llm_check_output` → `switch_check_rules_llm`, whose three outputs are `set_output`,
  `set_error_max_tries` and (fallback) `download_post_prompt`. `download_post_prompt`'s
  `FEEDBACK` carries `$json.explanation` into the next attempt. `switch_check_rules_llm`'s bound is
  `{{ $runIndex + 1 }} > MAX_TRIES` — the `+ 1` is the fix of 2026-09-30, when `$runIndex >
  MAX_TRIES` spent MAX_TRIES + 2 drafts.
- `prompts/article_writer_system.md` declares no placeholder (it is fetched with `{}`), so it can
  serve as a substituted `{{ RULES }}` block in another prompt without an unresolvable name.
- `prompts/article_writer.md` hardcoded `<!-- asset:image -->` for the hero. `build_commit_files`
  matches `<!-- asset:<requested type> -->`, so a row requesting `image_wide` never matches it and
  the hero is placed by the fallback branch (`placed without a marker: image_wide`). Invisible
  today; fatal under a marker check.

## Gate findings

- **The deterministic budget must beat the reviewer.** A model asked to count words will report a
  number it invented, so the count stays in `parse_article` and `merge_article_verdict` rejects on
  `PROBLEM` regardless of the reviewer's `<output>`. This is the `endpoint-warden` lesson
  (a mandatory column satisfied with invented numbers) applied to a gate.
- **The gate must read the same rules file as the writer.** Two copies drift, and a gate enforcing
  a rule the drafter never saw is the failure of 2026-09-30 in a new place. `RULES` is
  `$('download_system_prompt').output` — the writer's own fetched file — never a second file.
- **A rejection must re-render the prompt.** The retry edge returns through
  `download_article_prompt`, whose `FEEDBACK` appends `Internal review rejected the previous draft
  with: <explanation>`. A retry straight to the model resubmits the same prompt.
- **`MAX_TRIES` bounds retries, so the loop admits `MAX_TRIES + 1` drafts.** Bound expression
  `$runIndex + 1 > MAX_TRIES`, copied from the LinkedIn gate rather than re-derived, because the
  off-by-one there was measured. Measured here too, live 2026-10-18: `MAX_TRIES = 3` ran
  `parse_article` **four** times (executions 13892 and 13913). The expression is kept — it is the
  LinkedIn lane's measured shape — but the name is a bound on the retries, not a count of drafts.
- **The marker instruction is a precondition of the gate.** Adding a marker check without fixing
  `<!-- asset:image -->` would reject every wide-type draft forever, so the prompt half is part of
  this change rather than a follow-up.
- **The gate's marker check must name the form, not the id.** The first live runs rejected a
  correct `<!-- asset:image_wide -->` twice — the check said "spelled as the type id" and the
  reviewer read that as the bare id — and on the two attempts that followed the writer dropped the
  marker altogether, so the gate destroyed the thing it was checking (executions 13892 and 13913,
  2026-10-18). `build_commit_files` matches `<!--\s*asset:<type>\s*-->`, so the comment form is the
  authority: the check now states that form, and `test_both_prompt_files_name_the_same_marker_form`
  pins it against the writer's rule. Same class as 2026-09-30 in the LinkedIn lane — a rule the
  drafter cannot satisfy — and it was found by a live run, not by the offline gate.

## Decisions

- **D1 — a second model pass, not a code-only validator.** The owner asked for the LinkedIn shape.
  The chain is `chainLlm` (`check_article_llm`) fed by `ai_model`/`ai_model_fallback` at
  `ai_languageModel` index 0/1, exactly as `check_rules_llm` is.
- **D2 — `PROBLEM` is data, not a throw.** `parse_article` no longer throws on over-budget; the
  loop decides. `MAX_WORDS` missing still throws: that is a caller bug, not a draft to retry.
- **D3 — one verdict node.** `merge_article_verdict` combines the reviewer's `<output>` with the
  parser's `PROBLEM` and emits the `output`/`explanation` the switch reads, so the retry decision
  has a single, testable input. It reads `parse_article` by paired item (`$('parse_article').item`),
  so a later attempt does not see the first attempt's numbers.
- **D4 — the bound is `MAX_TRIES = 3`**, set in `set_workflow_vars` beside `MODEL`/`MODEL_FALLBACK`.
- **D5 — `set_output` clears `ERROR`.** The accepted branch must not carry a stale reason from an
  earlier attempt, so it writes a literal empty string rather than forwarding `parse_article`'s.
- **D6 — no `ENABLE_CHECK` toggle.** The LinkedIn lane gates the review behind a trigger flag; the
  article lane always reviews, because an unreviewed draft is the thing being fixed. Adding the
  knob would be an unused switch.

## Risks / Trade-offs

- **Cost.** Every article now pays one extra model pass per attempt (up to 3). The alternative was
  a dead run; the pass is bounded and only re-runs on rejection.
- **A reviewer that always rejects** burns the bound and fails the run with
  `MAX_RETRIES_EXCEEDED: <reason>`. The reason is carried, so the failure is diagnosable, and the
  bound is what keeps it from being an infinite loop.
- **`CONTENT` in the review prompt.** The reviewer is given the fetched source so "no invented
  fact" is checkable. It costs context on every attempt; it is the one check a reviewer cannot make
  without the source.
- **The prompt halves are live on push, the graph is not.** A pushed `article_review.md` with a
  placeholder `Article Creator` does not pass stops every run until the graph is applied — the
  contract is asserted offline in `test_article_review_gate.py` to catch it before the push.

## Open Questions

- **Whether 3 attempts is the right bound for an article.** `MAX_TRIES = 3` is copied from the
  LinkedIn lane; an article attempt is more expensive (a research-capable agent turn), so the bound
  may want to be 2. Partly measured: 4 drafts cost ~5 minutes each run and **both** live probes
  exhausted the bound (executions 13892, 13913, 2026-10-18), each rejection a legitimate finding —
  an unsupported fact, or a closing paragraph that restates the article. Still `[UNVERIFIED]`
  whether a passing run is reached within the bound on a realistic row.
- **Whether the reviewer should see `CONTENT`.** Included for the fact check; if the pass proves
  slow or noisy, dropping it leaves length, markers and shape still checkable. `[UNVERIFIED]`.
- **The hero marker.** Fixed here for the requested-type id; whether `build_commit_files`'s
  fallback placement should remain at all, now that the prompt is correct, is a separate question.

## Definition of done

- `openspec validate --all` passes with this change present.
- `agents/n8n`'s offline suite passes, and `test_article_review_gate.py` fails without the change
  (retry edge, reason carry, bound, deterministic budget, marker contract).
- The export's two graph copies agree, and `test_code_nodes_parse.py` parses every new `jsCode`.
- The graph is applied live with `--require-edge`, read back, and the export diffed against live.
- A live run with a draft that first runs over `MAX_WORDS` produces a second draft inside the
  budget and publishes, rather than failing; a run whose drafts never satisfy the gate reports
  `MAX_RETRIES_EXCEEDED: <reason>`.
- Every `[UNVERIFIED]` above is either resolved or still marked as such.
