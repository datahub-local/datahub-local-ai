# Design

## Gate findings

- After the previous change the graph runs `check_draft_error → first_draft → derive_slug`, and
  `switch_article_retry` points at `execute_article_creator`. Two spec requirements still said the
  lane calls `aspects` and `improve`, and that a human retry re-enters the improvement pass.
- The removed improvement pass also owned the "a feedback round may fence an unverified block"
  exception; with the name-based ledger that exception has no subject.

## D1 — A retry is a re-draft, not an edit

The edit existed to avoid re-reading sources. Continuation instead grew the session until
compaction dropped the evidence. A re-draft starts clean, is seeded with the previous draft and the
feedback, and passes the same drafting gate — one rule for every round.

## D2 — The task list is a capability, not a schedule

`Article Creator` still serves `review`, `audit`, `aspects` and `improve`; the entry point decides
that only `draft` runs automatically. Keeping the tasks costs nothing and lets a human ask for an
audit without a new deployment.

## Risks

- **A re-draft may drift from what the person liked.** The previous draft is in the brief and the
  feedback says what to change; the human review catches drift, and the alternative was a 26-minute
  edit on a 7 MB session.
- [UNVERIFIED] live: a human retry on the new graph until the next run.

## Definition of done

- The spec's entry point and retry requirements match the graph.
- `openspec validate --all` passes.
