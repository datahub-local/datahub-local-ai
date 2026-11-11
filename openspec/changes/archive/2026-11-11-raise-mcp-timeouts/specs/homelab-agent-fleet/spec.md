# Spec Delta

## ADDED Requirements

### Requirement: MCP timeouts are explicit and ordered

Every `MCPServer` this repository renders SHALL state `spec.timeout` rather than
take the chart's 30s default, and the value SHALL sit above the server's own
backend ceiling with at least 10 seconds of headroom. The four layers (server
backend, catalog bridge, Hermes client, Pod probe) and their effective values
SHALL be recorded once in `datahub-local-ai-mcp/docs/deployment.md`, and this
repository SHALL link to that table rather than keep a second copy.

#### Scenario: A server with a backend ceiling near the chart default

- **WHEN** a server's own Prometheus, Loki or Trino timeout is 20s or 30s
- **THEN** its rendered `MCPServer` carries a `timeout` of at least 60s
- **AND** the bridge does not expire before the server can return its own error

#### Scenario: A server with a long internal fetch

- **WHEN** a server may spend 120s on one internal fetch
- **THEN** its rendered `MCPServer` carries a `timeout` above 120s
- **AND** the reason the long fetch exists is recorded with the table

#### Scenario: A new server takes the chart default

- **WHEN** a new MCP server omits `timeout`
- **THEN** the render carries 30s
- **AND** the change is rejected unless an explicit `timeout` with at least 10s of headroom over the ceiling is set
