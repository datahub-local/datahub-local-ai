# Proposal

## Why

The article lane produces correct drafts that are thin to read. Three causes sit in the prompts,
not in the model:

- The drafting turn may make three lookups and is told to stop early, so the pages that carry
  the runnable example, the version and the error text are usually never fetched. A draft with
  no fetched example has nothing concrete to show.
- Nothing asks the body to show work. `writing.md` allows fenced blocks and the ledger enforces
  them, but no prompt wants one: a draft can pass every gate without a single command, manifest
  or file. Articles about tools that ship no code are the weakest output of the lane.
- The title, the numbers and the recommendation have no rule: the title can be any noun phrase,
  a figure can be borrowed to sound large, and a recommendation carries no boundary. Those are
  the three things a reader uses to decide to read, trust and try a post.

## What Changes

- **Research budget 3 → 20 lookups on Firecrawl alone.** The prompt named `curl` and a GitHub
  server this pod does not have: egress admits the model and the MCP servers, nothing else. It now
  names `firecrawl_search`, `firecrawl_scrape` and `firecrawl_map`, and splits the budget into at
  most four searches and sixteen scrapes.
- **Research is planned.** `article_task.md` names what to spend the lookups on, in order: the
  project's README/docs, an example it ships, the changelog or upgrade guide for the version that
  changed the behaviour, a page carrying the error the reader will hit, and the issues or design
  document that states what breaks in practice. It stops when the pages held carry the article's
  claims, not when the budget is spent.
- **A retry may fetch up to four pages.** The drafting turn today may not research on a retry even
  when the human feedback names a claim it cannot answer. Four lookups, only for a named claim.
- **The body shows a runnable block.** New `## What the body shows` section: at least one fenced
  block quoted from a fetched page for any shape that teaches a tool; whole and verbatim, because
  the ledger matches the block's words against the page, with names introduced in the prose above.
  A quoted failure (error text, rejected apply, version mismatch) with cause and fix. A pinned
  version in the section that first depends on one.
- **The title is a rule.** At most twelve words, subject plus the specific thing the article
  settles, no "A Guide to X" and no colon-slogan. Added to the system prompt, the improver (when
  a finding names the title) and the review gate.
- **Numbers carry provenance.** A figure states what was measured, on what, and where it comes
  from; no rounded figure to sound large, no range from one data point.
- **A recommendation names its boundary.** Every shape gains one line on when this is the wrong
  choice and what to use instead; the comparison shape gains one table on the deciding dimension.
- **The close names its next hop.** A page with the URL the writer fetched, or the command to run
  now; "see the documentation" fails the review.
- **The improver keeps code verbatim** and may add a code example, not only a command, when a
  finding or the feedback asks for one (reported as unverified, as that exception already is).

## Capabilities

- `content-writer`

## Impact

- `agents/adapters/pi-writer/prompts/{article_task,article_writer_system,article_structures,article_improver,article_review}.md`
- No workflow, schema or API change: the prompts are baked into the adapter image and the
  request shape is untouched. The lane's existing code gates (word budget, asset markers, ledger
  fidelity) are unchanged and still reject what they rejected before.

## Non-goals

- No change to the ledger rule, the allowlist, the source hosts or the MCP catalog: more lookups
  within the same bound, not a new fetch path.
- No new asset type, no aspect registry entry, no change to the audience levels.
- No second copy of a prompt in `agents/n8n/`.
