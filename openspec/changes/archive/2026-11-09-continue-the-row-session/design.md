# Design

## Gate findings

- Execution 16185 produced the walk-through the owner asked for; 16187, the next retry, produced a
  different article about provider configuration. The retry had a fresh session (by design of the
  one-turn change) and the previous draft was not passed at all, so the newest feedback read as the
  topic.
- The owner's intent, stated after the run: a session opens with the first draft and iterations stay
  in it.

## D1 — Session continuity beats transcript size

A fresh session per attempt bounds the prompt but throws away the fetched corpus, the sections
already agreed and the asks already applied. The ledger is derived from the transcript file, not
from the model's context, so compaction does not break verification; the cost is latency, which the
owner accepts.

## D2 — The draft still travels

The brief carries `previous_draft` from the entry point's draft of record. In a continuing session
it is redundant; when the session is gone or was reset it is the only thing that keeps the retry
from drafting a different article.

## Risks

- **Long rows get slow**, and a 500k window means compaction on every turn. Accepted.
- [UNVERIFIED] live: a whole row on one session with the new gate until the next run.

## Definition of done

- The session id is `article-<row>` live and in the export.
- `DRAFT_TEXT` reaches the sub-workflow on a human retry.
- `openspec validate --all` passes.
