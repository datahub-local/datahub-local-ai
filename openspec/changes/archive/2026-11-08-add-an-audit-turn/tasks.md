# Tasks

## 1. The audit turn

- [x] 1.1 `prompts/article_audit.md`: the job, the four things it judges, the lookup cap and the
      answer shape.
- [x] 1.2 `session-server.mjs`: `audit` in `TASKS`, `auditPrompt`, a branch that runs with tools,
      and a result carrying the review verdict plus findings appended to the explanation.
- [x] 1.3 Tests: the verdict, the findings reaching the explanation, and tools offered.

## 2. The writer checks itself

- [x] 2.1 `bin/check-article.mjs`: derives the ledger from the session transcript and prints a
      `MISSING:` line per unquoted block.
- [x] 2.2 `session-server.mjs`: pass `PI_WRITER_SESSION_ID` and `PI_WRITER_SESSION_DIR` to the turn.
- [x] 2.3 `Dockerfile`: install the command; `writing.md` tells the turn to run it before answering.
- [x] 2.4 `PI_WRITER_THINKING` moves the reasoning level and the level map covers it.

## 3. The caller

- [x] 3.1 `Article Creator` `build_review_request` sends `task: 'audit'`, applied live and mirrored
      into the export.

## 4. Gates

- [x] 4.1 `node --test 'agents/adapters/pi-writer/test/*.test.mjs'` passes (53).
- [x] 4.2 `openspec validate --all` passes.
