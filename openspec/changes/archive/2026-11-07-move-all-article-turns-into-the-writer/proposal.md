# Proposal

## Why

The article lane still called models inside n8n. `Article Creator` ran the publish gate as a
`chainLlm` node, and `Article Content Writer` ran the three aspect reviewers as a second
`chainLlm` plus the improvement edit as an agent with tools. The writer adapter only drafted.

That split breaks the owner's rule of 2026-11-07: writer agents do every model turn, and review
feedback always reaches the writer. A human rejection entered the n8n improver and never the
writer session, so the feedback the writer was supposed to apply never reached it. The Slack
message carried only finding counts, never the findings. The prompts themselves were split:
drafting in the adapter image, review/aspect/improver under `agents/n8n/prompts/`.

## What Changes

- **The writer adapter gains three tasks.** `POST /v1/chat/completions` takes a `task` field:
  `draft` (default), `review`, `aspects` or `improve`. All four run in the same Pi session, so
  the draft, the fetched corpus and the ledger stay in one conversation.
- **The prompts move into the adapter image.** `article_review.md`, the three aspect prompts,
  `article_improver.md` and `article_aspects.json` move from `agents/n8n/` to
  `agents/adapters/pi-writer/prompts/`; the n8n copies are deleted.
- **`Article Creator` posts the review turn.** `parse_article` → `build_review_request` →
  `request_review` → `parse_review_verdict` → `merge_article_verdict` → `switch_article_check`.
  The four model nodes and the three prompt-download nodes are removed.
- **`Article Content Writer` posts the aspect and edit turns.**
  `build_improvement_context` → `build_aspects_request` → `request_aspects` →
  `merge_aspect_findings` → `if_has_findings` → `build_improve_request` → `request_improve` →
  `check_improved_draft` → `switch_improved_ok`. The model nodes, the prompt-download nodes,
  the aspect fan-out and the writer-rules fetch are removed.
- **The deterministic gates stay in n8n.** Word budget, asset markers and ledger fidelity are
  still counted in code by `parse_article` and `check_improved_draft`; the review, aspect and
  edit turns only supply judgement and text.
- **A failed turn is data.** A gate turn that cannot answer is a rejection with
  `REVIEW: HTTP <status>: <message>` as the explanation, so the retry carries the cause. An
  edit turn that cannot answer is reported `FAILED`, not `NONE`. An aspect turn that fails
  contributes no findings and the rest still run.

## Capabilities

`content-writer`.

## Out of scope

- Every other lane keeps its n8n model nodes; this is the article lane only.
- No prompt wording change beyond `article_aspects.json` now naming files beside itself.
- The live apply needs the published image digest and owner approval; the pull request carries
  the graph change, the deployment half is reported to the owner.
