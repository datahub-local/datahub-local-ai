# Proposal

## Why

Four ceilings bound one MCP tool call in this homelab: the server's own backend
timeout, the `MCPServer.spec.timeout` the catalog bridge applies, the Hermes client
timeout, and the Pod probe that decides whether the process survives. They were
never stated together, and three of the four servers this repository deploys took
the chart's 30s bridge default:

- `homelab-facts` pairs a 20s Prometheus and Loki timeout with a 30s bridge, which
  leaves 10s for serialization and queueing on a 4-node Pi cluster.
- `semantic` and `semantic-finance` pair a 30s Trino timeout with a 30s bridge, so
  the server's own error can never surface before the bridge times out. `mcp-trino`
  already pairs 30 inside with 60 outside.
- `utils` may fetch for 120s but its catalog entry allows 30s, so anything slower
  than 30s is unreachable through the catalog.

## What Changes

- `homelab-facts`, `semantic` and `semantic-finance` set `timeout: 60` on their
  `MCPServer`, giving 40s of headroom over the 20s Prometheus/Loki ceilings and
  30s over Trino.
- `utils` sets `timeout: 130`, above the 120s temp fetch. The 120 exists for n8n's
  direct `temp_store` call, which bypasses the catalog; no agent mounts the server.
- The chart keeps its 30s default for a new server, but every server here now
  states its value.
- The four-layer rule and the effective per-server table are recorded once in
  `datahub-local-ai-mcp/docs/deployment.md`; this repository links to it rather
  than keeping a second copy.

Not changed: the server code. The inner Prometheus, Loki, Garage, Trino and fetch
timeouts keep their values, because raising the bridge is enough to give each one
headroom.

## Capabilities

### Modified Capabilities

- `homelab-agent-fleet`: the fleet's MCP servers now carry explicit, ordered
  timeouts instead of the chart default.

## Impact

- `agents/sympozium/values/default.yaml.gotmpl`: four `timeout` values.
- `docs/agent/mcp-servers.md`: one paragraph pointing at the shared table.
- The companion changes are in `datahub-local-core` (explicit Hermes client
  timeouts) and `datahub-local-ai-mcp` (the table). The rendered `MCPServer`
  objects for these four servers change value; no new workload, image or Secret.
