# Design

## Gate findings

- 2026-11-09, row 3: three identical drafts rejected three times for `"team."`, `"hours."` and
  `"analyst."` — words inside a quoted `systemPrompt`. The block was correct; the verifier split a
  sentence into names.
- The same rule had already produced: five invented heredocs passed (the audit had no tools), a
  deleted examples section, a fallback to an unchanged draft, and two 15-minute timeouts.

## D1 — A count can gate, a judgement cannot

Shape, budget and markers are counts: deterministic, cheap, and false only if the code is wrong. A
provenance judgement over a model-written document is not a count; every attempt to make it one
produced a new false rejection. The reviewer, given the ledger and the transcript, is the right
instrument for it, and the human is the right authority.

## D2 — The reviewer runs after the gate and cannot reject

`switch_article_check`'s pass output goes to `build_review_request → request_review → review_note →
set_output`. `review_note` always returns notes; a transport failure becomes a note. The retry edge
stays bound to the counted checks only.

## D3 — The ledger is not thrown away

`sources.json` remains the record, and the audit's prompt receives the blocks no page carried as its
starting list. The difference is who acts on it: a person, with the draft in front of them.

## Risks

- An invented name can reach the human. The reviewer usually names it first, and the human reads the
  draft anyway; the cost of the alternative was four rounds of a correct article being rejected.
- A reviewer turn per draft costs a call. It is one call, not one per attempt, and it cannot fail
  the run.
- [UNVERIFIED] live until the next full row.

## Definition of done

- The gate's `PROBLEM` no longer includes ledger findings.
- The audit runs once per accepted draft and its findings appear in the Slack review message.
- A review failure adds a note and does not reject.
- Tests and `openspec validate --all` pass.
