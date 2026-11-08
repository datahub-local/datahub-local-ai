# Tasks

## 1. The ledger is derived

- [x] 1.1 `session-lib.mjs`: `transcriptPages(rows)` maps each MCP scrape result to
      `{url, text}`, unwrapping `{markdown}` and keeping the truncated text the model saw.
- [x] 1.2 `session-lib.mjs`: `deriveLedger({article, pages})` returns one entry per fence found
      on a page, and the list of fences found nowhere.
- [x] 1.3 `session-server.mjs`: the draft turn writes the derived ledger and reports `unquoted`.

## 2. The writer's part shrinks

- [x] 2.1 `session-lib.mjs`: `articleTurnInstruction` names `article.md` only.
- [x] 2.2 `writing.md`: the ledger section becomes "the server records what you scraped".
- [x] 2.3 `article_task.md`: a fence must appear verbatim on a page scraped this session.

## 3. The re-read goes

- [x] 3.1 Delete `revalidateLedger`, `scrapeReader`, `mcpToolPayload`, `scrapeText`,
      `fetchLedgerUrl`, `sourceUrlRefusal` and their tests. `hostAllowed`, `isBlockedHostname`
      and `isLoopbackHostname` stay: the source proxy still decides a CONNECT target with them.
- [x] 3.2 `session-server.mjs` drops the Firecrawl verification path and its boot log.

## 4. Gates

- [x] 4.1 `node --test 'agents/adapters/pi-writer/test/*.test.mjs'` passes (51).
- [x] 4.2 The proxy's refused-CONNECT branch no longer writes to a socket whose client has gone,
      which took the server down once the turn got fast enough to race it.
- [x] 4.3 `openspec validate --all` passes.
