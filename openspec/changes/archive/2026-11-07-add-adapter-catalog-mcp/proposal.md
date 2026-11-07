# Proposal

## Why

Both Pi adapters run with `--no-extensions`, which disables Pi's built-in MCP client along with
skill and extension discovery. A drafting or authoring turn therefore has one way to read the
project it writes about: `curl` through the writer's source proxy, or the engine's own docs. The
article drafts that prompted `add-agent-authored-articles` failed on exactly this — the model could
not find a command, a manifest or an example, so it wrote the shape of one and left placeholders.

`datahub-local-core` already runs an MCP catalog in `automation`, including a GitHub server (45
tools, token minted per request by the proxy sidecar) and Firecrawl. It is wired into Hermes and
OpenCode and into no adapter. Pi 1.4 reads `~/.pi/agent/mcp.json`, so the missing piece is a config
file and one flag.

## What Changes

- **Both sessions write `mcp.json` at startup from deployment env.** `session-lib.mjs` gains
  `mcpConfig()`: the URLs come from `PI_WRITER_*_MCP_URL` / `PI_RENDER_*_MCP_URL`, never an image
  default, read-only tools declared `direct`, every other tool `hidden`. The GitHub server's write
  tools (`create_or_update_file`, `push_files`, `create_pull_request`, `issue_write`, …) are never
  reachable from these lanes.
- **Core injects the env.** No CRD field sets it on a session pod, so `datahub-local-core` adds a
  MutatingAdmissionPolicy that sets the two variables on the `harness-session` Deployment. Cross-repo;
  until it lands the catalog is absent and the turn falls back to `curl` / `hyperframes docs`.
- **`-e builtin:mcp` pairs with `--no-extensions`.** The flag list still refuses discovered
  extensions; only the built-in MCP client is loaded back.
- **Each chart gains an `mcp-egress` NetworkPolicy** (port 8080 to pods labelled
  `app.kubernetes.io/name: mcpserver`), so the session's reach is stated rather than inferred from
  the controller's wide default.
- **The prompts name the tools they may use.** `pi-writer/prompts/writing.md` says a catalog result
  is a pointer to a page that must still be opened, and that a file read through
  `get_file_contents` is ledgered by its `raw.githubusercontent.com` URL, which is what the server
  can refetch. `pi-render/prompts/authoring.md` says the engine's docs stay the contract and a
  worked example is only a pattern; both bound the lookups (three for a draft, five for a render).

## Capabilities

### Modified Capabilities

- `content-writer`: a drafting turn may read the catalog's GitHub and Firecrawl read tools, and the
  ledger still names a URL the server can refetch.
- `agent-authored-compositions`: an authoring turn may read the catalog's read tools for worked
  examples, while the render itself stays offline.

## Impact

- `agents/adapters/pi-writer/`, `agents/adapters/pi-render/`: `session-lib.mjs`, `session-server.mjs`,
  the prompt files, READMEs and tests.
- `agents/sympozium/templates/pi-writer-session.yaml`, `pi-render-session.yaml`: one additive
  NetworkPolicy each.
- `agents/sympozium/MEMORY.md`: why the URLs are image defaults and why the egress rule is explicit.
- No workflow change: n8n still sends fields, never prompt text.

## Non-goals

- No MCP server for the writer to call the cluster with; both servers are read-only web surfaces.
- No new image dependency: Pi 1.4.0 is the version already pinned in both Dockerfiles.
- No change to the article gate: a fence whose ledger entry is dropped is still rejected.
