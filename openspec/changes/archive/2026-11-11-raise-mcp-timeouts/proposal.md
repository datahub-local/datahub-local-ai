# Proposal

## Why

Four ceilings bound one MCP tool call in this homelab: the server's own backend
timeout, the bridge timeout the Sympozium controller applies, the Hermes client
timeout, and the Pod probe that decides whether the process survives. They were
never stated together, and three of the four servers this repository deploys took
the chart's 30s bridge default:

- `homelab-facts` at 30s cut off every measured call to its three name-resolving
  tools: `find_object` 31.9 to 40.7s, `logs` 22.0 to 52.3s, `why_failed` 34.7 to
  60.2s over 22 calls on 2026-11-14. The base cost is the Kubernetes list
  fan-out (`find_object` lists thirteen kinds), not the 20s Prometheus and Loki
  ceilings, which those calls never reach. The bridge cut each call at 30.01s.
- `semantic` and `semantic-finance` pair a 30s Trino timeout with a 30s bridge, so
  the server's own error can never surface before the bridge times out. `mcp-trino`
  already pairs 30 inside with 60 outside.
- `utils` may fetch for 120s but its catalog entry allows 30s, so anything slower
  than 30s is unreachable through the catalog.

The bridge applies the persona's own `mcpServers[].timeout`; the
`MCPServer.spec.timeout` is inherited only when that entry omits one (Sympozium
`resolveMCPServerURLs`, v0.13.0). Every persona states 30, so raising the catalog
alone would have changed no agent's call.

## What Changes

- `homelab-facts` sets `timeout: 90` on its `MCPServer` and on every persona that
  mounts it, above the measured 60.2s p-max with 29.8s of headroom. The number is
  set by the measured calls, not by the 20s HTTP ceilings.
- `semantic` and `semantic-finance` set `timeout: 60` on their `MCPServer`;
  `homelab-oracle.yaml` states 60 for `semantic`, so the persona does not undercut
  the catalog. The same file's `trino` entry goes from 30 to 60 to match core's
  catalog; that server is rendered by `datahub-local-core`, so the new gate cannot
  see it.
- `utils` sets `timeout: 130`, above the 120s temp fetch. The 120 exists for n8n's
  direct `temp_store` call, which bypasses the catalog; no agent mounts the server.
- `agents/sympozium/templates/ensembles.yaml` fails the render when a persona's
  `mcpServers[].timeout` is lower than the entry this chart renders, because that
  is the value the bridge actually applies.
- The chart keeps its 30s default for a new server, but every server here now
  states its value.
- The four-layer rule and the effective per-server table are recorded once in
  `datahub-local-ai-mcp/docs/deployment.md`; this repository links to it rather
  than keeping a second copy.

Not changed: the server code. The inner Prometheus, Loki, Garage, Trino and fetch
timeouts keep their values. The `homelab-facts` single-worker executor and its
serial list fan-out are recorded as the remaining throughput limit; shortening
them is a server change, not a bridge number.

## Capabilities

### Modified Capabilities

- `homelab-agent-fleet`: the fleet's MCP servers carry explicit, ordered timeouts,
  and each persona states the value its bridge applies.

## Impact

- `agents/sympozium/values/default.yaml.gotmpl`: four `timeout` values.
- `agents/sympozium/projects/*/agents/*.yaml`: the eight persona entries that
  mount these servers.
- `agents/sympozium/templates/ensembles.yaml`: the persona-versus-catalog gate.
- `docs/agent/mcp-servers.md`: one paragraph pointing at the shared table and
  naming the value the bridge applies.
- The companion changes are in `datahub-local-core` (explicit Hermes client
  timeouts) and `datahub-local-ai-mcp` (the table). The rendered `MCPServer`
  objects for these four servers change value; no new workload, image or Secret.
