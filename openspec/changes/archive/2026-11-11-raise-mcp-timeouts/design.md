# Design

## Context

The controller writes the bridge's timeout from the AgentRun's
`mcpServers[].timeout`, and inherits `MCPServer.spec.timeout` only when that entry
is absent (`resolveMCPServerURLs` in Sympozium `v0.13.0`: `if srv.Timeout == 0 &&
mcpServer.Spec.Timeout > 0`). Every persona in this repository states 30, so the
catalog number alone bounded nothing. The chart template renders
`{{ $server.timeout | default 30 }}`, so an omitted value silently becomes 30.
Three of the four servers here paired a backend ceiling close to or above 30:

| Server | Backend | Measured p-max | Bridge before | Bridge after |
| --- | --- | --- | --- | --- |
| `homelab-facts` | Kubernetes lists unbounded; Prometheus 20, Loki 20, Garage 10 | 60.2 | 30 | 90 |
| `semantic` | Trino 30 | not measured | 30 | 60 |
| `semantic-finance` | Trino 30 | not measured | 30 | 60 |
| `utils` | fetch 120 | not measured | 30 | 130 |

The measured column is 22 calls on 2026-11-14 against
`http://datahub-local-ai-mcp-homelab-facts.automation.svc:8080/mcp`, at a 180s
client ceiling:

| Tool | p50 | max | What dominates |
| --- | --- | --- | --- |
| `find_object` | 35.6 | 40.7 | thirteen cluster-wide Kubernetes lists, serial |
| `logs` | 33.4 | 52.3 | seven lists plus a second Pod list; Loki only on fallback |
| `why_failed` | 42.8 | 60.2 | the same lists plus one Event list per pod; Loki only on fallback |

None of the three calls Prometheus. Every 30s-ceiling call ended at 30.01s with a
client timeout. `why_failed` on `job-dlt-ingest-finance-qcryeee2` reached 60.2s on
the Loki fallback, and a call retried behind a tool the bridge had already
abandoned took 64.9s, because the server runs every JSON-RPC request on one
worker.

Hermes does not register these four, so there is no Hermes client ceiling to
match. n8n calls `utils` directly over the Service, so the catalog value never
bounded its fetch; 130 is the value that keeps the rule true if an agent ever
mounts it.

## Gate findings

- **The rendered objects carry the new values.** `helmfile template` in
  `agents/sympozium/` renders `datahub-local-ai-mcp-homelab-facts` at 90,
  `semantic` and `semantic-finance` at 60, and `utils` at 130. Every persona that
  mounts one states the same value, and a persona below its catalog entry fails
  the render.
- **The bridge reads the persona, not only the catalog.** The earlier draft
  raised `MCPServer.spec.timeout` alone. That value is inherited only when the
  persona omits `mcpServers[].timeout`, which no persona here does.
- **The rule is four layers, not three.** The Pod probe is the layer that decided
  the postgres incident: the stdio adapter answered `/healthz` from the same child
  as tool calls, a pre-initialize request blocked both, and the probe restarted the
  container after its 30s initial delay plus five 15s periods. No tool timeout was
  involved. The probe values on a controller-managed `MCPServer` are not in the
  CRD, so they cannot be sized here.
- **A single table belongs in `datahub-local-ai-mcp`.** The rule spans both
  repositories that deploy the catalog. Keeping one copy there, next to the server
  code, avoids a second copy in this repository that drifts.

## Decisions

- **D1: Raise the bridge, not the inner ceiling.** The 20s Prometheus and Loki
  queries are already generous; the bridge was the tight side. For
  `homelab-facts`, 90s is set by the measured p-max (60.2s), not by those HTTP
  ceilings.
- **D2: `utils` goes to 130, not down to 30.** The 120s fetch is real work for
  n8n's `temp_store`; lowering it would cut a large asset download. Raising the
  catalog value costs nothing because no persona mounts the server.
- **D3: No server-code change.** The inner timeouts are the correct side of the
  budget; only the bridges were too tight. The single worker and the serial list
  fan-out are the remaining throughput limit, and shortening them is a separate
  server change.
- **D4: Record the opencode equality as an exception.** The bridge and the Hermes
  client are both 900 because the shim's own `run_task` ceiling is 300, so neither
  bounds a real turn.

## Risks / Trade-offs

- **A stuck call now occupies an agent for up to 90s instead of 30s.** The
  alternative was a server error that could never surface. The evidence is the
  60.2s measured call and the 64.9s queued retry, not a headroom argument.
- **The server still runs one tool at a time.** Two concurrent callers can queue
  past 90s even though one call fits. Parallelising the list fan-out or widening
  the executor is the fix; it is not part of this number change.
- **`utils` at 130 could hold one worker for two minutes.** The server is
  single-worker by design and n8n already waits 120s for the fetch; the catalog
  entry now matches the caller rather than hiding the longer path.

## Open Questions

- **Whether the catalog bridge should impose a ceiling at all.** If it let the
  caller's timeout win, the middle layer would disappear. Not changed here,
  because the bridge is the only place a Sympozium agent gets a per-server bound.
- **Whether the postgres probe should be sized.** It cannot be from any repository
  here; the CRD has no probe fields. The adapter needs a read deadline, or the
  controller needs probe settings. Tracked in the MCP timeout table, not fixed by
  a number change.

## Definition of done

- `helmfile template` in `agents/sympozium/` renders the four new values and every
  persona entry, and fails when a persona is below its catalog entry.
- `uv run -- pytest agents/sympozium/tests/ -q` and `ruff` pass.
- `openspec validate --all` passes with this change present.
- The shared table in `datahub-local-ai-mcp/docs/deployment.md` lists the effective
  values for all four layers and the measured p-max.
- The companion `datahub-local-core` change gives each Hermes client timeout
  explicit headroom over its bridge.
