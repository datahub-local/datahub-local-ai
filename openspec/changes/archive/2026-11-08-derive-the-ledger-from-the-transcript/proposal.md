# Proposal

## Why

Row 3 failed three attempts in a row on the same five blocks, and the model had fixed them
in its answer: the ledger is a second representation of the prose that the model has to keep
byte-exact, and it cannot. Measured on the live pod 2026-11-08: `article.md` carried 8 fenced
blocks and `sources.json` 3 entries on every attempt, with the same three `kubectl apply -f -
<<EOF` heredocs and the same `sreb-watchdog` patch reported as `UNQUOTED` each time. The
gate is right; the writer's job description is wrong.

The session server already holds the evidence the ledger is supposed to describe: Pi's
transcript records every MCP `firecrawl_scrape` call with its URL and the exact text the model
received. A fence either appears in that text or it does not.

## What Changes

- **The server derives `sources.json` from the transcript.** For every fenced block in
  `article.md`, the server searches the scrape results the turn received (whitespace-collapsed,
  as the gate matches it) and writes one ledger entry per block that appears on a page, with
  that page's URL. A block on no page gets no entry, which the gate already reports as
  `UNQUOTED`.
- **The writer no longer writes `sources.json`.** `articleTurnInstruction`, `writing.md` and
  `article_task.md` say the server records the pages it scraped and that a fence must appear
  verbatim on one of them. The rule the model follows is the same one the gate enforces, so
  there is no second copy to drift.
- **The outbound re-read goes.** `revalidateLedger`, `scrapeReader` and the URL-policy family
  are removed: the scrape the pod brokered is already the proof that the page exists and
  carries the text, and re-fetching it was a second dependency (`firecrawl_scrape` in the
  verification path) plus a second way to drop a correct entry.

## Capabilities

- `content-writer`

## Impact

- `agents/adapters/pi-writer/session-lib.mjs`: `transcriptPages`, `deriveLedger`; the fetch
  family deleted.
- `agents/adapters/pi-writer/session-server.mjs`: the draft turn writes the derived ledger.
- `agents/adapters/pi-writer/prompts/{writing,article_task}.md`: the writer's part shrinks.
- The n8n gate is unchanged: it still compares fences to `sources.json`, and `UNQUOTED`,
  `SOURCE_NOT_FOUND` and `VALIDATION_FAILED` keep their meanings.

## Non-goals

- No change to the review, the aspect passes or the improver.
- No change to what counts as a source: still only a page this session scraped.
- Bash `curl` reads and the GitHub tool are not derived from; the sandbox map names Firecrawl
  as the only read path.
