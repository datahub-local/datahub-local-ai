# Design

## Context

Read off the `datahub-local-core` catalog and the two adapters.

- Core's MCP values deploy `mcp-github` (github-mcp-server v2.1.0 behind a proxy sidecar that mints
  the App token per request) and `mcp-firecrawl-http`, both on 8080, both with
  `app.kubernetes.io/name: mcpserver` on the Pods.
- Live `kubectl get mcpserver -n automation` reports both `READY true`; `tools/list` on the GitHub
  server returns 45 tools, write tools included.
- Both adapters run Pi 1.4.0 with `--no-extensions`. In 1.4.0 that flag disables discovered,
  configured and built-in extensions, and `-e builtin:mcp` loads the MCP client back.
- Pi reads servers from `<agent-dir>/mcp.json`; a server with `exposure: hidden` can expose selected
  tools through `toolExposure`.
- `AgentRuntime` has no `env` field, so a URL cannot be passed to the session from the chart.

## Decisions

### D1. GitHub and Firecrawl, read-only, direct

The article lane needs examples, commands and manifests; the render lane needs worked compositions.
GitHub answers both from source, Firecrawl reaches a documentation site the repository does not
carry. The catalog's other servers are about this cluster (k8s, trino, postgres, grafana) and are not
what either lane researches.

Exposure is `hidden` at the server and `direct` for the read tools the prompts name. `direct` is
deliberate: codemode is Pi's default and would put a third calling convention between the model and
six read tools. The 45-tool list stays out of the system prompt because only the declared subset is
exposed.

Rejected: letting the GitHub server's write tools through. `toolsDeny` in the catalog already hides
the destructive ones, but `create_or_update_file` and `push_files` remain, and a drafting turn has no
business writing to a repository.

### D2. The addresses come from the deployment, never the image

Both adapters read `SYMPOZIUM_GITHUB_MCP_URL` and `SYMPOZIUM_FIRECRAWL_MCP_URL` and carry no
default; an unset variable omits that server. A release name is a cluster fact, and a published
image holding one is a second copy of what core already owns. The names are cluster-level rather
than per-adapter for the same reason: one policy can set them for every harness session.

Nothing in the CRDs can set that env. The HarnessSession controller builds the session container's
environment from a fixed list, and `Agent.spec.agents.default.env` is applied on the AgentRun path
only. Core's `sympozium_upstream_fixes.yaml` therefore injects the two variables on pod admission
(fix 8): a MutatingAdmissionPolicy matching `app.kubernetes.io/name: harness-session`, with a JSON
patch that appends when the container has an `env` array and adds one when it does not. The second
arm matters because `failurePolicy: Fail` turns a patch error into a rejected session.

Rejected: image defaults (a cluster name baked into a published image), and a chart knob that the
controller ignores — the trap the render README already records for resources.

### D3. One additive NetworkPolicy per session

The controller's session policy already admits 8080 anywhere, so this is not what enables the call.
It is what makes the session's reach readable: a `to` on `mcpserver` Pods rather than an open port.
The writer's loopback source proxy is not in the path — `NO_PROXY` carries `.svc` and
`.cluster.local`, and Node's `fetch` ignores the proxy variables.

### D4. The prompts keep the ledger rule

`get_file_contents` returns text with no addressable page, so the writer prompt names
`https://raw.githubusercontent.com/<owner>/<repo>/<ref>/<path>` as the ledger URL. That host is
already in `DEFAULT_ARTICLE_SOURCE_HOSTS`, and the server's own refetch is what decides whether the
block exists. A Firecrawl read is ledgered by the documentation page it opened, which must be on the
caller's `source_hosts`.

### D5. The catalog is optional at runtime

An unset URL writes no server, `-e builtin:mcp` stays harmless, and both prompts name the catalog
only when its tools are present. A cluster without the policy, or with an MCP server down, degrades
to the paths that existed before this change rather than failing a turn.

## Risks

- **A server that does not answer.** Pi reports the failure once and the turn continues; the prompts
  name the backend `curl`/`hyperframes docs` path, so a dead catalog degrades rather than fails.
- **A raw URL at the wrong ref.** `get_file_contents` may be read at a branch head; the raw URL is
  then a moving target. The server records the excerpt and hash per turn, which is the same exposure
  a docs page already has.
- **Model reads too much.** Each search result counts against the prompt's lookup budget; that is a
  prompt bound, not enforcement, the same shape as the existing `curl` budget.

## Open questions

- [UNVERIFIED] A live model turn through the catalog. The image that reads the env is not published
  yet, so the first turn after the images are rebuilt and rolled is the remaining check. The env
  injection itself is verified: a server dry-run of a `harness-session` pod carries both variables,
  and the replaced `pi-writer` pod carries them.
