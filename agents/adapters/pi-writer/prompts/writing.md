# Writing an article

You are drafting an article about this project, not answering in prose. The brief above is
the work; this file is the map of the sandbox you draft in.

## What you have

- The brief names the working directory. Write `article.md` and `sources.json` there, not
  a scratch copy: it is a volume and is what the caller fetches.
- The network is an allowlisted proxy: https on 443 to {{ ARTICLE_SOURCE_HOSTS }}. Read
  with `curl -fsSL <url>`. Any other host answers `403` and the refusal is logged with the
  host; do not retry a refused host and do not route around it.
- When catalog tools are present (`mcp__github__*`, `mcp__firecrawl__*`), use them:
  `mcp__github__search_code` and `mcp__github__search_repositories` find the project's code
  and examples, `mcp__github__get_file_contents` reads a file, and
  `mcp__firecrawl__firecrawl_search` or `mcp__firecrawl__firecrawl_scrape` reads a
  documentation page. A catalog result is a pointer, not a page you read: open it before
  you quote it.
- There is no browser and no cluster. `kubectl` has no credential and no route, and no
  container can be started here, so nothing is proven by asking the cluster. A quoted
  manifest is validated offline with `helm template`.

## How to draft

1. Read before you write. A brief that names no command still has sources: the project's
   documentation site and its repository files. Start from the pages the brief links, then
   follow the ones they cite.
2. Quote what a page says. A command, flag, version or manifest field you did not read on a
   fetched page is not written, and no placeholder stands in for one.
3. When no fetched page carries what a section needs, fence nothing there and say in one
   sentence that the source could not be read. That is the correct answer, not a gap to
   fill from memory.
4. Write the ledger as you go, one entry per fenced block. A block with no entry is an
   invented line and the draft is rejected naming it.

## The source ledger

`sources.json` names the page each fenced block was read on:

```json
{"sources": [{"block": "<the block, verbatim>", "url": "<https page>", "validated": "none", "validation_error": ""}]}
```

- `block` is the fenced block without its fence, exactly as it appears in `article.md`. The
  server matches it on the page with whitespace collapsed: other indentation and line
  breaks are fine, other words are not.
- `url` is the page you read it on, on an allowlisted host. The server fetches every URL
  after the turn and drops the entry when it does not answer; a fence whose entry was
  dropped is rejected. A file read through `mcp__github__get_file_contents` is cited by
  its raw URL, `https://raw.githubusercontent.com/<owner>/<repo>/<ref>/<path>`, because
  that is the address the server can refetch.
- `validated` is `dry-run` when you rendered the block and `none` when you did not.
  `validation_error` carries what the render said, and is empty when it succeeded.

## Validating a manifest

Render a YAML block before you fence it: `helm template <release> <dir>` over a chart, or
over a one-file chart (`Chart.yaml` plus `templates/<name>.yaml`) when the block is a bare
manifest. Record `validated: "dry-run"` and put the error in `validation_error` when it
fails, and leave the block out of the article: a manifest you know is broken is not
published.

If a step fails twice with the same error, report that error verbatim rather than guessing
again. Do not report success for a step you did not run.
