# Pi writer adapter

A Sympozium harness adapter that owns every model turn of the article lane. `task: "draft"`
reads the pages the brief cites through the Firecrawl MCP server, writes `article.md`, writes the
`sources.json` ledger that names the page each fenced block came from, and hands both to the
caller. After the turn the server re-reads every ledgered URL through that same server and rewrites
the ledger with what it saw, so the model is never the authority on whether a source exists.

The other three turns are review, not drafting:

- `task: "review"` judges the draft against the publish gate and answers
  `<output>true|false</output>` plus an `<explanation>`.
- `task: "aspects"` runs the aspect registry (`prompts/article_aspects.json`) over the draft and
  answers one `<findings>` block per aspect.
- `task: "improve"` applies findings, human feedback or an objective problem and answers the
  edited article.

Review, aspect and improve turns run `--no-tools`: they may not research, and the server writes
the article they produce. They continue the same Pi session as the draft, so the model keeps the
article and the sources it already read.

Derived from the maintained Pi adapter's `session-server.mjs`, which is the reference for
the session contract. The deltas:

- `--no-tools` is dropped for a draft, so Pi can search and scrape and render a manifest.
- Every article prompt lives here, not in n8n: the drafting rules, the publish gate, the three
  aspect reviewers, the improver, the aspect registry and `prompts/writing.md` are baked into
  the image. The caller sends the entry's fields, never prompt text.
- Reading is the Firecrawl MCP server (`search`, `scrape`, `map`) and nothing else: the pod's
  egress policy admits the model and the MCP servers, so `curl` has no route to the internet and
  the loopback source proxy cannot reach a page either.
- The turn is a session (`v1alpha2`) only. An article needs the session directory and
  the serialized turn; a one-shot Job is refused by name rather than half-served.
- The catalog's read tools are offered. Pi reads a `mcp.json` naming Firecrawl's (`search`,
  `scrape`, `map`) and, when the deployment sets its address, the GitHub server's read tools
  (`search_code`, `search_repositories`, `get_file_contents`, `list_branches`, `list_commits`,
  `list_tags`); the GitHub server's write tools are always hidden. `--no-extensions` stays and
  `-e builtin:mcp` loads the one extension back. The addresses are `SYMPOZIUM_GITHUB_MCP_URL`
  and `SYMPOZIUM_FIRECRAWL_MCP_URL`: the image carries no cluster names, and an unset variable
  omits that server. The prompts name Firecrawl only, because it is the one read path this pod
  is guaranteed to have.

## What it costs

`node:22-bookworm-slim`, `curl`, `jq`, the pinned Pi package and a pinned `helm` (about
17 MB) — roughly a tenth of the render image, which carries a browser, an encoder and a
vendored engine. `helm` is here only because the instruction validates a quoted YAML
manifest offline: `helm template` renders a chart with no cluster, which is the only
proof available inside the pod.

## The request

`POST /v1/chat/completions`, OpenAI chat shape. The fields this adapter reads:

| field | meaning |
| --- | --- |
| `task` | `draft` (default), `review`, `aspects` or `improve` |
| `brief` | the entry's fields: `topic`, `description`, `url`, `max_words`, `asset_types`, `audience`, `extra_prompt`, `content`, `feedback`. The server renders the prompt from its own files |
| `article` | the draft of record for `review`, `aspects` and `improve`: `{ title, text }`. The caller resolves it, so the turn reviews exactly what the caller decided |
| `findings` | the merged aspect findings for `improve`, as one text block |
| `problem` | the objective failure a retry has to fix (`OVER_BUDGET`, `MARKERS`, a source problem) |
| `messages` | a plain-text fallback for a caller that is not the article lane; its last user message is sent to Pi unchanged |
| `session_id` | the row's session; one directory per id, so a retry continues in place |
| `source_hosts` | the allowlist for a draft (a string or array); the image default applies when absent |
| `attempt` | `> 1` means the drafting turn is a correction, even if the article was not written yet |
| `stream` | SSE chunks instead of one JSON body; a draft only, because a review's answer is structured |

The response carries `article: { name, ledger, title, text, word_count, sources, quoted, dropped, error }` — the counts and drop reasons are the server's, and `error` is
non-empty when the turn wrote no readable ledger. A `review` answer adds
`review: { pass, explanation }`; an `aspects` answer adds
`findings: [{ aspect, focus, error, text, count }]`.

`GET /artifacts/<session_id>/article.md|sources.json` serves the two files. No other name
is reachable.

## Fields Pi receives

`MODEL_NAME`, `MODEL_BASE_URL`, `OPENAI_API_KEY`, `SYMPOZIUM_HARNESS_CONTRACT_VERSION`
(`v1alpha2`), and the optional `PI_WRITER_*` knobs for the context window, token cap, idle
timeout and retry window. `SYMPOZIUM_WORKSPACE` moves the run directory; it defaults under
`/tmp`, because a session mounts the PVC there and not `/workspace`.

## Tests

```bash
node --test 'agents/adapters/pi-writer/test/*.test.mjs'
```

The ledger tests cover the fetch policy and the matching rule without a network. The
server test spawns the real server with a stub `pi` on `PATH`, so the artifact route, the
proxy refusals, the correction instruction and the four task answers are exercised end to end.
