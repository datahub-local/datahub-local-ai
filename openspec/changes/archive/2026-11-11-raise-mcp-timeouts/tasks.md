# Tasks

## 1. Raise the catalog bridges

- [x] 1.1 Set `timeout: 60` on `homelab-facts`, `semantic` and
  `semantic-finance` in `agents/sympozium/values/default.yaml.gotmpl`.
- [x] 1.2 Set `timeout: 130` on `utils`, above its 120s temp fetch.

## 2. State the rule once

- [x] 2.1 Add the four-layer ordering rule and the effective per-server table to
  `datahub-local-ai-mcp/docs/deployment.md`.
- [x] 2.2 Link to that table from `docs/agent/mcp-servers.md` instead of copying
  the values here.

## 3. Gate

- [x] 3.1 `helmfile template` in `agents/sympozium/` renders the four new values.
- [x] 3.2 `uv run -- pytest agents/sympozium/tests/ -q` passes.
- [x] 3.3 `uv run -- ruff check agents/sympozium/files/ agents/sympozium/tests/`
  passes.
- [x] 3.4 `openspec validate --all` passes.

## 4. Companion changes

- [x] 4.1 `datahub-local-core` PR #284 (open): set an explicit Hermes client
  `timeout` for every registered server, each above its bridge with headroom.
- [x] 4.2 `datahub-local-ai-mcp` PR #3 (open): commit the table and record why the
  firecrawl 300s and the postgres park loop were not timeout-size problems.
