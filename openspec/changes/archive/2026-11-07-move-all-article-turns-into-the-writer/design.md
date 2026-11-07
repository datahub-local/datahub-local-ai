# Design

## D1 — One endpoint, a `task` field

The adapter already serves `POST /v1/chat/completions` for a draft. Review, aspects and improve
became tasks on the same endpoint rather than new routes: the session contract, the request body
and the error shape stay one thing, and a caller that omits `task` keeps drafting.

Rejected: `/v1/review`, `/v1/improve` routes. Three routes multiply the contract checks and the
tests for one behaviour that differs only in the prompt and the answer shape.

## D2 — One turn per request, n8n keeps the loop

The owner asked for the Visual Studio shape: maintain the session and share the feedback. So each
HTTP request is one model turn, and the loop that decides what happens next stays in n8n:

- the drafting gate decides retry or accept;
- `if_has_findings` decides edit or skip;
- `switch_improved_ok` decides retry once or converge;
- the Slack answer decides re-enter or stop.

Rejected: one call per round where the adapter drafts, reviews, edits and answers the final
article. It hides the verdict from the graph, makes each request long enough to hit the HTTP
timeout, and gives the human's feedback nowhere to enter between turns.

## D3 — The draft of record travels with the turn

`review`, `aspects` and `improve` carry `article: { title, text }`. n8n resolves it in the same
order it always did: the converged draft of this execution, the creator's answer, then the
`article_drafts` row. A review resumed in a later execution therefore edits the draft the human
read, not whatever the session still held from an earlier round. The adapter falls back to its
own `article.md` only when the request carries no draft.

## D4 — The prompts live in the image, once

`article_review.md`, `article_aspect_clarity.md`, `article_aspect_flow.md`,
`article_aspect_structure.md`, `article_improver.md` and `article_aspects.json` moved to
`agents/adapters/pi-writer/prompts/`. `article_aspects.json` names files beside itself.

Rejected: keep fetching prompts through `DownloadTemplate`. A prompt is part of the turn the
writer runs; fetching it from the n8n repository keeps a second deployable that can disagree
with the image, and the adapter cannot render a prompt it does not carry.

The registry is validated at boot, so a missing or empty registry stops the pod instead of
answering every aspect turn with no findings.

## D5 — No tools on the judging and editing turns

`review`, `aspects` and `improve` run `pi --no-tools`. They get the draft in the prompt and answer
in the response; they may not fetch a page again. The server writes the edited article itself,
from the `<article>` block the turn returns.

The drafting turn keeps its tools and proxy because reading the sources is the job.

## D6 — Deterministic gates stay in n8n

The review and edit turns are judgement. The budget, the asset markers and the ledger fidelity are
counts, and a count asked of a model is a count that gets invented (the 2026-10-30 lesson). So
`parse_article` and `check_improved_draft` stay in the graph and still win over any verdict.

## D7 — Failures are reported, never silent

- A gate turn that fails (timeout, 4xx, no verdict) becomes `output: false` with
  `REVIEW: HTTP <status>: <message>`, so the retry carries a real cause.
- An aspect turn that fails contributes no findings and the rest run; a whole-call failure says
  `aspects: unavailable` and the human feedback still drives the edit.
- An edit turn that fails leaves no article and is reported `FAILED`; `select_final_draft` keeps
  the gate-passed draft and names the failure to the reviewer. `NONE` means only "nothing to
  apply".
