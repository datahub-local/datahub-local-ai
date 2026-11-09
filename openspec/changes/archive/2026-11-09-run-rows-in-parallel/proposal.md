# Proposal

## Why

Two `Article Content Writer` executions ran at once, each with its own row. The adapter
serialised every session through one queue, so row 4's draft waited behind row 3's turn and hit
the caller's fifteen-minute timeout without ever starting. n8n closed the connection, the adapter
aborted the queued turn, and the row went to `ERROR` — the draft was not lost because of the
model, but because one row's work blocked another's until the deadline.

The same round showed the second half: the audit runs inside the writer's session, so a turn that
only needs the artifacts re-sent a 500k-token transcript and took ten minutes, exactly its own
timeout.

## What Changes

- **Turns serialise per session, not per adapter.** Two rows have different transcript files,
  run directories and artifacts; they run at the same time. Two turns of one session still take
  turns, because they share that file.
- **The proxy admits only what every active turn declared.** Concurrency must not widen an
  allowlist: the admitted set is the intersection of the active turns' hosts.
- **A draft survives a caller hang-up.** When the caller closes the connection, a drafting turn
  finishes and writes `article.md` and the ledger anyway, so the row's next attempt adopts it
  instead of paying for it again. Every other task exists only in its response and still cancels.
- **The audit runs in its own session.** Its prompt is the article, the gate list and the
  prompts, not the draft conversation; its evidence is the writer's transcript file, which it
  greps.
- **The caller's deadlines match the work.** `request_article` 15 → 30 min, `request_review` and
  `request_improve` 10 → 15 min.

## Capabilities

- `content-writer`

## Impact

- `agents/adapters/pi-writer/session-server.mjs`, tests.
- `agents/n8n/workflows/article_creator.workflow.json` and the live workflow: three timeouts.

## Non-goals

- No change to the gate, the ledger derivation, the prompts' rules or the graph.
- The lane still handles rows one execution at a time; concurrency is not introduced on purpose.
