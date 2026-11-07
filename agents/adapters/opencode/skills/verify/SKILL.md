---
name: verify
description: The check command for each datahub-local repository, and which checks the Pod cannot run. Use before reporting DONE, before opening a pull request, and whenever a change needs a gate.
---

# Verify

Run the gate of the repository you changed. Not a subset, not a neighbouring
repository's gate.

## Commands

### `datahub-local-ai`

Each sub-project has its own `uv` environment. Run from the sub-project directory.

| Path | Gate |
| --- | --- |
| `workflows/dbt` | `uv sync --extra dev` then `uv run pytest tests/ --ignore=tests/example_db/test_integration.py` and `uv run ruff check .` |
| `workflows/dbt` (DuckDB end to end) | `uv run pytest tests/example_db/test_integration.py` |
| `workflows/dlt` | `uv sync --extra dev` then `uv run pytest` and `uv run ruff check .` |
| `workflows/airflow` | `uv sync` then `uv run pytest` |
| `workflows/superset` | `python3 workflows/superset/scripts/build_bundles.py` (from the repository root) |
| `agents/n8n` | no unit-test gate: the review diff, the live apply and the next run are the check (see `docs/agent/n8n.md`) |
| `agents/sympozium` | from the root: `uv run -- pytest agents/sympozium/tests/ -q` and `uv run -- ruff check agents/sympozium/files/ agents/sympozium/tests/`, then `helmfile template` in `agents/sympozium/` |
| repository | `openspec validate --all` |

### `datahub-local-ai-mcp`

```
uv sync --extra dev
uv run -- ruff check .
uv run -- pytest -q
```

A Dockerfile, a mount path or a degradation path also needs the container run, not
just the tests: build it, mount data, hit `/healthz` and a `tools/list` POST.

### `datahub-local-core`

```
cd releases/<namespace>
helmfile template
openspec validate --all
```

The render is the gate: ArgoCD runs helmfile, so `helm template` alone misses a Go
template error in a values file.

### `datahub-local`

```
uv sync
uv run mkdocs build --strict
openspec validate --all
```

### `datahub-local-bootstrap`

```
ansible-playbook --syntax-check playbook/<the playbook>.yaml
```

Syntax only. Never `--check` against a host and never a real run.

## What the Pod cannot check

The egress policy admits DNS, LiteLLM, the `mcpserver` pods and the proxy. The
Kubernetes API is not reachable, so:

- `promtool check rules` against the running Prometheus: owner-side. A new or
  edited PromQL expression is `[UNVERIFIED]` until the owner runs it, and the
  report has to say which expression.
- Anything that reads live cluster state as the gate: use `k8s_*` to inspect, and
  report the reading as an inspection rather than as a passing test.
- Anything that applies: never.

## Reporting

One line per command, with the result:

```
- `uv run -- pytest -q` -> 142 passed
- `uv run -- ruff check .` -> clean
- `promtool check rules` -> [UNVERIFIED] no route to Prometheus from the Pod
```

A failing check is reported with its output, not summarised. A check that was not
run is reported as not run, with the reason. "Tests pass" without the command and
the count is not a result.
