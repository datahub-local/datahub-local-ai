# Design

## Context

See `proposal.md` — Why. The relevant mechanics, all read from the live instance:

- `LinkedIn Post Creator` (id `PaeHFdCsdoVbQx11`) is a sub-workflow of `LinkedIn Post Sharing` (id `oxARWWyxenKgmv6A`). Its graph is fixed:
  `main_trigger → download_post_rules_prompt → set_workflow_vars → download_post_classify_prompt → classify_content → set_variety_directives → download_post_prompt → download_post_system_prompt → create_post_ai → parse_llm_output → if_enabled_check → (download_post_review_prompt → check_rules_llm → parse_llm_check_output → switch_check_rules_llm)`, with `switch_check_rules_llm` sending output 0 (accepted) to `set_output`, output 1 (bound reached) to `set_error_max_tries`, and its fallback (rejected) straight back to `create_post_ai`.
- The prompts are not embedded: `DownloadTemplate` reads them out of this repository over the GitHub API at run time (`$env["BACKUP_GITHUB_REPO_OWNER"/"_NAME"/"_PATH"]`), so prompt edits are live on push and workflow edits are not.
- `set_workflow_vars` sets `MAX_TRIES = 3`; the bound condition is `$runIndex > MAX_TRIES` on `switch_check_rules_llm`, and the switch's own run index counts one per submitted draft — so `MAX_TRIES = 3` produced 5 drafts in execution 11728 (verified: 5 `check_rules_llm` runs, 5 `create_post_ai` runs, 3m44s).
- The drafting prompt (`prompts/linkedin_post.md`) and the review prompt (`prompts/linkedin_post_review.md`) both carry a `Reviewer Feedback` block that is `HIGHEST PRIORITY` and wins over every other rule. `download_post_prompt` fills it from `main_trigger.FEEDBACK`, which is the *human* rejection text and is empty on a scheduled run — which is why five attempts were indistinguishable.
- Both failure paths in `LinkedIn Post Sharing` (`check_subworkflow_error` for the draft, `check_subworkflow_error_image` for the image) reach the same notice through `update_status_error → set_error_error → send_error_notification`, and `set_error_error` replaces the sub-workflow's `ERROR` with the literal string `"ERROR"`. The notice's own `{{ $execution.url }}` rendered empty in the live message (`Error Publishing Post () in LinkedIn: ERROR`).
- The live workflows and the exports under `agents/n8n/workflows/` were byte-identical for the creator at review time, so the export is a safe edit target.

## Goals / Non-Goals

**Goals:**

- Remove the class of failure where two enforced rules cannot both hold for a source, and make a rejection informative enough that the next attempt differs.
- Make the failure of a run legible from the two places a human actually looks: the sheet row and the Slack notice.
- Keep the change reviewable in this repository and reproducible against the live instance.

**Non-Goals:**

- Full determinism of the gate. The gate is one model call judging several criteria, and it remains a model call; this design makes the *rule* decisive for the subject-term case and gives the run a legible failure, it does not promise a stable verdict.
- Replacing the gate with a deterministic check, or splitting the banned-word test out of it. Both are plausible follow-ups (see Open Questions); the count and feedback fixes deliver most of the value for two lines of prompt and one rewired edge.
- Salvaging a rejected draft. On a gate failure the row is marked and the article is retried from scratch; publishing a draft the gate rejected is not considered.
- Anything in the blog `content-writer` flow, the curator, the image branch or the sheet schema.

## Decisions

### 1. The AI-speak list keeps the word and gains the verb/noun distinction

`linkedin_post_rules.md` bans a list of overused words; `harness` is on it as the verb ("harness the power of X"), which is what makes AI copy read as AI copy. The failure is that the same string is the standard technical noun for the component the article is about, and the rules *require* naming that component. Deleting the word from the list leaves "harness the power of" unbanned and treats a symptom; splitting hype from subject term fixes the contradiction that caused the failure. The same sentence is applied to `linkedin_post_review.md`, which names `harness` in its own check list, so the writer and the gate read the same rule.

The rule text says the noun is allowed *when it names the subject of the post* rather than listing exceptions per word, so the reasoning generalises to the next collision (`delve` in an article about a tool called Delve, `landscape` in a post about a product by that name).

**Alternatives considered:** remove `harness` (weakens the intent, does not generalise); allow-list technical terms at run time by matching the source content (the gate does not receive the source content, and adding it would grow the prompt for one word); route such articles to manual review (leaves a permanent manual workaround for a model-side rule).

### 2. The rejection reason reaches the next attempt through the existing feedback slot

