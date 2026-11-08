# Tasks

## 1. Research is proactive and planned

- [x] 1.1 `article_task.md`: budget 3 → 20 lookups on Firecrawl (≤4 searches, ≤16 scrapes);
      `curl` and the GitHub server removed from the prompts, because neither is reachable.
- [x] 1.2 `article_task.md`: ordered hunt plan (docs, shipped example, changelog/upgrade guide,
      the page carrying the error the reader meets, the issue or design note that states what
      breaks in practice), skipping a lookup whose answer is already held.
- [x] 1.3 `article_task.md`: a retry may fetch at most four pages, only for a claim the feedback names.

## 2. The body shows its work

- [x] 2.1 `article_task.md`: `## What the body shows` — at least one ledgered fenced block for a
      shape that teaches a tool; verbatim, names introduced in the prose above.
- [x] 2.2 `article_task.md`: a quoted failure with cause and fix; a pinned version where it is
      first needed.
- [x] 2.3 `article_writer_system.md`: code quoted, never paraphrased; prose says the block's job.
- [x] 2.4 `article_structures.md`: the block beat in `One spine`; the comparison table.
- [x] 2.5 `article_improver.md`: keep untouched blocks verbatim; a code example is covered by the
      unverified exception.

## 3. Title, numbers, boundary, close

- [x] 3.1 `article_writer_system.md`: title rule, numbers with provenance, boundary rule.
- [x] 3.2 `article_structures.md`: the boundary beat before the close.
- [x] 3.3 `article_task.md`: the close names a fetched URL or the command to run now.
- [x] 3.4 `article_improver.md`: the title rule applies when a finding names the title.
- [x] 3.5 `article_review.md`: checks for title, close specificity and the boundary.

## 4. The ledger re-read leaves the pod

- [x] 4.1 `session-lib.mjs`: `mcpToolPayload` and `scrapeText` read a JSON body or an SSE frame and
      unwrap Firecrawl's `{markdown}` wrapper.
- [x] 4.2 `session-lib.mjs`: `scrapeReader` calls `firecrawl_scrape` over MCP and answers
      `{status, body}` or a refusal naming the failure.
- [x] 4.3 `revalidateLedger` takes `reader`, and the source-host policy still runs on the citation
      before anything is read.
- [x] 4.4 `session-server.mjs`: verification uses the reader when `SYMPOZIUM_FIRECRAWL_MCP_URL` is
      set, and logs which path it uses at boot.
- [x] 4.5 `README.md`, `writing.md`: reading and re-reading are both Firecrawl; `curl` is gone from
      what the model is told.
- [x] 4.6 Tests: SSE and JSON payloads, an error payload, a dead endpoint, a reader verifying a
      block, and a reader not bypassing the allowlist.

## 5. Gates

- [x] 5.1 `node --test 'agents/adapters/pi-writer/test/*.test.mjs'` passes.
- [x] 5.2 `openspec validate --all` passes.
- [x] 5.3 The lookup budget is [UNVERIFIED] against a live batch; it stays an open question in
      `design.md` (`one line in article_task.md` to lower) rather than a task an archive would lose.
