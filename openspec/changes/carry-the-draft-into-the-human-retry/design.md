# Design

## Context

Read off the committed exports, the prompts, the live graph and the run that failed.

- `article_content_writer.workflow.json`: `switch_article_retry` (the human's `Retry` answer) loops
  back into `execute_article_creator` — the *same* node as the first call. Its mapping passes
  `TOPIC`, `DESCRIPTION`, `URL`, `CONTENT`, `MAX_WORDS`, `ASSET_TYPES`, `EXTRA_PROMPT` and `FEEDBACK`
  (the human's feedback or the row's `ARTICLE_FEEDBACK`), and no draft.
- `linked_in_post_sharing.workflow.json`: identical shape, `switch_user_retry → execute_post_creator`,
  with `FEEDBACK` from `notification_retry_or_cancel` and `HOOK` from the row.
- `article_creator.workflow.json`, `download_article_prompt`: `PREVIOUS_DRAFT` reads
  `parse_article`, which exists only within one invocation, so a fresh invocation renders it empty —
  and `prompts/article_writer.md` reads an empty block as "this is the first attempt".
- Live run 14178: `Article Content Writer`, `waiting` on the approval form; 14180 (first authoring,
  2 attempts, the internal retry carrying the draft), then 14187 and 14191, two human retries, each
  with a populated `FEEDBACK` and an empty `## Previous Draft`. Each of the two retries made **one**
  drafting attempt, so the regeneration is the fresh-write path and not the internal loop.
- The draft is durable on the article side (`article_drafts` DataTable, `ARTICLE_TEXT` by
  `ENTRY_ID`, written by `store_draft` and read by `read_draft_for_publish`) and **nowhere** on the
  post side: `content_queue` has no post column (`URL TITLE STATUS PRIORITY SCORE ORIGIN TOPIC SOURCE
  RATIONALE EXTRA_PROMPT MAX_WORDS PUBLISHED_AT UPDATE_DATE RELEASE_DATE LINKEDIN_URL ENTRY_ID ERROR
  EXECUTION_ID row_number`), and the post text reaches Slack as
  `$('execute_post_creator').item.json.text` and is then dropped.

## Gate findings

- **The retry already sits in the run, so the draft is in memory.** The human answers the approval
  inside the same execution; the loopback edge re-enters the call node that produced the draft being
  reviewed. A second source (a DataTable read, or persisting the post) would be a copy of state the
  run still holds — and on the post side it would need a new table plus a manual creation step,
  because the lane stores nothing today.
- **A node may read its own earlier runs, and it returns the run before the current one.** Verified
  live 2026-10-18 with a throwaway probe workflow (created, fired over its own webhook, read,
  deleted): a cycle `hook → step → gate → step` with `round = $('step').isExecuted ?
  $('step').last().json.round + 1 : 0` produced `step` run 0 = `{round: 0, seen: -1}` and run 1 =
  `{round: 1, seen: 0}` (execution 14195). So `.last()` on the second execution is the **first**
  execution's output — the draft the human just rejected — and not the row being built. This is the
  one property no offline case can show, and the reason the expression is not read as speculation.
- **`.last()`, never `.first()`.** On a third invocation `.first()` would re-send the *first* draft
  while the human reviewed the second, which is the non-convergence the internal loop's own design
  already records (`carry-the-rejected-draft-into-the-retry`, D1).
- **`isExecuted` is still required.** The first pass runs the same node, where the reference would
  throw rather than be empty.
- **The sub-workflow's fallback must not displace the in-run draft.** Inside one invocation the
  internal reviewer's retry must keep editing *its own* attempt: `parse_article.isExecuted` wins, and
  the caller's value is only the fallback. Reversing the order would send a human-retry draft into an
  internal retry — the three-attempt loop would edit the wrong text.
- **No placeholder set changes, so no push order this time.** Both prompts already declare
  `PREVIOUS_DRAFT` / `PREVIOUS_POST` and both call nodes already supply them (as `""`); only the value
  changes. `DownloadTemplate` scans for names, not for emptiness, so the graphs and the prompt files
  can be pushed in either order — and neither prompt file needs an edit at all.

## Decisions

- **D1 — the entry point carries the draft**, as
  `$('execute_article_creator').isExecuted ? ($('execute_article_creator').last().json.text || "") : ""`
  and `$('execute_post_creator')` likewise.
- **D2 — the sub-workflow falls back to the trigger**: `parse_article.last().TEXT` when it has run,
  else `main_trigger.PREVIOUS_DRAFT || ""`. `PREVIOUS_DRAFT` / `PREVIOUS_POST` join the trigger's
  declared inputs and the call node's schema.
- **D3 — no prompt changes.** The instruction the prompts already carry ("keep what the review did
  not object to and change only what the feedback names") is what a human retry needs.
- **D4 — the offline cases move to the half that was unguarded**: the entry point's mapping, in each
  lane, and the trigger fallback in the sub-workflow.

## Risks / Trade-offs

- **A 1200-word draft now travels through the sub-workflow call.** It already did on the internal
  retry (a 24,675-char prompt on 14180 attempt 1); the human retry was the only path without it. The
  item is a string in the run, not a binary, so it costs no `binary_data` row.
- **A human feedback that asks for a restructure will still rewrite most of the draft** — that is the
  instruction, not a defect. Run 14187's "simpler, different sections" is that case; 14191's "top 5
  features" is the one this change is for.
- **Round identity is unchanged.** `store_draft` still increments `ROUND` and overwrites the
  DataTable row per `ENTRY_ID`, so the durable copy holds the latest draft; nothing reads a
  per-round history and this change does not add one.

## Open Questions

- **Whether the human retry should also skip the research tools**, as the internal retry's prompt
  text already tells the article writer to do. The prompt says it; the tool surface is the caller's
  to choose and `if_needs_research` is driven by whether the entry carries a source, so a row with no
  source still hands the retry its tools. Not measured yet — the row in run 14178 carries its README.
- **Whether a third human round is worth forbidding.** Each round spends a full authoring turn; the
  queue's `cancel_after_days` ceiling is the only bound today.

## Definition of done

- `openspec validate --all` passes with this change present.
- The new cases fail without the change: the entry point's mapping has no `PREVIOUS_DRAFT` /
  `PREVIOUS_POST`, and the sub-workflow's trigger declares neither.
- Both graphs (four exports, both copies each) agree with themselves and pass the offline suite and
  `ruff`.
- Applied live with `--require-edge` and read back, then diffed against the exports.
- One human retry observed to keep the parts the feedback did not name.
