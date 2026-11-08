# Proposal

## Why

The publish gate passed five invented heredocs three times, then passed a body whose only
supporting evidence was a page the reviewer had never seen. The cause is not the model: `review`
runs `--no-tools`, so it reads the draft and the seed page and nothing else. Every fact this lane
got wrong was found by a reader that could open the artifacts — that is what the operator did by
hand, twice.

## What Changes

- **`task: "audit"`**: a new turn on the same adapter, same pod, same session and run directory,
  with tools. It reads `article.md` and the derived `sources.json`, greps the session transcript
  for the phrases it doubts, may fetch a page (six lookups), and answers the review's
  `<output>` verdict plus `<explanation>` and a `<findings>` list. The findings are appended to the
  explanation, so the writer's retry carries them as feedback.
- **`Article Creator` calls it instead of the blind review.** One field in `build_review_request`
  changes (`task: 'audit'`); the verdict nodes, the merge and the switch stay, because the answer
  shape is the review's.
- **The writer can check itself before answering.** `check-article` ships in the image and applies
  the same derivation the server does, so a turn that fences a block no page carries sees
  `MISSING:` while it can still fix it instead of losing a round.
- **`PI_WRITER_THINKING`** moves the model's reasoning level, default `minimal`; the level map now
  covers low, medium and high so the variable is usable rather than a trap.

## Capabilities

- `content-writer`

## Impact

- `agents/adapters/pi-writer/`: `prompts/article_audit.md`, `bin/check-article.mjs`, `session-server.mjs`,
  `Dockerfile`, `README.md`, tests.
- `agents/n8n/workflows/article_creator.workflow.json` and the live workflow: `task: 'audit'`.
- No change to the code gates, the ledger derivation, the aspect pass or the improver.

## Non-goals

- No second deployment or persona: the audit is a task, not an agent.
- No change to what counts as a source, or to the word budget, markers or fence checks.
- The audit does not write the article: findings become the writer's next instruction.
