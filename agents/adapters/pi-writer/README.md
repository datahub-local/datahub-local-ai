# Pi writer adapter

A Sympozium harness adapter that drafts an article from sources the session actually
read. One turn fetches the pages the brief cites through an allowlisted proxy, writes
`article.md`, writes the `sources.json` ledger that names the page each fenced block came
from, and hands both to the caller. After the turn the server refetches every ledgered
URL and rewrites the ledger with what it saw, so the model is never the authority on
whether a source exists.

Derived from the maintained Pi adapter's `session-server.mjs`, which is the reference for
the session contract. The deltas:

- `--no-tools` is dropped, so Pi can fetch a page and render a manifest.
- The instruction is `prompts/writing.md`, read at run time.
- Outbound reading goes through a loopback forward proxy. Anything off the caller's
  `source_hosts` answers `403` and is logged with the host.
- The turn is a session (`v1alpha2`) only. An article needs the session directory and
  the serialized turn; a one-shot Job is refused by name rather than half-served.

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
| `messages` | the last user message is the brief; its content is sent to Pi unchanged |
| `session_id` | the row's session; one directory per id, so a retry continues in place |
| `source_hosts` | the allowlist for this turn (a string or array); the image default applies when absent |
| `attempt` | `> 1` means the turn is a correction, even if the article was not written yet |
| `stream` | SSE chunks instead of one JSON body |

The response carries `article: { name, ledger, sources, quoted, dropped, error }` — the
counts and drop reasons are the server's, and `error` is non-empty when the turn wrote no
readable ledger.

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
proxy refusals and the correction instruction are exercised end to end.
