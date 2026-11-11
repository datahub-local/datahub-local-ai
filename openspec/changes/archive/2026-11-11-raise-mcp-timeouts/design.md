# Design

## Context

The catalog bridge reads `MCPServer.spec.timeout` and applies it per tool call.
The chart template renders `{{ $server.timeout | default 30 }}`, so an omitted
value silently becomes 30. Three of the four servers here omitted it while pairing
a backend ceiling close to or above 30:

| Server | Backend | Bridge before | Bridge after |
| --- | --- | --- | --- |
| `homelab-facts` | Prometheus 20, Loki 20, Garage 10 | 30 | 60 |
| `semantic` | Trino 30 | 30 | 60 |
| `semantic-finance` | Trino 30 | 30 | 60 |
| `utils` | fetch 120 | 30 | 130 |

Hermes does not register these four, so there is no Hermes client ceiling to
match. n8n calls `utils` directly over the Service, so the catalog value never
bounded its fetch; 130 is the value that keeps the rule true if an agent ever
mounts it.

## Gate findings

- **The rendered objects carry the new values.** `helmfile template` in
  `agents/sympozium/` renders `datahub-local-ai-mcp-{homelab-facts,semantic,semantic-finance}`
  at 60 and `datahub-local-ai-mcp-utils` at 130. The chart template already
  supports `timeout`, so no template change is needed.
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

- **D1: Raise the bridge, not the inner ceiling.** A 20s Prometheus query is
  already generous for this cluster; the bridge was the tight side. Raising the
  bridge also gives the fan-out tools room for serialization.
- **D2: `utils` goes to 130, not down to 30.** The 120s fetch is real work for
  n8n's `temp_store`; lowering it would cut a large asset download. Raising the
  catalog value costs nothing because no persona mounts the server.
- **D3: No server-code change.** The inner timeouts are the correct side of the
  budget; only the bridges were too tight.
- **D4: Record the opencode equality as an exception.** The bridge and the Hermes
  client are both 900 because the shim's own `run_task` ceiling is 300, so neither
  bounds a real turn.

## Risks / Trade-offs

- **A stuck call now occupies an agent for up to 60s instead of 30s.** The
  alternative was a server error that could never surface. The evidence for the
  larger budget is the fan-out in `metrics_store_health` and `alerts_snapshot`,
  not a single measured call.
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

- `helmfile template` in `agents/sympozium/` renders the four new values.
- `uv run -- pytest agents/sympozium/tests/ -q` and `ruff` pass.
- `openspec validate --all` passes with this change present.
- The shared table in `datahub-local-ai-mcp/docs/deployment.md` lists the effective
  values for all four layers.
- The companion `datahub-local-core` change gives each Hermes client timeout
  explicit headroom over its bridge.
