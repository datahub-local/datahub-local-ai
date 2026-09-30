# Tasks

## 1. Make the AI-speak rule satisfiable

- [x] 1.1 Rewrite the banned-word rule in `agents/n8n/prompts/linkedin_post_rules.md:16` so a listed word is banned in its hype usage and allowed when it names the subject of the post (the component, product or technology the draft is about), and verify the file still contains exactly the placeholders the workflow supplies (`MIN_WORDS`, `MAX_WORDS`) by reading it against `download_post_prompt`'s `template_vars`
- [x] 1.2 Apply the same rule to the gate's own check list in `agents/n8n/prompts/linkedin_post_review.md:12`, and verify the file's placeholder set is unchanged (`RULES`, `EXTRA_PROMPT`, `URL`, `TEXT`, `VARIETY_DIRECTIVES`, `FEEDBACK`) so `DownloadTemplate`'s missing-variable check cannot start failing
- [x] 1.3 Confirm joint satisfiability by review against the article that failed (`https://arcprize.org/blog/astra`): record which rule would have rejected each of the five drafts in execution 11728, and confirm a draft can now satisfy every rule at once

## 2. Creator: convergent retries and an exact attempt bound

- [x] 2.1 Extend `parse_llm_check_output` to extract `<explanation>` alongside the existing `<output>` (trimmed, single line, absent-safe) and verify a stored check output from execution 11728 yields both fields
- [x] 2.2 Compose `download_post_prompt`'s `FEEDBACK` as the human feedback plus the gate's last explanation when the gate has already run in this execution (`$('parse_llm_check_output').isExecuted`), and verify the first attempt carries author feedback only while a rejected attempt carries the reason
- [x] 2.3 Rewire the retry edge from `switch_check_rules_llm`'s fallback to `download_post_prompt` (was `create_post_ai`) so a rejected attempt re-renders the prompt, and verify the edge with `--require-edge 'switch_check_rules_llm>download_post_prompt'`
- [x] 2.4 Reference the single trigger item with `.first()` instead of `.item` in `download_post_prompt` and `download_post_review_prompt` (both nodes now run inside the retry cycle) and verify paired-item resolution by reading a two-iteration execution after the change is live
- [x] 2.5 Change the bound in `switch_check_rules_llm` from `$runIndex > MAX_TRIES` to `$runIndex + 1 >= MAX_TRIES` so `MAX_TRIES` counts drafts, and verify by forcing a consistently rejected draft that exactly `MAX_TRIES` `create_post_ai` runs and `MAX_TRIES` `check_rules_llm` runs occur
- [x] 2.6 Compose `set_error_max_tries`' `ERROR` as the existing marker plus the gate's final explanation (single line, bounded length) and verify the value is non-empty, still greppable as a gate failure, and names a reason
- [x] 2.7 Apply 2.1–2.6 to both copies of the nodes in `agents/n8n/workflows/linked_in_post_creator.workflow.json` (top level and `activeVersion`) and verify the two copies are identical and the file parses

## 3. Failure report carries the reason and the article

- [x] 3.1 Delete `set_error_error` from `agents/n8n/workflows/linked_in_post_sharing.workflow.json` and connect `update_status_error` directly to `send_error_notification`, and verify the `CANCELLED` path still supplies its own `ERROR` value to the same notice
- [x] 3.2 Rewrite `send_error_notification`'s text to name the selected row's article URL, the reason from `ERROR`, and the execution id in place of the empty `$execution.url`, and verify against the live message that reported `Error Publishing Post () in LinkedIn: ERROR` for execution 11726
- [x] 3.3 Apply 3.1–3.2 to both copies of the nodes (top level and `activeVersion`) and verify the two copies are identical and the file parses

## 4. Tests and CI

- [x] 4.1 Add an offline structural test over the two exports that fails without this change: the retry edge targets `download_post_prompt`, the bound is `$runIndex + 1 >= MAX_TRIES`, `parse_llm_check_output` extracts the explanation, `download_post_prompt`'s `FEEDBACK` references the gate explanation, `set_error_max_tries` carries an explanation, and the sharing export has no `set_error_error` and a notice naming the article; verify it fails against the pre-change exports and passes against the post-change ones
- [x] 4.2 Run the offline n8n tests (`uv run -- pytest agents/n8n/scripts/ -q`) and verify the whole suite passes, including the existing export guards
- [x] 4.3 Add an n8n job to `.github/workflows/test-agents.yaml` (`paths: agents/n8n/**`) running `uv run -- pytest agents/n8n/scripts/ -q`, and verify the existing suite passes offline with no cluster, no credential and no network — today no CI job runs `agents/n8n/`, so 4.1's test would otherwise never gate

## 5. Apply to the live instance

- [ ] 5.1 Show the field-level diff for both workflows and get explicit approval before writing anything live, as the repo rule requires
- [ ] 5.2 Apply the creation of a throwaway probe pod (`--print-pod-overrides` + `kubectl cp` of the script, per the repo's apply notes) and verify the pod can reach the in-cluster n8n API
- [ ] 5.3 Apply the creator changes with `--require-edge` guards, re-read the workflow and verify the live graph and each changed field match the export
- [ ] 5.4 Apply the sharing changes likewise, re-read and verify the live graph matches the export
- [ ] 5.5 Verify the creator's schedule-independent path is untouched: `callerPolicy` and `settings` unchanged and no `errorWorkflow` added to the sub-workflow

## 6. Verify the fixed gate end to end

- [ ] 6.1 Create a temporary probe workflow (webhook trigger → `LinkedIn Post Creator`, `waitForSubWorkflow`) from a file outside this repository, and verify its webhook answers from inside the cluster
- [ ] 6.2 Invoke the probe with the exact inputs of execution 11728 (`CONTENT`, `EXTRA_PROMPT`, `URL` from execution 11726) and verify the run returns a non-empty `text` with an empty `ERROR` — the draft about the harness is no longer rejected on the AI-speak rule
- [ ] 6.3 Invoke the probe with a draft forced to fail (`ENABLE_CHECK=true` and an `EXTRA_PROMPT` that demands a banned word, or an invalid model id) and verify the second attempt's rendered prompt contains the gate's explanation and exactly `MAX_TRIES` drafts were produced
- [ ] 6.4 Verify a forced gate failure reaches a human legibly: the probe run's `ERROR` names a reason, and a failure routed through `LinkedIn Post Sharing` produces a Slack notice naming the article and the reason
- [ ] 6.5 Verify nothing is published on a failed run: no `send_2_linkedin_omImage` execution and no `LINKEDIN_URL`/`PUBLISHED_AT` on the row
- [ ] 6.6 Delete the probe workflow and verify it is gone from the live instance and absent from the repository (two `zz_*.workflow.json` probe exports are already committed from an earlier run; do not add a third)

## 7. Recover the failed row and record the lesson

- [ ] 7.1 Set `STATUS=QUEUE` on row 58 of `content_queue` (with `ERROR` cleared) and verify the row is selectable by the existing `select_article_to_post` ordering
- [ ] 7.2 Run `LinkedIn Post Sharing` once (manual trigger, or the next scheduled tick) and verify row 58 reaches its normal Slack approval step rather than `ERROR`, or fails legibly with a named reason
- [ ] 7.3 Record the failure class where it is read: a short paragraph in the n8n section of `AGENTS.md` stating that the gate's rules must be jointly satisfiable with the drafting rules, the evidence (row 58, execution 11728; the same word passing as often as it failed), and the two places the rule lives
