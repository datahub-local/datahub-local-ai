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
2. Quote what a page says. A command, flag, version or manifest field you did not read on a
   scraped page is not written, and no placeholder stands in for one.
3. When no scraped page carries what a section needs, fence nothing there and write the step
   in prose. That is the correct answer, not a gap to fill from memory.
4. A fenced block is verified against the page you scraped it from: the server searches the
   text it handed you for that page, and records the block only if it appears there, word for
   word apart from whitespace. A block you assembled from several pages, or renamed inside,
   will not appear and the article is rejected naming it.
5. A YAML resource is shown as the file the project ships: quote the file's own text from its raw
   URL as the block, then the command that applies it by name (`kubectl apply -f instance.yaml`),
   which the page also carries. Never wrap it in `kubectl apply -f - <<EOF` unless the page shows
   that exact heredoc: the wrapper is text you added, so it is text no page carries, and the
   article is rejected naming it. A one-file-per-resource walk-through is easier to paste than a
   heredoc anyway: the reader gets a file they can edit.

## How a block is verified

You do not write the ledger. The server does, from what it gave you:

- For each fenced block in `article.md` it searches every page you scraped this session and, on
  a match, records one entry naming that page's URL.
- A block that matches no page gets no entry, and the caller rejects the article naming the
  block. There is no way to argue with this and no field to fill in: the fix is to quote the
  page or drop the fence.
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
