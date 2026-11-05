# Article writer tools

The model-facing descriptions of the two tools the writer can call. The tool names belong to
the workflow; the text below is what the model reads.

## research_sources

Search Hacker News and the author's RSS feeds for a subject. Returns a digest of titles, URLs, points and comment counts. Use it first; read a result with read_page before relying on it.

## read_page

Fetch one URL and return its readable text. Use it on a link the other tools returned, or on a documentation URL.
