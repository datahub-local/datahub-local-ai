# Proposal

## Why

A run added an Ensemble example and an MCPServer example as fenced blocks that no page carried.
The audit answered `<output>true</output>` and said the MCPServer block "matches the page's HTTP
transport example word for word" — a block the session had never read. It could not check: the
prompt named `PI_WRITER_SESSION_FILE`, which the server never set, and tools without the source
proxy have no route. So the auditor guessed, the gate rejected, and the writer received
`UNQUOTED: "apiVersion: sympozium.ai/v1alpha1"` — a first line that names neither of the two
blocks and no page that carries either. The loop could not converge.

## What Changes

- **The audit starts from the gate.** The ledger is derived before the audit runs, and the audit's
  prompt carries every unquoted block with its own text and the URLs this session read. Its
  findings must give one of three fixes per block: quote the page (pasted in the finding), turn it
  into prose, or cut it.
- **The audit cannot pass a draft the gate rejects.** Code decides the verdict's floor: any
  unquoted block makes `pass` false whatever the model concluded.
- **The audit can read.** `PI_WRITER_SESSION_FILE` is set to the session's transcript, and the
  source proxy is enabled for the audit turn, so its six lookups are possible.
- **The edit turn can quote.** `task: "improve"` runs with tools and the same allowlist, at most
  four lookups, and runs `check-article` before answering. It may paste a block verbatim from a
  page it fetched or from a finding that already quotes one. The old absolute ban on fences is why
  a requested example was deleted rather than sourced.

## Capabilities

- `content-writer`

## Impact

- `agents/adapters/pi-writer/session-server.mjs`, `session-lib.mjs`, `prompts/article_audit.md`,
  `prompts/article_improver.md`, `README.md`, tests.
- No change to the caller, the graph, the ledger rules or the code gate.

## Non-goals

- The audit still does not write the article.
- The improver's extra research is for quoting, not for new claims: same ledger, same gate.
