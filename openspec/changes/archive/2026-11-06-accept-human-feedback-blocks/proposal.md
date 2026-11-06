# Proposal

## Why

A person asked for two changes to a draft they had just read: number the sections, and add the
prerequisite commands for a local cluster and an LLM provider secret, each in a block with its
expected output. The board answered with the **byte-identical draft** — 7716 characters, 1184
words, the same title — and the run was reported as improved.

The draft did not change because the code re-check only accepts a fenced block that `sources.json`
records as read verbatim from a fetched page, and the Sympozium docs carry neither `kind create
cluster`, the provider key's Secret command, nor a sample of their output. The improver obeyed the
rule, returned the draft, and nothing downstream noticed that a round had changed nothing.

Two defects, one run. Neither is a prompt-wording problem:

- **A human's request outranks a ledger.** The rule exists so a first draft cannot invent a command
  and present it as sourced. When a person names the command, the person is the source, and
  refusing to write it is the lane ignoring its reviewer.
- **An unchanged answer was called an improvement.** A round that returns what it was given has
  applied nothing, and reporting it as improved sends the same draft back for a second rejection.

## What Changes

- **A feedback round may add fenced blocks no fetched page carries.** `check_improved_draft`
  accepts them only when the round carries human feedback, counts them, and reports
  `FIDELITY: "feedback"` and `UNVERIFIED: n`. Blocks the ledger does carry and that failed —
  `found: false`, a failed dry-run, a drifted excerpt — still fail on a feedback round, and the
  first-draft gate keeps its strict rule.
- **An unchanged round is reported, not improved.** `check_improved_draft` sets `UNCHANGED` when
  the returned body and title equal the ones it was given; `select_final_draft` names the outcome
  `UNCHANGED`, keeps the draft of record, and says the feedback was not applied.
- **The review message names both.** `notify_article_review` adds the unverified count, so the
  reviewer is told which blocks their feedback introduced and that no source carries them.
- **`article_improver.md`** states the feedback-round exception and that a feedback round must
  change the draft.

## Capabilities

`content-writer`.

## Out of scope

- Re-drafting from the sub-workflow on a retry: the spec forbids re-entering it, and the draft the
  person read is the material.
- Verifying an added command against a live cluster: the count is a report to the human, not a
  gate.
- The row that produced the failure (`gh-80`) is not rewritten by this change.
