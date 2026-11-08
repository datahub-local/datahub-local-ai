# Tasks

## 1. The session stays inside the window

- [x] 1.1 `session-lib.mjs`: `DEFAULT_COMPACTION` (trigger 150,000, keep 20,000, minimum reserve
      16,384) and a `compaction` block in `agentSettings`, reserve derived from the context window.
- [x] 1.2 `agentSettings` refuses a trigger outside the window.
- [x] 1.3 `session-server.mjs`: pass the window and the two env overrides; log the trigger at boot.
- [x] 1.4 Tests: the derived reserve, a smaller window, and the two refused triggers.

## 2. The live row

- [x] 2.1 `2026-11-06T10-34-42-425Z_article-3.jsonl` renamed to `.jsonl.over-window` on the PVC.

## 3. Gates

- [x] 3.1 `node --test 'agents/adapters/pi-writer/test/*.test.mjs'` passes (57).
- [x] 3.2 `openspec validate --all` passes.
