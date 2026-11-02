# Design

## Context

Read off the committed exports and the run that failed.

- `article_creator.workflow.json`, `parse_article`: counts the body in code (markers stripped) and
  reports `OVER_BUDGET: <n> words against MAX_WORDS=<m>` as **data**; `merge_article_verdict`
  rejects on it whatever the reviewer said, and `switch_article_check` retries until
  `$runIndex + 1 > MAX_TRIES` (3, so four drafts).
- `article_content_writer.workflow.json`, `check_improved_draft`: the same check as the improvement
  pass's re-check, retried once by `switch_improved_ok` and then falling back to the gate-passed
  draft.
- `prompts/article_review.md`: "the body is at most `{{ MAX_WORDS }}` words and it is
  `{{ WORD_COUNT }}`. Over budget is a failure."
- Row 3, 2026-10-30: `MAX_RETRIES_EXCEEDED: OVER_BUDGET: 1248 words against MAX_WORDS=1200 …`,
  with the reviewer adding "cut roughly 50 words" and "everything else passes".

## Decisions

**The margin is proportional, 10%, computed in the check.** A fixed +50 would be 12.5% on a
400-word post and 4% on a 1200-word one, so the same tolerance would mean two different things. The
ratio is one expression in each of the two gates, and the twin test that already runs both nodes
against one fixture is extended to the boundary, so the copies cannot drift.

**The reviewer is handed the limit, not the budget.** `merge_article_verdict` requires the
reviewer's `true`, so a reviewer still enforcing `MAX_WORDS` would reject a 1248-word draft the code
accepts — the margin would exist in code and nowhere in effect. `parse_article` emits `WORD_LIMIT`
and the review prompt's check reads it; the raw budget stays in the prompt as context so the two
numbers are not confusable.

**Lenient gate, unchanged brief.** The writer and the improver still aim at `MAX_WORDS` (the owner's
call). A draft that lands on the cap is the intent; the margin only stops an overshoot of a few
percent from becoming a failed run.

## Risks

- **The published article may be up to 10% over the row's budget.** Accepted: `MAX_WORDS` is a
  length preference, and the alternative is losing runs over 48 words.
- **A draft 11% over still fails, and that is the point** — the tolerance absorbs counting error, not
  a writer that ignores the brief.
- **A retry that now passes carries fewer cuts than the reviewer asked for.** The retry is told the
  limit ("cut 30 words"), which is the number the gate enforces, so the loop converges on the same
  bound the gate uses.

## Open questions

- Whether the writer should aim a few percent under the cap so most drafts land inside
  `MAX_WORDS` rather than inside the limit. Rejected for now: it shortens every published article to
  fix an overshoot the margin already absorbs.

## Definition of done

- Both gates accept a draft inside the margin and reject past it, verified by executing the
  committed `jsCode`.
- The reviewer's length check reads the limit the code enforces, and the prompt's placeholders match
  the variables the node supplies.
- `openspec validate --all` and the n8n test suite pass.
- [UNVERIFIED] live: the graph has to be applied to the running instance before the margin exists
  there, and the prompt is live on push — so the graph goes first (a pushed prompt naming a variable
  the graph does not pass stops every run).
