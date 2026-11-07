# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

A monorepo of data workflow definitions for a local/homelab Datahub stack. Sub-projects are grouped by what they are: `agents/` holds AI agent definitions, `workflows/` holds the data pipelines and the dashboards built on them. The Python ones have their own `pyproject.toml` and `uv` environment:

- `agents/n8n/` — n8n workflow JSON exports, LLM prompt templates and JSON config datasets, plus one operational script that pushes export changes back to the live instance; see [n8n workflows](docs/agent/n8n.md)
- `agents/sympozium/` — Sympozium agent ensembles (Kubernetes CRs) plus a Helm release that deploys them onto the control plane datahub-local-core runs in `automation`; also deploys the MCP servers and owns the data they mount (`config/`), though the server code itself lives in [`datahub-local-ai-mcp`](https://github.com/datahub-local/datahub-local-ai-mcp); see [Sympozium agents](docs/agent/sympozium.md) and [MCP servers](docs/agent/mcp-servers.md)
- `workflows/airflow/` — Airflow DAGs that orchestrate the dlt + dbt tasks via Kubernetes pods
- `workflows/dbt/` — dbt Core pipelines on **Trino** (homelab) / **DuckDB** (local), Iceberg + Apache Polaris, medallion architecture; a thin Python `dbt_runner` wraps `dbt build`
- `workflows/dlt/` — [dlt](https://dlthub.com) ingest/export pipelines (CSV → bronze; silver/gold → Postgres) that run *around* dbt
- `workflows/superset/` — Superset dashboard export bundles per project (`workflows/superset/projects/<name>/dashboard_export/` YAML) plus a Helm release (`workflows/superset/release/`) that ships them as ConfigMaps labeled `superset_dashboard=1` for the dashboard sidecar in datahub-local-core. After editing YAML: `python3 workflows/superset/scripts/build_bundles.py` rebuilds the zips under `release/files/` — the build refuses a dataset that reads bronze, and the archive is deterministic in contents and timestamps but not byte-for-byte across interpreters, because the deflate stream is the building zlib's — then `helmfile apply` from `workflows/superset/release/` deploys them. Object `uuid`s are the stable identity across re-imports — never regenerate them once deployed.

## Deep dives

Read the matching file in full before editing anything under that path. These are
not summaries; they are the rules, and the top of this file does not repeat them.

| Path you are editing | Read first |
| --- | --- |
| `agents/n8n/**` | [`docs/agent/n8n.md`](docs/agent/n8n.md) |
| `agents/sympozium/**` | [`docs/agent/sympozium.md`](docs/agent/sympozium.md) |
| the MCP server catalog and the data this repository mounts for it | [`docs/agent/mcp-servers.md`](docs/agent/mcp-servers.md) |

## AI prompt policy

This applies to **every** prompt in this repository, including n8n templates,
Sympozium persona prompts, and any future AI workflow. Prompts must be short,
literal, and action-oriented — like a compact GitHub/Copilot prompt. State the
job, required inputs or tools, bounded steps, no-result behavior, and required
output. Put deterministic logic in code and durable rationale in documentation;
do not turn prompts into tutorials, copied schemas, or background essays.

**Every instruction a model reads is declared in a prompt file or the authoring
brief.** In n8n that is `agents/n8n/prompts/*.md`, fetched by `DownloadTemplate`
with its placeholders filled; the article drafting prompt is
`agents/adapters/pi-writer/prompts/*.md`, rendered by the adapter from the entry's
fields; in Sympozium it is `systemPromptFile` / `schedule.taskFile`. The brief
(megaprompt) is assembled in a Code node or by the adapter from those files plus
values, and may own selection and formatting — never a rule, a definition or an
example that exists nowhere else. An inline instruction in a Code
node, a model node's `text`, an HTTP body or a tool description is a gap: the model
reads it and a reviewer does not, and editing the prompt file cannot fix it. A
definition the model must follow — what a scene is, what a form means — is written
where the model reads it, never inferred from a count or a field name.

## Naming conventions

Sub-projects follow a consistent structure:

```
workflows/<tool>/
  src/
    <tool>_runner/        Python entry point package (python -m <tool>_runner)
  projects/
    <project>/            project-specific code or dbt SQL/YAML
  tests/
    <project>/            tests grouped by project
    test_<cross>.py       cross-project tests stay at the tests/ root
  Dockerfile
  pyproject.toml          name: datahub-local-ai-<tool>
  README.md
```

`dbt`, `dlt` and `mcp` all use a `src/` layout with a `projects/` directory:

- **dbt**: `src/dbt_runner/` is the only Python package; `projects/example_db/`, `projects/pi/`, `projects/bodega/` are SQL+YAML dbt projects (not Python packages).
- **dlt**: `src/dlt_runner/` is the runner; `projects/example_db/` and `projects/bodega/` are Python pipeline packages installed via hatchling.
- **mcp**: no longer in this repository. The servers are in
  [`datahub-local-ai-mcp`](https://github.com/datahub-local/datahub-local-ai-mcp);
  this repo keeps only the data they mount — `agents/sympozium/config/` for
  homelab-facts, and `workflows/dbt/semantic/` for the semantic registry, which
  stays beside the dbt models whose columns it references.

| What                  | Convention                    | Examples                                    |
| --------------------- | ----------------------------- | ------------------------------------------- |
| Package name          | `datahub-local-ai-<tool>`     | `datahub-local-ai-dbt`                      |
| Python runner module  | `<tool>_runner`               | `dbt_runner`, `dlt_runner`                  |
| Container entry point | `python -m <tool>_runner`     | `ENTRYPOINT ["python", "-m", "dbt_runner"]` |
| Project dir           | lowercase, underscores        | `example_db`, `pi`                          |
| Test subdirs          | per-project, mirroring source | `tests/example_db/`, `tests/pi/`            |

Two sub-projects ship Helm releases instead of Python entry points and keep their
reviewable source under `projects/` rather than following the table above:

- `workflows/superset/` builds `projects/` into committed zips under
  `release/files/` with `scripts/build_bundles.py`, because a Superset bundle is
  a **binary** zip and Helm cannot assemble one. ArgoCD points at `release/`.
- `agents/sympozium/` generates **nothing**: its Helm templates read `projects/`
  at render time, so the sub-project root is the chart root (Helm's `.Files`
  cannot read above the chart directory) and ArgoCD points at
  `agents/sympozium/`, whose render is its only build-time gate.

Prefer the sympozium shape for anything textual. A committed generated file is a
second copy that can fall out of date with its source; only reach for a build
step when the artifact genuinely cannot be produced by a template.

One exception to "lowercase, underscores": names that become Kubernetes object
names must be DNS-1123, so `agents/sympozium/projects/` uses kebab-case
(`homelab-ops`, `sre-sentinel`). Prompt *files* there stay `snake_case.md`, as in
`agents/n8n/prompts/`.

### Design specs (`openspec/`)

Design specs live in `openspec/`, which is the only spec system in this repo.
`docs/specs/` was retired on 2026-10-07; its six design files (five topics) are
preserved verbatim in
`openspec/changes/archive/2026-10-07-retire-docs-specs/designs/`.

- **Active work is an OpenSpec change.** `openspec/changes/<kebab-id>/` with
  `proposal.md` (why, what, capabilities, impact, non-goals), `design.md`
  (context, gate findings, decisions, risks, open questions, definition of done)
  and `tasks.md` (checkboxed tasks with stable ids and cross-repo `blocked by`
  links). `openspec validate --all` gates it and `openspec list` reads it.
- **Completed work is archived, never deleted.** `openspec archive <id>` moves it
  to `openspec/changes/archive/<date>-<id>/`. `openspec/specs/<capability>/spec.md`
  is the resulting current behaviour, written as `Requirement`/`Scenario` deltas.
- **A spec is a decision record.** Keep the reasoning that was rejected and why
  (the gate findings and alternatives), because the next change re-litigates it
  otherwise. Mark tasks `[x]` as they land rather than removing them.
- **Renaming a spec means grepping the whole repo.** Code points at these files —
  `workflows/dbt/semantic/bodega.yaml` carries a path to the semantic-layer spec
  in a comment, and a stale path there is invisible until someone follows it.
- **Mark what you could not verify.** `[UNVERIFIED]` in place beats dropping a
  fact or asserting it — the same standing rule as agent prompts, for the same
  reason.

## Bronze is not a consumer layer

**Nothing user-facing reads bronze.** Superset datasets and the semantic
registry may reference `silver.*` and `gold.*` only. If a consumer needs
something that exists solely in bronze, the answer is a silver model, never a
dataset or a `semantic_model` pointing at the raw table.

The reason is not tidiness. Bronze is the landing zone as the source emitted it:
`bronze.bodega.raw_invoices` keeps `items_json` and `taxes_json` as unparsed
JSON strings, so its 85 rows are 85 *invoices* and the 1,682 line items inside
them are not queryable until `silver.bodega.invoice_items` expands them. A chart
built on bronze would silently count invoices where it meant items. Bronze also
carries loader bookkeeping (`_dlt_load_id`, `_dlt_id`, `_kafka_offset`,
`_batch_timestamp`) that means nothing to a reader, has no `persist_docs`
descriptions, and is rewritten by the ingest pipeline's stale-row cleanup — so a
number read from it is not stable between runs.

How each half is held today:

- **Semantic MCP: structural.** `SEMANTIC_WAREHOUSE_SCOPES` is
  `silver.bodega,gold.bodega`, so the server never discovers a bronze table and
  a registry `ref()` to one fails to resolve. Do not add a bronze scope.
- **dbt: structural.** `raw_invoices` is a **source**, not a model, and
  `dbt_project.yml` materialises only into `+database: silver` or `gold`. No
  dbt model can land in bronze.
- **Superset: at build time.** `scripts/build_bundles.py` refuses to build a
  project whose dataset YAML selects from `bronze.` or declares
  `catalog: bronze`, and it matches the raw YAML so the check holds whatever
  shape an export takes. A bundle therefore cannot be produced from the landing
  zone, and every committed dataset reads silver or gold. What it does not
  cover is a dataset edited in the running Superset rather than in
  `projects/`: the sidecar imports the bundles, but nothing else stops a UI
  edit, and Trino's `rules.json` still grants `superset` the bronze catalog —
  narrowing that rule is the enforcing fix for that path.

Trino's access-control file lists users explicitly with **no catch-all**, so an
unlisted user is denied every statement — verified: an invented name fails even
`SELECT 1`. Currently listed: `admin` (all), `dbt`/`superset`/`maintenance`
(all on the medallion catalogs), `mcp` (read-only). Read the live rules before
assuming a user works; the set has changed at least once.

## Comments in YAML and helmfile

**Config files carry values, not prose.** `values/*.gotmpl`, `helmfile.yaml.gotmpl`,
`Chart.yaml` and the Helm templates carry **no comments at all**; the rationale
for a knob goes in `agents/sympozium/MEMORY.md`, and anything a reader needs
before touching the file goes here. This is enforced by review only.

The reason is not brevity. A comment beside a value is a second copy of a
decision that drifts from it — the `toolsAllow` note had been pasted into nine
persona files and the `grafana_list_datasources` note into four before they were
stripped, and removing all of it changed neither the parsed YAML nor a byte of
`helm template` output. Two further points specific to helmfile: it renders
`values/default.yaml.gotmpl` as a Go template *before* Helm parses it as YAML,
**comments included**, so a literal brace pair inside a comment is an
undefined-function error that `helm template` never sees — that is exactly how a
comment broke the ArgoCD sync on 2026-08-23 after CI had passed. And a values
file is the one place a reviewer looks to see what a cluster is actually set to,
which prose buries.

Python and shell keep comments, sparingly, for a non-obvious *why*. Workflow
files under `.github/` keep them too — they are procedure, not config.

## Git commits

Governed by the global rule in `~/.claude/AGENTS.md`: **never commit unless asked
directly**, and suggest one short `type(scope): summary` line instead. Repeating
it here would be a second copy that drifts; the global file is the one place it
lives.

The local convention it points at: this repo's history uses
(`fix(dbt,semantic): ...`, `docs(spec): ...`), and the rationale a body would
carry goes where it is actually read — this file, a sub-project `MEMORY.md`, or
an OpenSpec change in `openspec/` — not into a log entry nobody greps. Work here spans this
repo and datahub-local-core, so suggest one message per repository.

## Commands

Each sub-project uses `uv`. Run commands from the sub-project directory.

### dbt (`workflows/dbt/`)

dbt runs SQL directly on Trino (homelab) or DuckDB (local). The `dbt_runner`
package is just a convenience wrapper around `dbt build`.

```bash
# Install
uv sync --extra dev

# Run project (local target — DuckDB, no external services)
uv run python -m dbt_runner --project pi --target local
uv run python -m dbt_runner --project example_db --target local   # needs bronze source seeded first

# Run project (homelab target — Trino/Polaris/S3 required)
uv run python -m dbt_runner --project example_db --target homelab

# Validate a project without a warehouse connection
uv run dbt parse --project-dir projects/pi --profiles-dir projects/pi --target local

# Tests (no warehouse — project structure, model SQL, dbt parse)
uv run pytest tests/ --ignore=tests/example_db/test_integration.py
# DuckDB end-to-end (seeds bronze, runs dbt build, asserts medallion tables)
uv run pytest tests/example_db/test_integration.py

uv run ruff check .
```

### dlt (`workflows/dlt/`)

```bash
uv sync --extra dev
# Full local chain (DuckDB), shared warehouse dir with dbt:
export DBT_DUCKDB_DIR=/tmp/duckdb
uv run python -m dlt_runner --pipeline ingest --project example_db --target local
uv run python -m dlt_runner --pipeline export --project example_db --target local
uv run pytest
uv run ruff check .
```

### Airflow (`workflows/airflow/`)

```bash
uv sync
uv run pytest          # all tests
uv run pytest tests/tasks/test_dlt.py  # single file
```


## Test structure

- dbt `tests/` are lightweight: project/profile structure, model SQL, and `dbt parse` — no warehouse. `tests/example_db/test_integration.py` seeds the bronze source in DuckDB, runs `dbt build` **in a subprocess** (avoids DuckDB's per-process "file already attached" conflict), and asserts the medallion tables.
- dlt `tests/example_db/` covers the local DuckDB ingest+export integration test; `tests/test_config.py` covers `projects/example_db/config.py` helpers (cross-project, stays at the tests root).
- airflow `tests/` import the DAGs and check the dbt/dlt task arguments, env, and ordering — `test_pi_dag.py` covers the pi DAG; `test_example_db_dag.py` covers example_db.
- MCP server tests moved with the code to `datahub-local-ai-mcp`. They need no
  cluster, and are where nine prose validators went: regexes that policed
  English in a prompt became assertions about the expression the server sends.
  Worth knowing that the counter/gauge test shows a suffix rule failing this
  cluster in both directions — `cnpg_backends_total` is a gauge despite
  `_total`, `cnpg_pg_stat_archiver_failed_count` a counter despite `_count`.
- `agents/sympozium/` tests only the delivery hook (`tests/test_deliver_slack.py`, the one piece of code there that runs in production). It has no source validator: `scripts/validate.py` was deleted on 2026-08-31 because most of it mirrored the cluster and the upstream CRD, and a mirror that drifts fails correct config. CI runs the hook tests and then renders the chart through `helmfile` — the render is the only gate on `projects/`, so anything it cannot see reaches the admission webhook (loud) or the running agent (silent). See `agents/sympozium/MEMORY.md` for what is now unguarded.
- **No unit tests for n8n workflows.** Do not add a test under `agents/n8n/` that asserts a workflow export, a Code node, a prompt or a dataset. Those files are a backup of the live instance and are edited for reasons a test cannot know, so the next correct change goes red; the review diff, the live apply and the next run are the check. Owner rule, 2026-11-07. Adapter tests are unaffected, because they cover code the image runs.
- **No tests for prompt, config or export files.** Do not add a test that asserts the contents of a prompt, `opencode.json`, a values file or a workflow export: it pins a file edited for reasons the test cannot know, so the next correct change goes red and the failure says nothing about whether the agent or the cluster works. That is the same drift the sympozium validator died of. Gate those with the build (the adapter's `jq` asserts, `helmfile template`) and review them in the diff.
