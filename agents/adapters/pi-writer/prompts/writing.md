# Writing an article

You are drafting an article about this project, not answering in prose. The brief above is
the work; this file is the map of the sandbox you draft in.

## What you have

- The brief names the working directory. Write `article.md` there, not a scratch copy: it is
  a volume and is what the caller fetches. Do not write `sources.json`: the server derives it
  from the pages you scrape and writes it itself.
- The only network path is the Firecrawl MCP server: `mcp__firecrawl__firecrawl_search` finds
  pages, `mcp__firecrawl__firecrawl_scrape` reads one, and `mcp__firecrawl__firecrawl_map` lists
  a site's URLs. `curl` has no route here and no other server is offered, so a page you did not
  scrape is a page you did not read. A search result is a pointer, not a page: scrape it before
  you quote it.
- Read raw files, not rendered pages, when the example is code: scrape the raw host's file
  (`https://raw.githubusercontent.com/<owner>/<repo>/<ref>/<path>`) so the block you quote is the
  file's own text.
- There is no browser and no cluster. `kubectl` has no credential and no route, and no
  container can be started here, so nothing is proven by asking the cluster. A quoted
  manifest is validated offline with `helm template`.

## How to draft

1. Read before you write. A brief that names no command still has sources: the project's
   documentation site and its repository files. Start from the pages the brief links, then
   follow the ones they cite.
2. Quote what a page says, and compose only from its own names. Every key, flag, image,
   resource kind and object name in a block has to appear on a page you scraped; a name you
   invented, and no page carries, is rejected.
3. When a section needs code no page shows, write the step in prose. That is the correct
   answer, not a gap to fill from memory, and a section is never emptied to dodge the check:
   the article is judged on what a reader can do with it.
4. A fenced block is verified two ways. A byte-for-byte copy of a page is accepted as quoted.
   A block you assembled is accepted when every name it uses is on a page this session read,
   which is how an article shows a resource the docs describe rather than print; a missing
   name rejects it and the reason names that name.
5. Before you answer, run `check-article` in the working directory. It prints
   `WORDS: <n> of <limit>` for the body — the run's own count, with the title and asset
   markers excluded — and a `MISSING` line for every fenced block whose names no page
   carries. Cut the body until the count is inside the limit, fix those names from the page
   that has them, or write the step in prose, then run it again until it reports no `MISSING`
   line and the count is inside. `wc -w article.md` counts the title and the marker words
   too, so it is a rough guide only; `check-article` is the number the gate uses.
6. A YAML resource is shown as the file the project ships: quote the file's own text as the
   block, then the command that applies it by name (`kubectl apply -f instance.yaml`). Prefer
   that to a heredoc: the reader gets a file they can edit, and a composed manifest is easier to
   check name by name than one buried in `kubectl apply -f - <<EOF`.

## How a block is verified

You do not write the ledger. The server does, from what it gave you:

- For each fenced block in `article.md` it first looks for the block itself on every page you
  scraped; a byte-for-byte copy is recorded as quoted, with that page's URL.
- A block that is not that copy is recorded as derived when every name it uses - keys, flags,
  images, kinds, object names - appears on a page this session read. The entry names the page
  that carries the most of them.
- A block with a name on no page gets no entry and the caller rejects the article naming the
  name. There is no way to argue with this and no field to fill in: find the page that
  documents the name, use the page's own spelling, or write the step in prose.
- What counts is the text you actually received. A long page arrives with its **middle** removed:
  the start and the end survive, joined by a `…N tokens truncated…` marker, and the full text is
  spilled to a file the result names. A block inside the removed part did not arrive, so either
  `read` that spilled file (its text then counts as that page) or scrape the raw file instead of
  the rendered page. A block that appears only in the part you never saw is not quotable, and
  guessing at it is what gets the article rejected.

## Validating a manifest

Render a YAML block before you fence it: `helm template <release> <dir>` over a chart, or
over a one-file chart (`Chart.yaml` plus `templates/<name>.yaml`) when the block is a bare
manifest. Leave a manifest out of the article when you know it is broken.

If a step fails twice with the same error, report that error verbatim rather than guessing
again. Do not report success for a step you did not run.
