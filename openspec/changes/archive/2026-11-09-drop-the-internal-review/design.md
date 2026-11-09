# Design

## Gate findings

- Execution 16184 (2026-11-09): attempt 1 failed on the unquoted check, attempt 2 passed every
  counted check, the audit rejected it anyway, attempt 3 ran and passed — 3 drafts, 7 minutes.
- The audit's own instruction forbids it from reporting the counts code owns, so the only thing it
  could add was judgement — which the human review already makes, with the draft in hand.

## D1 — One automatic gate

`parse_article` already counts the budget, the markers, the source ledger and the session errors.
`gate_verdict` turns that into the branch the retry loop reads. The human review is the judgement
step; a rejected draft still reaches the human with the reason after the bound.

## D2 — The reason is the gate's own

`set_error_max_tries` reads `explanation`; `gate_verdict` puts the parser's `PROBLEM` there, so the
retry and the failure answer name the same cause the gate reported, with no paraphrase.

## Risks

- A missing requested section is no longer caught before the human sees the draft. That judgement
  was the audit's, and the accepted cost of one turn is that the human makes it.
- [UNVERIFIED] live until the next attempt runs on this graph.

## Definition of done

- The graph branches on `gate_verdict`; the review chain is gone from live and the export.
- `openspec validate --all` passes.
