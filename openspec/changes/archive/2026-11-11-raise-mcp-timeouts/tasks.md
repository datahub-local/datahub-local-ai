# Tasks

## 1. Raise the catalog bridges

- [x] 1.1 Set `timeout: 90` on `homelab-facts` and `timeout: 60` on `semantic`
  and `semantic-finance` in `agents/sympozium/values/default.yaml.gotmpl`.
- [x] 1.2 Set `timeout: 130` on `utils`, above its 120s temp fetch.
- [x] 1.3 State the same value on every persona entry that mounts one of these
  servers: 90 for `homelab-facts` in the six `homelab-ops` personas and
  `homelab-oracle`, and 60 for `semantic` in `homelab-oracle`.
- [x] 1.4 Fail the render when a persona's `mcpServers[].timeout` is lower than the
  catalog entry it mounts, because the bridge applies the persona value.

## 2. State the rule once

- [x] 2.1 Add the four-layer ordering rule, the effective per-server table and the
  measured p-max to `datahub-local-ai-mcp/docs/deployment.md`.
- [x] 2.2 Link to that table from `docs/agent/mcp-servers.md` instead of copying
  the values here, and name the value the bridge applies.

## 3. Gate

- [x] 3.1 `helmfile template` in `agents/sympozium/` renders the four new values
  and the eight persona entries, and fails when a persona is below its catalog
  entry.
- [x] 3.2 `uv run -- pytest agents/sympozium/tests/ -q` passes.
- [x] 3.3 `uv run -- ruff check agents/sympozium/files/ agents/sympozium/tests/`
  passes.
- [x] 3.4 `openspec validate --all` passes.

## 4. Companion changes

- [ ] 4.1 `datahub-local-core` PR #284 (open at archive time): set an explicit
  Hermes client `timeout` for every registered server, each above its bridge with
  headroom.
- [ ] 4.2 `datahub-local-ai-mcp` PR #3 (open at archive time): commit the table,
  change `homelab-facts` to 90, record the measured p-max, and record why the
  firecrawl 300s and the postgres park loop were not timeout-size problems.
