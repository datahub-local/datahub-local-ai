# Design

## Gate findings

- Execution 16163 (row 4) started 08:39:54 and its `request_article` died at 08:54:54 — exactly
  900 s, the node's timeout — while execution 16160 (row 3) was still looping its draft.
- The adapter logged `turn failed: request cancelled`: the client's disconnect aborted the queued
  turn, so row 4's `pi` never ran and `article.md` stayed at the previous attempt's 06:14 copy.
- The queue was one module-level promise, so the wait was a property of the adapter, not of the
  row.
- The audit's turn took ten minutes (08:39:54 → 08:49:54), because it continued the writer's
  session and re-sent the whole transcript.

## D1 — Serialise the session, not the process

Pi's constraint is a shared JSONL file per session id. Two sessions share nothing: different
file, different run directory, different artifacts. Keying the queue by session id gives the same
protection with no cross-row wait.

## D2 — The allowlist is the intersection of the active turns

`articleHosts` was one module-level value because "turns are serialized". With concurrency that
assumption is gone. The proxy now computes the admitted set from every active turn and admits only
hosts all of them declared, so a turn that names fewer hosts can never be widened by a neighbour.

## D3 — A draft's artifact outlives its caller

The response is not the only output of a draft: `article.md` and `sources.json` are the contract,
and the caller fetches them by URL. Aborting on disconnect was right when the turn existed only
for its answer; for a draft it threw away minutes of work at the moment it was about to land. The
turn now finishes and logs that the caller hung up, and the next attempt edits the artifact.

## D4 — The audit does not need the draft's conversation

The audit's job is to compare the article against pages it can read from disk. A fresh session
cuts the prompt from the whole transcript to the article plus the gate list, which is what makes
ten minutes into seconds and stops the audit from hitting its own caller's timeout.

## Risks

- **Two model turns at once** share the pod's 1 CPU / 2 Gi. Both are mostly waiting on the model,
  but a second 500k-token turn is real memory. If it bites, the limit is the place to raise it.
- **A hung-up draft keeps spending** after the caller gave up. Bounded by Pi's own turn, and the
  alternative is spending it again.
- [UNVERIFIED] live: the audit's latency and quality in a fresh session, and two rows in parallel.

## Definition of done

- Two sessions' turns overlap; one session's turns do not.
- The proxy admits the intersection of the active turns' hosts.
- A draft whose caller disconnects still writes its artifacts.
- The audit runs in its own session and still reads the writer's transcript.
- The caller's timeouts are 30/15/15 minutes, live and in the export.
- Tests and `openspec validate --all` pass.
