# Design

## Gate findings

- `review` receives the draft and the seed page and runs `--no-tools`; a claim about a scraped page
  is invisible to it. The two failures that reached a human (five invented heredocs, a schedule
  name no page carries) were both of that kind.
- The adapter already has the evidence on disk by the time any review turn runs: `article.md`,
  the derived `sources.json`, and the transcript with every scraped page's text.
- The caller's switch reads `$json.output === 'true'`, so a new answer shape would mean graph
  surgery. Returning the review's verdict plus findings keeps the graph.

## D1 — A task, not an agent or a skill

An agent means a new `Agent`/`AgentRuntime` and pod; a skill is instructions and cannot grant
tools. The audit needs the same session (the fetched corpus lives there), the same run directory
and tools, which is exactly what a fifth task on this endpoint gives for one prompt file and one
branch.

## D2 — The verdict stays the review's, the findings ride in the explanation

`merge_article_verdict` combines the reviewer's boolean with the parser's `PROBLEM`, and that
combination is right: code owns counts. The audit therefore answers `<output>` as before, and its
`<findings>` are appended to `<explanation>`, which is the field the retry already sends back as
feedback. One graph node changes.

## D3 — The auditor must not outsource the code checks

The audit prompt forbids reporting budget, markers, fence counts, numbering or the Source line:
those are counted in code, and a model told to count will invent a count. Its job is the two
things code cannot do: is a claim supported by a page, and did the body deliver what the entry
asked.

## D4 — The writer checks itself

`check-article` reuses `transcriptPages` and `deriveLedger` from `session-lib`, shipped in the
image with the session id and directory in the environment. The same rule the server applies after
the turn, available before it answers. Rejected: telling the prompt to grep the spill files by
hand, which is the bookkeeping the derived ledger exists to remove.

## Risks

- **Cost.** The audit is a tool-enabled turn: up to six lookups and a full session read. It runs
  once per draft instead of the blind review, so the round gains a fetch but not a turn.
- **It can be wrong in the other direction** and reject a sound draft. Its findings are prose, not
  a gate: the writer may fix or contest them, and the code gates still decide what publishes.
- [UNVERIFIED] live: the audit's judgement quality on this model at `minimal` thinking.

## Definition of done

- `task: "audit"` runs with tools and answers verdict plus findings; the findings reach the retry.
- `check-article` is in the image and the guide tells the turn to run it.
- `Article Creator` requests the audit, live and in the export; the switch is unchanged.
- `node --test 'agents/adapters/pi-writer/test/*.test.mjs'` and `openspec validate --all` pass.
