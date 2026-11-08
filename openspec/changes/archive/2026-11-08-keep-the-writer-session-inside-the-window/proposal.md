# Proposal

## Why

Row `article-3` answers one character and every gate above it believes the turn succeeded.

Measured on the live pod 2026-11-08: the draft turn finished at 07:33 (5,457 input after Pi
compacted twice while it ran), then the next turn resumed the same session and sent **258,433
tokens** into a **262,144** window. The gateway truncated, the model returned `<` with
`stopReason: length`, and the retry re-sent 289,534. The session had been growing since
2026-11-06 because Pi, on resume, only compacts above `contextWindow - reserveTokens`, and the
vendor reserve is 16,384: 245,760 tokens. A session at 258k is therefore never compacted.

## What Changes

- The writer writes Pi's `settings.json` with `compaction` set explicitly: enabled, a trigger of
  150,000 tokens and 20,000 kept recent. The reserve is derived from the context window, so a
  deployment that changes the window keeps the same trigger.
- `PI_WRITER_COMPACT_AT_TOKENS` and `PI_WRITER_COMPACT_KEEP_TOKENS` override them, and the boot
  log prints the trigger with the window it must fit inside.
- `agentSettings` refuses a trigger outside the window.

## Capabilities

- `content-writer`

## Impact

- `agents/adapters/pi-writer/session-lib.mjs`, `session-server.mjs`, `test/ledger.test.mjs`.
- No workflow, request or API change: n8n is not involved, and the session id is unchanged.
- One live action outside the image: the over-window transcript was renamed to `.jsonl.over-window`
  so the row's next turn starts from an empty session. Pi ignores a file that does not end in
  `.jsonl`.

## Non-goals

- Rotating session ids per turn, or asking the caller to carry the ledger: both were considered and
  rejected in favour of using Pi's own compaction, which keeps one session per row.
- Changing `maxTokens` or the context window.
