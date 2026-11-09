# Design

## Gate findings

- `deriveLedger` accepted only a byte copy. The Ensemble and MCPServer blocks the owner asked for
  were composed from the docs' own field names and rejected four times in a row; the same session
  then produced a draft with zero fences, and `sources.json` came back `{"sources":[]}`.
- The audit could not settle it: it argued "both rejected blocks are the pages' own text" because
  the rule it was checking was the one that produced the rejection.
- Round 3 (2026-11-09) took 26 minutes for one draft turn on a 7.3 MB session; the previous run's
  audit spent 10 minutes and hit its own timeout.

## D1 — Evidence is the names, not the bytes

A composed block is how an article shows a resource: the docs print one object, the article needs
another with the same schema. Requiring byte equality made the correct article unpublishable. The
replacement check is: the block parses by its language, and every name in it is on a page this
session read. `my-first-agent-heartbeat` — the name an earlier run invented — is still rejected,
which is the property the byte rule existed to protect.

Byte equality keeps its own path because a copied command has to be exact; the ledger records
`mode: quoted` for it and `mode: derived` otherwise, and the gate reads the mode.

## D2 — Language-aware name extraction

YAML: every key, and every value token that looks like a name (digit or separator). Shell: the
command head, flags, assignments and paths. JSON: parsed, then keys and string values. Anything
else: the distinctive tokens only. Plain words are not evidence — "the" being on a page proves
nothing — which is why only names are checked.

## D3 — One turn, because the seams were the failures

The audit, the aspect pass and the edit each cost a model turn, a timeout and a way to fail apart
from the draft. The lane now runs the writer once, gates its answer in code, and presents it. The
human review is unchanged. The tasks stay on the adapter for on-demand use.

## D4 — A retry is a new session

Continuation was meant to save a re-read of the sources. Instead it grew the transcript until
compaction dropped the pages the ledger needed, so the retry could not prove what the first draft
had fetched. A retry now starts clean, is seeded with the previous draft and the gate's reason,
and re-fetches only what it needs.

## Risks

- **Name coverage is weaker than byte equality.** A block can pass while a value is wrong if every
  name appears somewhere. Bounded by the strongest part: object names, images and kinds are
  checked individually, and a fabricated name still fails.
- **No second opinion.** The audit sometimes caught a missing section. That judgement now rests on
  the human review; the spec records it as the accepted cost.
- **The name extractor is a heuristic**, not a YAML parser; it rejects a malformed line but cannot
  prove a document valid. [UNVERIFIED] until a live run.
- Two attempts may be too few for a hard entry. The row still reaches the human with the reason.

## Definition of done

- A composed block whose names are on a read page passes; an invented name fails and is named.
- The lane calls `draft` once, gates it, and presents it; no aspect or edit call.
- A retry is a fresh session with the previous draft and the reason; `MAX_TRIES` is 2.
- `check-article` reports the missing names.
- Tests and `openspec validate --all` pass.
