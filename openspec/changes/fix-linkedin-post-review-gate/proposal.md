# Proposal

## Why

On 2026-09-30 the `LinkedIn Post Sharing` run for row 58 (`https://arcprize.org/blog/astra`) failed with `MAX_RETRIES_EXCEEDED`: the `LinkedIn Post Creator` internal reviewer rejected all five drafts because the source is about an agent **harness** and `"harness"` is on the banned AI-speak list, while the drafting rules simultaneously require naming the technology from the source. Those two rules cannot both be satisfied for such a source, so no draft can pass and the run can never succeed. The same rule is also applied inconsistently — executions 11317 and 11311 passed in the same week with the word used 8 and 7 times — so the gate's verdict on a legitimate technical term is effectively a coin flip, and today it cost a queued article a full run.

## What Changes

- **Make the drafting and review rules jointly satisfiable.** The banned AI-speak list keeps `harness` as a banned *verb* ("harness the power of") and allows it as the *noun* naming the technology under discussion, in both `linkedin_post_rules.md` and `linkedin_post_review.md`, so a rule can no longer require a word that another rule forbids.
- **Make retries converge.** The reviewer's `<explanation>` is carried into the next attempt's prompt through the existing `Reviewer Feedback` slot, instead of the current blind resampling of the unchanged prompt. A rejection for the same reason therefore cannot repeat.
- **Fix the attempt bound.** `switch_check_rules_llm` currently gives `MAX_TRIES + 2` drafts under a constant named `MAX_TRIES` (5 drafts for `MAX_TRIES = 3`, 10 model calls, 3m44s); it will produce exactly `MAX_TRIES` drafts.
- **Make the failure report carry its reason and its article.** The gate's last explanation becomes part of the `ERROR` value, `set_error_error` (which overwrites the real reason with the literal string `"ERROR"`) is removed, and the Slack notice names the article and the execution instead of the empty `$execution.url`.
- The failed row 58 is returned to `QUEUE` so the corrected pipeline retries it.
- **No change** to the sheet structure, the queue/publish logic, the image branch, the content curator, the blog (`content-writer`) flow, or the model in use.

## Capabilities

### New Capabilities
- `linkedin-post-publishing`: the scheduled pipeline that turns a queued source article into a published LinkedIn post, and specifically the internal review gate that decides whether a draft goes on to human review — which rules it may reject on, how a rejected draft is regenerated, how many attempts it gets, and how a gate failure is recorded and reported.

### Modified Capabilities
<!-- None. `openspec/specs/` is empty; no capability has landed yet. -->

## Impact

- **`agents/n8n/prompts/linkedin_post_rules.md`, `agents/n8n/prompts/linkedin_post_review.md`**: the banned-word rule gains the verb/noun distinction. Fetched from GitHub at run time by `DownloadTemplate`, so these take effect on push, with no workflow apply.
- **`agents/n8n/workflows/linked_in_post_creator.workflow.json`**: `parse_llm_check_output` extracts the explanation; the retry edge returns through `download_post_prompt` instead of straight to `create_post_ai`; `download_post_prompt` merges the last explanation into `FEEDBACK`; `switch_check_rules_llm`'s bound changes; `set_error_max_tries` carries the reason.
- **`agents/n8n/workflows/linked_in_post_sharing.workflow.json`**: `set_error_error` is deleted (both the draft and image failure paths reach the same notice through it) and `send_error_notification`'s text names the article and the execution.
- **Tests and CI**: an offline structural test over the two exports that fails without the gate fix, plus an `agents/n8n/**` job in `.github/workflows/test-agents.yaml` — no CI job runs `agents/n8n/` today (`test_workflow_exports.py` has never gated anything), so the new test needs one to be a gate rather than a habit.
- **Live n8n**: both workflow changes are applied with `scripts/apply_workflow_changes.py`, guarded by `--require-edge`; a temporary webhook-invoked probe workflow verifies the gate before it is deleted; row 58 in `content_queue` is set back to `QUEUE`.
- **`AGENTS.md`**: the n8n section gains the durable lesson (the gate's rules and the drafting rules must be jointly satisfiable, and a gate failure must name its reason).
- **Cost**: each rejected draft now costs one extra `DownloadTemplate` round trip (two files) — noise against the four model calls the count fix removes.
