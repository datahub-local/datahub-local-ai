# Design

## Context

The drafting turn is one Pi session with the catalog's read tools and an allowlisted HTTPS proxy.
Every fenced block must be ledgered against a page the server can refetch, and `findExcerpt`
matches a block's words on the page with whitespace collapsed. Review, aspects and improve run
`--no-tools` in the same session, so they see the pages but cannot fetch more.

That ledger rule is what makes "share more code" safe: the cheapest way to satisfy it is to quote
an example the project ships, which is also the example a reader can run.

## Gate findings

- A three-lookup budget was spent on the seed link and two follow-ups; the example directory and
  the changelog were never reached in practice. Raising the bound is the only change needed —
  the limit is prompt text, not code.
- Code blocks are already legal and already gated. What was missing was a prompt that wants one,
  so drafts passed with none.
- **Adapting an example breaks its ledger entry.** Renaming an object inside a block makes the
  block absent from the page and the server drops the entry. The rules therefore say: introduce
  the name in the prose above, never edit the block. This is the constraint that shaped the
  wording of the code rule, and it replaces an earlier structures line that said to adapt the
  example.
- The review gate has no page access of its own, but it shares the draft session: it can judge a
  title, a close and a boundary without fetching. It cannot verify a block's text — the ledger
  code gate does that — so no block-fidelity check was added to the review.

## D1 — Twenty lookups, split four searches to sixteen scrapes

Searches return pointers and scrapes return text, so one flat count spends the budget on the cheap
half. Four searches cover the five hunt steps (docs, example, changelog, error text, issues);
sixteen scrapes leave a second source for each claim the article rests on and a retry's four.

The ceiling that matters is the context window, not the turn timeout: 262144 tokens with 20
scraped pages of roughly 3–8k tokens each lands near 100k before the draft is written, and the
review and improve turns continue in the same session. Sixteen scrapes is the most that leaves
room for those turns; a page the model does not need is a page it should not scrape.

Rejected: unbounded — a model with no spending rule keeps searching and the turn dies on the
caller's 900 s.

The hunt order is written as an ordered list rather than a checklist to satisfy, so a run that
finds the example in scrape 2 skips the one that would repeat it instead of filling the budget.

## D2 — A code rule placed in three files, each for its own reason

- `article_task.md` owns the requirement (at least one block; which shapes) and the ledger
  constraint, because that is what the drafting turn reads last before it writes.
- `article_writer_system.md` owns the voice rule (quoted, never paraphrased; the prose explains
  the block's job, not each line), because it applies to every paragraph that surrounds code.
- `article_structures.md` owns the shape rule, because "getting started" and "introduction"
  need a block and "state of a thing" may not.

Rejected: one long section in the task prompt. The system prompt is what survives a task prompt
that the caller overrides with an extra prompt.

## D3 — The title rule is a check, not a preference

A title that fits another project is objectively wrong for this article, and the reviewer already
receives `Title:`. Twelve words is a bound the reviewer can count. Rejected: a style list of good
titles — it is a second copy of a rule the model reads once.

## D4 — Boundary and provenance are rules; the comparison table is a shape beat

The boundary is one sentence in the system prompt (it is a way of reasoning) plus one beat in
`One spine` (it has to appear before the close). Numbers with provenance sit in the system prompt
because they are a writing rule, not a structure. The table is only added to `A comparison`,
where the decisive dimension is actually a table.

## D5 — The ledger re-read goes through Firecrawl, not a direct fetch

The design says the server, not the model, decides whether a source exists. With egress limited to
the MCP servers, a direct fetch answers nothing for every entry, so that promise turned into "every
fenced block is rejected". `scrapeReader` calls `firecrawl_scrape` over MCP and returns the scraped
markdown; `revalidateLedger` takes it as `reader` and runs the identical URL policy on the citation
first, so the allowlist still decides what may be cited.

Rejected: trusting the model's scrape in the ledger (the model becomes the authority, which is the
one thing the ledger exists to prevent) and opening egress to the three hosts (a wider rule than
the design needs, and it would make the pod's network policy depend on a list a workflow owns).

The loopback source proxy and `proxyEnv` stay: they are the ledger's fallback path when no Firecrawl
endpoint is configured, and a session with no MCP injection then logs which path it uses at boot.

## Risks

- **The review gets stricter.** Three new failures (title, close, boundary) can reject a draft that
  would have passed. Each is objective and each was already a stated intent, but the first runs
  after the image ships should be watched for a rejection rate spike.
- **More lookups cost time.** Ten proxy fetches can add minutes to a draft; the retry allowance
  adds four more. The 900 s turn timeout and the 240 s idle timeout are unchanged, so a slow source
  can still exhaust the turn — the existing "write from the inputs alone" fallback covers it.
- **A code requirement can push a draft over the word budget.** A block counts toward the body
  count in the gate. The task prompt already says the budget is binding, and the review names how
  many words to cut.

## Open questions

- Whether twenty lookups is the right number is [UNVERIFIED] until a batch of drafts runs on it.
  It is one line in `article_task.md` if it needs lowering.
- The scrape reader's markdown is not byte-identical to the page's HTML text: `findExcerpt`
  collapses whitespace and the Firecrawl rendition keeps code fences, but a page whose example is
  rendered by JavaScript may come back without it. [UNVERIFIED] until a draft quotes one.

## Definition of done

- The five prompt files carry the rules above, with no second copy in `agents/n8n/`.
- `node --test 'agents/adapters/pi-writer/test/*.test.mjs'` passes.
- `openspec validate --all` passes.
