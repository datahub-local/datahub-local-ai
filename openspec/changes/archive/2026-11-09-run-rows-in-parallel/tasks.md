# Tasks

## 1. Per-session turns

- [x] 1.1 Replace the module-level queue with one chain per session id.
- [x] 1.2 Proxy allowlist is the intersection of the active turns' hosts.
- [x] 1.3 Test: two sessions overlap, one session's two turns do not.

## 2. A draft survives its caller

- [x] 2.1 `close` aborts only a non-draft turn; a draft finishes and writes its artifacts.
- [x] 2.2 The response write is skipped when the client is gone, and logged.

## 3. The audit's own session

- [x] 3.1 The audit runs in `<session>-audit`; its evidence stays the writer's transcript file.

## 4. Deadlines

- [x] 4.1 `request_article` 1800000, `request_review` / `request_improve` 900000, live and in the
      export.

## 5. Gates

- [x] 5.1 `node --test 'agents/adapters/pi-writer/test/*.test.mjs'` passes.
- [x] 5.2 `openspec validate --all` passes.