The retry edge moves from `switch_check_rules_llm` (fallback) → `create_post_ai` to → `download_post_prompt`, so a rejected attempt re-renders the drafting prompt with the reason in the `Reviewer Feedback` block, which is already declared `HIGHEST PRIORITY` and already overrides the other rules. `parse_llm_check_output` extracts `<explanation>` next to the `<output>` it extracts today, and `download_post_prompt` composes `FEEDBACK` as the human feedback plus, when the gate has already run in this execution, the last explanation. The gate therefore cannot reject twice for a reason it named once, and the loop needs no new node.

The feedback is added at the prompt-rendering node rather than as a second chain message because the prompt template is where the existing, tested feedback path lives; a per-iteration message on `create_post_ai` would have to reference a node that has not run yet on the first pass, which fails the workflow rather than degrading.

**Alternatives considered:** re-run `create_post_ai` with an extra appended instruction composed by a Code node (more moving parts, a second place that renders the prompt); raise `MAX_TRIES` and hope sampling finds a pass (blind, and today's five drafts all failed on the same word).

### 3. The bound counts drafts

`$runIndex` on `switch_check_rules_llm` is 0 for the first submitted draft, so `$runIndex > MAX_TRIES` spends `MAX_TRIES + 2` drafts. The condition becomes `$runIndex + 1 >= MAX_TRIES`, which makes the constant mean what its name says: three drafts. This is the intended meaning, and it removes four of the ten model calls a failure costs today.

### 4. The reason is carried in `ERROR` and the notice is rewritten

`set_error_max_tries` composes `ERROR` as the existing marker plus the gate's final explanation, single-line and truncated, so the value stays greppable as a gate failure while naming a reason. `set_error_error` is deleted rather than corrected — it exists only to hand the notice *something*, and what it hands it is the reason's loss — which leaves `update_status_error → send_error_notification` and keeps the `CANCELLED` path (which sets its own `ERROR`) working. The notice text takes the article URL from the selected row and adds the execution id in place of the empty `$execution.url`.

**Alternatives considered:** keep `set_error_error` and add a second field for the reason (keeps a node whose only job is to destroy information, and two fields where one suffices); put the reason only in the sheet (the notice is what interrupts a human's day).

### 5. Verification uses a throwaway webhook probe, then the real pipeline

No public n8n API can run a workflow, and the sub-workflow's real trigger is the caller, so the fixed gate is exercised before the next scheduled slot by creating a temporary workflow whose webhook trigger calls `LinkedIn Post Creator` with the same `CONTENT`/`EXTRA_PROMPT`/`URL` that failed, invoking it in-cluster by `curl`, reading the execution, then deleting it. The passing case (the harness article) and a forced-rejection case (a banned hype verb, to see the feedback land in the next attempt) are both observable this way. The end-to-end confirmation is then the real pipeline on row 58 after it is returned to `QUEUE`, by manual run or the next tick.

## Risks / Trade-offs

- [Paired-item resolution across the retry loop] `download_post_prompt` and `download_post_review_prompt` reference `$('main_trigger').item`, and a second iteration resolves through a cycle → reference the single trigger item with `.first()` in both nodes, as `set_variety_directives` already does, and verify a rejection path end to end.
- [The gate may still reject for a reason the explanation cannot fix — subject switch, hook mismatch, word count] → the bound stops the run, and the reason now reaches the sheet and Slack instead of being replaced by `"ERROR"`.
- [The verb/noun distinction is prose, and the gate is a small model] → the rule is decisive for the case that failed and the failure is legible; a gate that misapplies it now costs a legible error rather than a silent one. Not a guarantee, hence the Open Question below.
- [Each rejected draft adds two GitHub file reads] → against four model calls removed by the bound, and only on rejection paths.
- [Editing live workflows mid-flight] → both changes go through `scripts/apply_workflow_changes.py` with `--require-edge` guards and a re-read after the PUT; the schedule fires twice a week at 10:30 UTC, so the apply is done outside that window.
- [The export and the live instance can drift] → the exports were verified identical to live before planning; the apply is followed by re-reading both workflows and diffing them against the exports.

## Migration Plan

1. Push the two prompt files (live immediately for every subsequent run).
2. Apply the creator changes, then the sharing changes, with `--require-edge`; re-read and diff each against the export.
3. Create the probe workflow, exercise the passing and rejecting paths, delete it.
4. Set row 58 to `QUEUE` and let the pipeline (manual run or next tick) confirm end to end.

Rollback is the reverse: re-apply the previous field values (the exporter is field-level, so the prior values are the ones in git), and revert the two prompt files. A prompt revert is enough to restore the old gate behaviour; the loop and notice changes are independent of it.

## Open Questions

- Whether the banned-word judgement should move out of the gate's model call into a deterministic check (the repo's own policy is that deterministic logic belongs in code), and whether the gate should run on a different model from the writer. Both are follow-ups that would change the spec only if the gate's contract changes; neither is required for this fix.
