# Tasks

## 1. The gate reaches the auditor

- [x] 1.1 `deriveLedger` returns `unquotedBlocks` alongside the first-line list.
- [x] 1.2 `writeDerivedLedger` returns the blocks and the page URLs the session read.
- [x] 1.3 `auditPrompt` renders `{{ UNQUOTED }}` and `{{ PAGES }}`; `article_audit.md` turns each
      block into a fix (quote the page verbatim, prose, or cut).
- [x] 1.4 The audit's `pass` is false whenever a block is unquoted, whatever the model answered.

## 2. The auditor can read

- [x] 2.1 `transcriptFile(sessionID)` and `PI_WRITER_SESSION_FILE`; the prompt uses the real path.
- [x] 2.2 The source proxy is enabled for the audit turn with the caller's hosts.

## 3. The edit can quote

- [x] 3.1 `improve` runs with tools and the proxy, four lookups.
- [x] 3.2 `article_improver.md`: quote by fetching or from a finding, `check-article` before answer.

## 4. Gates

- [x] 4.1 Tests: the audit overrules a passing model, the prompt carries the block and pages, the
      edit runs without `--no-tools`.
- [x] 4.2 `node --test 'agents/adapters/pi-writer/test/*.test.mjs'` passes (54).
- [x] 4.3 `openspec validate --all` passes.
