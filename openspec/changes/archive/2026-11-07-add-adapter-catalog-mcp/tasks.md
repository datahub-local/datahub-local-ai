# Tasks

## 1. The config Pi reads

- [x] `agents/adapters/pi-writer/session-lib.mjs`, `agents/adapters/pi-render/session-lib.mjs`:
  `DEFAULT_MCP_URLS`, the GitHub/Firecrawl read-tool lists and `mcpConfig()` — server `hidden`,
  named tools `direct`, an empty URL omits the server.
- [x] `session-server.mjs` (both): write `<agent-dir>/mcp.json` at startup from `mcpConfig()`, fed by
  `PI_*_GITHUB_MCP_URL` / `PI_*_FIRECRAWL_MCP_URL`; no default URL in the image, and an unset
  variable omits that server.
- [x] `session-server.mjs` (both): add `-e builtin:mcp` beside `--no-extensions`.

## 2. The prompts

- [x] `pi-writer/prompts/writing.md`: name the catalog tools, say a result is a pointer, and give the
  raw URL as the ledger address for a file read.
- [x] `pi-writer/prompts/article_task.md`: the lookup budget counts catalog calls and `curl` alike.
- [x] `pi-render/prompts/authoring.md`: name the catalog tools, keep the engine's docs as the
  contract, bound the lookups, and state that the render itself stays offline.

## 3. The deployment env (cross-repo)

- [x] `datahub-local-core/releases/automation/templates/sympozium_upstream_fixes.yaml` fix (8): a
  MutatingAdmissionPolicy on pod admission adds `SYMPOZIUM_GITHUB_MCP_URL` and
  `SYMPOZIUM_FIRECRAWL_MCP_URL` to every `harness-session` pod. It patches the container env whether
  or not the array exists, so fail-closed admission cannot reject a session with no env.
- [x] Verified on the cluster: a server dry-run of a labelled pod carries both variables, and the
  replaced `pi-writer` pod carries them. The `pi-render` pod keeps them from its next restart, which
  is why only the writer was cycled.

## 4. The chart

- [x] `templates/pi-writer-session.yaml`, `templates/pi-render-session.yaml`: an additive
  `mcp-egress` NetworkPolicy to `app.kubernetes.io/name: mcpserver` on 8080.
- [x] `helmfile template` renders both policies.

## 5. Tests

- [x] `test/ledger.test.mjs`, `test/session-lib.test.mjs`: the exposure map, and that an empty URL
  omits a server.
- [x] `test/session-server.test.mjs` (both): the written `mcp.json` and the `-e builtin:mcp` argv.
- [x] `node --test 'test/*.test.mjs'` green in both adapters.

## 6. Documentation

- [x] `agents/adapters/pi-writer/README.md`, `agents/adapters/pi-render/README.md`: what the catalog
  adds and why the write tools are hidden.
- [x] `agents/sympozium/MEMORY.md`: the image-default URLs, the explicit egress rule, and the
  `--no-extensions` pairing.
