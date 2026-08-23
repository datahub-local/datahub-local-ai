# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

A monorepo of data workflow definitions for a local/homelab Datahub stack. Sub-projects are grouped by what they are: `agents/` holds AI agent definitions, `workflows/` holds the data pipelines and the dashboards built on them. The Python ones have their own `pyproject.toml` and `uv` environment:

- `agents/n8n/` — n8n workflow JSON exports, LLM prompt templates and JSON config datasets (no Python code); see [n8n workflows](#n8n-workflows)
- `agents/sympozium/` — Sympozium agent ensembles (Kubernetes CRs) plus a Helm release that deploys them onto the control plane datahub-local-core runs in `automation`; see [Sympozium agents](#sympozium-agents)
- `workflows/airflow/` — Airflow DAGs that orchestrate the dlt + dbt tasks via Kubernetes pods
- `workflows/dbt/` — dbt Core pipelines on **Trino** (homelab) / **DuckDB** (local), Iceberg + Apache Polaris, medallion architecture; a thin Python `dbt_runner` wraps `dbt build`
- `workflows/dlt/` — [dlt](https://dlthub.com) ingest/export pipelines (CSV → bronze; silver/gold → Postgres) that run *around* dbt
- `workflows/superset/` — Superset dashboard export bundles per project (`workflows/superset/projects/<name>/dashboard_export/` YAML) plus a Helm release (`workflows/superset/release/`) that ships them as ConfigMaps labeled `superset_dashboard=1` for the dashboard sidecar in datahub-local-core. After editing YAML: `python3 workflows/superset/scripts/build_bundles.py` rebuilds the reproducible zips under `release/files/`, then `helmfile apply` from `workflows/superset/release/` deploys them. Object `uuid`s are the stable identity across re-imports — never regenerate them once deployed.

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

Both `dbt` and `dlt` use a `src/` layout with a `projects/` directory:

- **dbt**: `src/dbt_runner/` is the only Python package; `projects/example_db/`, `projects/pi/`, `projects/bodega/` are SQL+YAML dbt projects (not Python packages).
- **dlt**: `src/dlt_runner/` is the runner; `projects/example_db/` and `projects/bodega/` are Python pipeline packages installed via hatchling.

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
  `agents/sympozium/`. `scripts/validate.py` only validates.

Prefer the sympozium shape for anything textual. A committed generated file is a
second copy that can fall out of date with its source; only reach for a build
step when the artifact genuinely cannot be produced by a template.

One exception to "lowercase, underscores": names that become Kubernetes object
names must be DNS-1123, so `agents/sympozium/projects/` uses kebab-case
(`homelab-ops`, `sre-sentinel`). Prompt *files* there stay `snake_case.md`, as in
`agents/n8n/prompts/`.

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

### Sympozium (`agents/sympozium/`)

No runner and no `pyproject.toml` of its own — the validator uses the root
`sympozium` extra. Run from the **repository root**:

```bash
uv sync --extra sympozium
uv run python agents/sympozium/scripts/validate.py

cd agents/sympozium
helm template datahub-local-ai-sympozium . -n automation -f values/default.yaml.gotmpl
helmfile apply                                              # or let ArgoCD sync it
```

With a cluster reachable, validate against the real CRD schemas and the
admission webhook before committing — this persists nothing:

```bash
helm template datahub-local-ai-sympozium . -n automation -f values/default.yaml.gotmpl \
  | kubectl apply --dry-run=server -f -
```

Rendering **is** the build step, so a render failure is a broken deploy. The
templates `fail` loudly on a missing prompt file or a name/directory mismatch.

## Architecture

### Engines and targets

dbt models run identical `database.schema.table` SQL on both engines:

| Target              | dbt engine                                                  | dlt ingest / export                        | When to use                   |
| ------------------- | ----------------------------------------------------------- | ------------------------------------------ | ----------------------------- |
| `homelab` (default) | Trino on Kubernetes (Iceberg over Apache Polaris REST + S3) | Iceberg via Apache Polaris REST / Postgres | Production / CI               |
| `local`             | DuckDB (one file per catalog)                               | DuckDB files / DuckDB export file          | Local dev — no external infra |

dbt is **stateless** — no plan/apply or state store. All models are `materialized='table'`.

### dbt projects and the runner

Each project is a self-contained dbt project under `workflows/dbt/projects/<name>/` (`dbt_project.yml`, `profiles.yml`, `models/`). `src/dbt_runner/__main__.py` (`--project --target [--select] [--full-refresh]`) just resolves the project dir and invokes `dbt build` in-process. It does **not** ingest or export — those are dlt projects. `PROJECTS_DIR` is read from `DBT_PROJECTS_DIR` env var (set to `/app/projects` in Docker) or derived from `__file__` for local editable installs.

- **`example_db`** follows the medallion pattern with three catalogs (`bronze`/`silver`/`gold`).
- **`pi`** is a Monte Carlo π estimator tunable via `PI_PARTITIONS`, `PI_SAMPLES_PER_PARTITION`, `PI_RANDOM_SEED` (dbt `vars`). Row generation differs between DuckDB and Trino, so `projects/pi/macros/generate_samples.sql` is **adapter-dispatched** (`duckdb__` uses `range()`, `trino__` cross-joins `sequence()` unnests); both draw x/y with `random()` (the seed is carried as a column but engine `random()` is unseeded).

#### Medallion catalogs

Trino and DuckDB both have real catalogs, so each medallion layer is its own catalog. Models set `+database` (catalog) and `+schema` (`example_db`) in `dbt_project.yml`, yielding `<catalog>.example_db.<table>`. The `generate_schema_name` macro (example_db) keeps the schema verbatim instead of the dbt default `<target>_<custom>` concatenation. `pi` has no `generate_schema_name` macro and relies on the profile's `database`/`schema`.

- **homelab (Trino):** the Trino server defines one Iceberg catalog per Apache Polaris catalog — `bronze`, `silver`, `gold`, `test` (used by `pi`). Catalogs are provisioned in Polaris; dbt does not create them.
- **local (DuckDB):** one DuckDB file per catalog (`bronze.duckdb`, …). dbt-duckdb derives the catalog name from the **file basename**, so file names must match catalog names. The example_db local profile attaches `silver`/`gold`; paths come from `DBT_DUCKDB_*` env vars (shared with dlt).

### dlt ingest/export (`workflows/dlt/`)

`src/dlt_runner/__main__.py` (`--pipeline {ingest,export} --project example_db --target {homelab,local}`) dispatches to the project. Project code lives in `projects/example_db/`:

- `projects/example_db/ingest.py` — streams the automotive CSV into `bronze.example_db.automotive_source` (the dbt source). The `direct` naming convention preserves the raw hyphenated column names. homelab writes Iceberg via pyiceberg's REST catalog (`config.configure_iceberg_env` sets `PYICEBERG_CATALOG__<LAYER>__*`), staging parquet in the **temp bucket** (`datahub-local-temp`); local writes DuckDB.
- `projects/example_db/export.py` — reads the dbt-built silver/gold tables (Trino on homelab, DuckDB locally) and loads them to Postgres (homelab) / a DuckDB export file (local).
- `projects/example_db/config.py` — env-driven: catalog→warehouse map, temp bucket, DuckDB paths (reusing the dbt `DBT_DUCKDB_*` vars so a local ingest lands in the files dbt reads), Postgres/Trino DSNs.

### Airflow DAGs and the launchers

**DAGs are one file per project** — each is self-contained and runs as Kubernetes pods:

- `dags/pi_dag.py` (`dag_id: pi`) — pure dbt compute: `dbt_pi`
- `dags/example_db_dag.py` (`dag_id: example_db`) — full medallion project: `dlt_ingest_example_db → dbt_example_db → dlt_export_example_db`

**Task utilities are organised by tool** under `dags/tasks/`:

- `dags/tasks/dbt.py` — `DbtTaskConfig` + `create_dbt_task` (dbt image, `python -m dbt_runner`). The shared `build_pod_env_vars` / `build_pod_resources` and the `SecretEnvVarRef`/`ConfigMapEnvVarRef` dataclasses live here. Pod env is just the explicit env/secret/configmap refs — the pods only need to connect to Trino/Postgres/S3.
- `dags/tasks/dlt.py` — `DltTaskConfig` + `create_dlt_task` (dlt image, `python -m dlt_runner`), reusing the dbt builders.
- Images: `ghcr.io/datahub-local/datahub-local-ai-dbt:main` and `...-dlt:main`.

### n8n workflows

`agents/n8n/` holds no code that runs in this repo — it is the **git mirror of a live n8n instance**. The `Backup N8N Workflows` workflow (`X0gxarZXHgGj5fl5`) reads every workflow through the n8n API and commits it back here, so the repo is a backup *and* the source the workflows read their prompts and configs from at runtime.

```
agents/n8n/
  workflows/   <snake_case_name>.workflow.json   full n8n export, one file per workflow
  prompts/     <domain>_<step>.md                LLM prompt templates with {{ VAR }} placeholders
  datasets/    <domain>_<thing>.json             tuning knobs / reference data, no secrets
```

**File names are generated, not chosen.** `sanitize_filename` in the backup workflow derives the file name from the workflow's display name: camelCase split on the boundary, spaces/dots/dashes → `_`, non-alphanumerics dropped, lowercased, then `.workflow.json`. So `LinkedIn Post Sharing` → `linked_in_post_sharing.workflow.json`. Never rename a file by hand — rename the workflow in n8n and let the backup rewrite it, otherwise the next run creates a second file.

#### Naming conventions inside a workflow

| What | Convention | Examples |
| --- | --- | --- |
| Workflow display name | Title Case with spaces | `Content Feed Curator`, `LinkedIn Post Sharing` |
| Node name | `snake_case`, `<verb>_<object>` | `fetch_miniflux_entries`, `build_digest`, `update_status_error` |
| Manual trigger | always `click_trigger` | |
| Cron trigger | always `schedule_trigger` | |
| Sub-workflow entry point | always `main_trigger` | `executeWorkflowTrigger` |
| Branch nodes | `if_*` / `check_*` / `switch_*` | `if_has_candidates`, `switch_user_accept` |
| Sub-workflow calls | `download_*` / `execute_*` | `download_judge_prompt`, `execute_post_creator` |
| Slack posts | `notify_*` / `send_*_notification` | `notify_digest`, `send_error_notification` |
| Loops | `loop_*` (`splitInBatches`) | `loop_triage_batches` |
| Sub-workflow I/O fields | `UPPER_SNAKE_CASE` | `URL`, `POST_CONTENT`, `MAX_WORDS`, `ERROR` |
| Sticky notes | `sticky_<topic>`, or n8n's default `Sticky Note<n>` | `sticky_overview`, `sticky_testing` |

Node names are the addressing scheme (`$('build_digest').first().json`), so renaming a node silently breaks every expression that references it — grep the file for the old name first.

#### `set_workflow_vars` — the config head of every workflow

Long-running workflows open with a `set` node named `set_workflow_vars` (`includeOtherFields: true`) that resolves every tunable into one item, read downstream as `$('set_workflow_vars').first().json.<NAME>`:

- Field names are `UPPER_SNAKE_CASE`.
- Values that come from the pod environment are `={{ $env["NAME"] }}`, normalised inline where it matters — e.g. `={{ ($env["N8N_API_URL"] || "http://…/api/v1").replace(/\/+$/, "") }}`.
- Model ids live here (`MODEL`, `MODEL_FALLBACK`, `MODEL_BULK`) and are wired to the LLM nodes by expression, so swapping a model is a one-node edit.
- n8n *instance* variables (`$vars`) are deliberately unused — everything is `$env` or a dataset file, so config is reviewable in git.

Env vars in use on the n8n pod: `BACKUP_GITHUB_REPO_OWNER`, `BACKUP_GITHUB_REPO_NAME`, `BACKUP_GITHUB_REPO_PATH` (the repo folder the mirror lives in — `agents/n8n`; it is the **only** place that path is configured, both for the backup commits and for every runtime prompt/dataset fetch), `N8N_API_URL`, `MINIFLUX_URL`, `MINIFLUX_API_USER`, `MINIFLUX_API_PASSWORD`. **Secrets never go in the JSON** — credentials are referenced by n8n credential name only (`Slack account`, `GitHub account`, `OpenRouter account`, …).

#### Prompts and datasets are fetched at runtime, not embedded

No workflow inlines a prompt. `DownloadTemplate` (`qUfjfWLGEjV96ljf` — **not** `09xEuVQj207pjK4x`, which is `Download Content`, a URL scraper taking `{URL}`; a node pointing there returns no `output` and the caller silently falls back to its defaults) is called as a sub-workflow with `{template_name, template_vars}`, pulls `<BACKUP_GITHUB_REPO_PATH>/<template_name>` from GitHub (`agents/n8n/<template_name>`; the prefix is resolved from `$env` in its `setVars` node, never hardcoded, so moving the folder is an env-var change), substitutes `{{ VAR }}` placeholders and returns `{output}`. It **fails loudly** — `check_template_vars_present` diffs the placeholders found in the file against the keys supplied and routes to `stop_and_error` listing the missing ones.

Consequences to respect when editing:

- Adding a `{{ VAR }}` to a prompt without adding it to every caller's `template_vars` breaks that workflow at runtime.
- The substituter matches on the **last dotted segment** of a placeholder, so keep placeholders flat and `UPPER_SNAKE_CASE`.
- Prompt files are `prompts/<domain>_<step>.md` (`linkedin_post_review.md`, `curator_judge.md`); a `*_system.md` file is the system message of a `chainLlm` node.
- The same mechanism loads config: `datasets/curator_config.json`, `datasets/credential_expiry.json` are downloaded as text and parsed by a `parse_*_config` code node that **defaults every key**, so a partial or broken file degrades instead of failing the run. Keep the two in sync when adding a knob.
- Datasets document themselves with sibling `_comment_<key>` keys next to the key they explain. Keep that pattern; there is no schema file.

#### Standard workflow skeleton

```
click_trigger ─┐
schedule_trigger ─┴─> set_workflow_vars -> download_*_config -> parse_*_config
   -> fetch/normalise/filter (code nodes)
   -> if_has_candidates ──false──> notify_empty
              └──true──> loop_* -> download_*_prompt -> *_llm -> parse_* (code)
   -> build_digest -> notify_* -> if_write_* -> googleSheets append/update
```

- Every workflow that can be run by hand has **both** `click_trigger` and `schedule_trigger` wired into the same first node — never a manual-only or schedule-only path.
- Schedules are cron expressions with an explicit `timezone: Europe/Madrid` in workflow settings (`0 0 6 * * 1,3,5`), not interval rules.
- `settings` for a scheduled workflow: `executionOrder: v1`, `callerPolicy: workflowsFromSameOwner`, `executionTimeout`, `errorWorkflow`, `timezone`.

#### Error handling

Three layers, used together:

1. **Instance-wide catch** — `errorWorkflow` points at `Catch Errors` (`fejq5nN6LP3F820w`), a two-node workflow that posts the failing workflow, message and execution URL to `#workflows`. Set it on anything scheduled. A workflow with domain-specific cleanup gets its own error workflow instead (`LinkedIn Post Sharing` → `linked_in_post_sharing_error`, which also writes the failure back to the sheet).
2. **`ERROR` envelope between sub-workflows** — a sub-workflow that fails a business rule returns an item with `ERROR` set to a screaming-snake reason (`CANCELLED`, `MAX_RETRIES_EXCEEDED`) rather than throwing. Callers branch on it with a `check_subworkflow_error` switch testing `{{ $json.ERROR || "" }}` is empty, `fallbackOutput: extra`. Keep new reasons in that vocabulary.
3. **Per-node tolerance** — LLM and flaky HTTP nodes set `retryOnFail` with `maxTries` 2–5 and `waitBetweenTries: 5000`; nodes whose absence is a valid state (`read_legacy_sheet`, the `probe_*` nodes, `download_full_content`) set `onError: continueRegularOutput` + `alwaysOutputData: true` so the downstream code node sees an empty item instead of the run dying.

#### LLM nodes

`chainLlm` + `lmChatOpenRouter` (Gemini in the image workflows). Conventions: `promptType: define` with the text coming from a `download_*_prompt` node; `needsFallback: true` with a second model node named `ai_model_fallback`; a dedicated `ai_model_bulk` for the cheap high-volume step. Model output is always parsed by a following `parse_*` code node that tolerates fenced JSON and bad output rather than trusting the model.

#### Code node conventions

Plain JS, no npm imports. They read named nodes (`$('parse_curator_config').first().json`) rather than relying on positional input, iterate `$input.all()`, and `return [{ json: ... }]`. HTTP from inside a code node uses `this.helpers.httpRequest`. Each non-trivial code node opens with a comment explaining **why** the step exists — several of the current ones record the incident that motivated them; match that when adding one.

#### Editing checklist

1. Prefer editing in the n8n UI and letting `Backup N8N Workflows` commit the export; hand-editing JSON is fine for prompts/datasets and small parameter tweaks, but the export will overwrite structural drift.
2. Keep node `id`s and workflow `id`s stable — they are the identity across re-imports, same rule as Superset `uuid`s.
3. Sticky notes are the docs: each workflow has one describing schedule, data flow, env vars and open TODOs. Update it in the same change.
4. Validate a hand-edited file with `jq . agents/n8n/workflows/<file>.workflow.json` before committing; grep for `$('old_node_name')` after any rename.
5. Commit messages for automated backups look like `chore(n8n): update backup workflow <file> (<date>)`; hand-authored changes use the normal `feat(n8n): …` / `fix(n8n): …` form.

### Sympozium agents

`agents/sympozium/` holds the **agents**; datahub-local-core holds the
**platform**. Core deploys the Sympozium control plane into `automation` along
with the `MCPServer` catalog, the `SkillPack`s and the built-in
`SympoziumPolicy`s. This sub-project only declares `Ensemble`s — teams of
personas — and never re-declares platform objects.

An `Ensemble` is the unit of deployment: installing one stamps out an `Agent` and
a `SympoziumSchedule` per persona and seeds their memory. **Ensembles default to
disabled** in the CRD ("catalog-only"), so a manifest without `enabled: true`
deploys but never runs. The chart's own eight example ensembles are all sitting
in the cluster disabled; ours are separate objects and must not be confused with
them.

```
agents/sympozium/
  Chart.yaml, helmfile.yaml.gotmpl   the sub-project root IS the chart root
  values/default.yaml.gotmpl         per-cluster knobs only
  templates/ensembles.yaml           assembles the Ensembles at render time
  projects/<ensemble>/
    ensemble.yaml       team-level spec + `defaults:` stamped onto each persona
    agents/<persona>.yaml   skills, schedule, MCP servers, tool policy, memory seeds
    prompts/<persona>_{system,task}.md
  scripts/validate.py   field checks the Go templates cannot do
```

#### Conventions

- **Prompts are files, never inlined.** A persona sets `systemPromptFile` and
  `schedule.taskFile`; the build script *rejects* a literal `systemPrompt` or
  `schedule.task`. Same reasoning as `agents/n8n/prompts/`.
- **Nothing is generated into the repository.** `templates/ensembles.yaml` reads
  `projects/` at render time, so the sources are the only copy. Do not reintroduce
  a committed manifest — it is a second copy that silently drifts from its source.
- **Source describes the agent; values describe the cluster.** Only `enabled`,
  `baseURL` and `policyRef` live in `release/values/default.yaml.gotmpl`, merged
  over `spec` at render time. The build script rejects those keys in
  `ensemble.yaml`. Per-persona `model`/`provider`/`runTimeout` come from the
  project's `defaults:` block, because they describe the agent, not the cluster.
- **`toolPolicy` is prefixed, `toolsDeny` is not.** `toolPolicy.allow` uses
  agent-facing names (`k8s_pods_list`) because that is what the model sees;
  `mcpServers[].toolsDeny` uses the server's own names (`pods_delete`) because
  that filter runs at the server. Backwards means a deny that matches nothing.
- **A channel binding is split across source and values, and both halves are
  load-bearing.** The persona carries the type (`channels: [slack]`),
  `send_channel_message` in the allowlist and a `{{ DELIVERY }}` token in its
  system prompt; values carry the credential secret (`channelConfigs`) and the
  `sympozium_delivery` knobs — `channel`, `verbosity` (`quiet|normal|verbose`),
  `notify` (`always|onChange|never`), with per-persona overrides. No CRD field
  carries a destination, so the channel only ever reaches the agent as prompt
  text: the templates substitute exactly `{{ DELIVERY }}`, `{{ CHANNEL }}`,
  `{{ AGENT }}`, `{{ ENSEMBLE }}` and `{{ SCHEDULE }}` and `fail` on any token
  left standing. `{{ DELIVERY }}` expands to three files —
  `prompts/delivery/header.md` (always), the chosen `delivery/<verbosity>.md`,
  and `notify/<level>.md`. Chart-only knobs must stay out of
  `sympozium_ensembles` — the webhook decodes `spec` strictly and rejects an
  unknown key outright. `scripts/validate.py` cross-checks every half. Note the
  binding is *bidirectional* — an inbound Slack message can start an `AgentRun`
  — which is why `homelab-reviewer`, the only ensemble with a write tool, is not
  bound.
- **The binding is what lets a message leave the pod, so delivery cannot be
  unbundled from it.** `send_channel_message` is registered on an *unbound*
  persona too, and it answers normally — a probe run of `renovate-reviewer`
  called it and reported `Succeeded` with `DONE` — but the ipc-bridge then drops
  the message: `Dropping outbound message to channel not configured on this
  agent`. Nothing fails, nothing arrives. Verified 2026-08-23.
- **Every channel sidecar delivers every instance's message, so N delivering
  personas means N copies of every report.** A binding deploys a
  `<persona>-channel-slack` sidecar, and each one subscribes to the fleet-wide
  `sympozium.channel.message.send` with an unfiltered, non-queue-group JetStream
  consumer: it filters on the transport in `data.channel` and never on the
  `metadata.instanceName` the envelope hands it. Five bound personas in
  `homelab-ops` means five sidecars and five byte-identical Slack messages in the
  same second, from one `send_channel_message` call. Nothing scopes that from the
  channel side: unbinding all but one persona silences the rest (previous
  bullet), `channelAccessControl` is inbound-only, the controller exposes only
  fleet-wide `SYMPOZIUM_IMAGE_REGISTRY`/`SYMPOZIUM_IMAGE_TAG`, and the sidecar
  Deployment declares `replicas: 1` under an `Agent` ownerReference. The
  upstream fix is a one-line filter on `metadata.instanceName` in the sidecar,
  which the envelope already carries.
- **`deliveryMode: hook` is the default and how this repo avoids the fan-out
  without waiting for upstream.** The templates stop
  substituting the posting instructions into the prompt and instead attach a
  `lifecycle.postRun` container that posts `AGENT_RESULT` to the Slack API
  directly. It touches no shared subject, so the report arrives exactly once
  regardless of how many personas are bound. Egress works because the hook pod
  carries no `sympozium.ai/role=agent` label and so escapes
  `sympozium-agent-deny-all` — verified against `api.test` from inside the pod.
  Two consequences are the point rather than side effects: the persona must
  **not** allowlist `send_channel_message` (otherwise it posts *and* is posted
  for, and the run ends on a tool call), and the report becomes the model's final
  text — which is what fixes the empty `status.result`, since the dominant cause
  was never invalid UTF-8 but `terminal turn had empty text`, 60 occurrences
  against 2 in one day. A hook posts unconditionally, so `notify` is meaningless
  under it and `scripts/validate.py` rejects both mistakes. Reach for
  `schedule.interval` if a channel gets too busy. `verbosity` is rejected for the
  same reason — hook mode substitutes `prompts/delivery/hook.md` and never reads
  the verbosity files. A persona with no `sympozium_delivery` channel gets no
  hook at all, which is what keeps `homelab-reviewer` silent by design, and
  `hook.md` deliberately names no tool: a 4B model reads a tool name as
  permission to call one. `tool` mode stays expressible and costs a duplicate
  copy per bound persona the moment it is used.
- **`send_channel_message` takes the destination in `chatId`.** Its `channel`
  argument is the *transport* (`slack`, `telegram`, …), never a `#name`. With
  `chatId` unset the tool still answers `Message sent`, targets "owner (self)",
  and on a scheduled run — which has no owner — Slack rejects it as
  `channel_not_found` in the `<persona>-channel-slack` sidecar log, the only
  place a delivery failure is ever visible. This cost every scheduled report for
  two days. Naming the argument was not enough: the prompts showed the call as
  `chatId: "{{ CHANNEL }}"` and a 4B model copied the quotes into the value, so
  Slack rejected the same way for another two days. `prompts/delivery/*.md` now
  write every argument bare, and the validator fails a verbosity file that stops
  mentioning `chatId` *or* puts `{{ CHANNEL }}` back in quotes. A prompt for a
  model this size must never show a value inside syntax the model is also
  expected to strip. Full write-up in `agents/sympozium/README.md`.
- **The report names its agent; it never invents a time.** Nothing in this fleet
  returns the current time (verified — the runtime injects no clock and no MCP
  server exposes one), so the header carries agent, ensemble and cadence, the
  prompts forbid any date or duration not read from a tool result, and Slack's
  message stamp is the run time. An authoritative in-message timestamp needs a
  `lifecycle.postRun` gate hook, which is the CRD's mechanism for rewriting
  agent output.
- **An HTTP endpoint replaces a persona's schedule; it does not add to it.** A
  serving `AgentRun` makes the schedule controller skip every tick for that
  agent — silently, with the `SympoziumSchedule` still `Active` and no run
  failing. So `sympozium_web_endpoint.enabled` is a master switch that stays
  `false` and is flipped on only for the length of a test. It is a values
  decision, never a persona one: the tree appends the `web-endpoint` SkillPack
  at render time, and both the template and the validator reject a persona that
  lists the skill itself, so which agents have a trigger in front of them stays
  readable in one place. It also **drops the persona's `toolPolicy`**: the proxy
  builds its child run from the `Agent` object, whose CRD has no `toolPolicy`
  field, so a web-triggered run of `sre-sentinel` starts with 60 tools instead of
  9 — `write_file` and `execute_command` among them. The read-only guarantee
  holds for scheduled runs, not for HTTP ones. It **truncates the task to its
  first line** too, so anything the `taskFile` said past the opening sentence is
  gone: that is how a web run came to write a full CRITICAL report and deliver
  none of it. Never put a requirement in a field a caller can replace — delivery
  is now a completion condition in `prompts/notify/*.md`, which every run
  carries. Until `toolsAllow` was pinned this
  also broke the endpoint outright: 60 tool schemas overflowed the then-32k
  context, so a web run never read its own system prompt and ended
  `(Agent completed its task via tool calls but did not produce a final text
  summary.)` The window is now 65536, which fixes that overflow; the budget
  argument below stands on its own.
- **Test with a hand-applied `AgentRun`, not the HTTP endpoint.** It suppresses
  no schedule and takes `systemPrompt`, `task` and `toolPolicy` inline, so a
  probe can differ from the real thing. The pod is deleted on completion
  whatever `cleanup` says, so `status.result` and the channel sidecar logs are
  the whole record — plan the probe around reading those. But `status.result` is
  dropped whenever the reply contains invalid UTF-8: the runner ships it to the
  controller over gRPC, protobuf refuses to marshal a bad `string`, and the run
  still reports `Succeeded` with no `error`. Our own header caused it — the model
  was told to echo `·` (U+00B7) verbatim and sometimes emitted a broken byte pair
  — so the delivery prompts are now ASCII-only inside every indented block and
  `scripts/validate.py` enforces it. A model can still corrupt a character on its
  own, so stream `kubectl logs <pod> -c agent -f` rather than reading the object
  afterwards, and never read an empty `result` as a quiet run.
- **`toolsAllow` is the prompt budget; `toolPolicy` is only the permission.**
  `toolPolicy` filters at the LLM request, but every tool the server exposes is
  still *registered* and its schema still injected — a persona allowing nine
  tools logs `tools enabled: 60 tool(s) registered`, because grafana alone
  exposes 66 and the persona only denied 14. At roughly 670 tokens per schema
  that is ~40k of prompt — measured: 40,500 first-call input tokens without
  `toolPolicy` versus 4,095 with it — and it is spent on *every* call in the
  loop, not once. That overflowed the window outright while it was 32,768
  (silently truncated from the front, losing the persona and the report format);
  at 65,536 it merely leaves no headroom for a large Prometheus result and gives
  a 4B model sixty tools to choose between. Every persona therefore pins
  `mcpServers[].toolsAllow` to exactly the tools its `toolPolicy.allow` names,
  unprefixed, and `scripts/validate.py` fails on any drift between the two. The
  `toolsDeny` lists are now redundant by construction and kept only as a record
  of which write names are real; they are not the enforcing mechanism.
- **`toolPolicy.allow` is a strict allowlist.** Omitting a tool disables it, so
  adding a capability means adding the tool name *and* wiring its MCP server on
  that persona. The build script cross-checks the two.
- **Schedules are UTC.** No Sympozium CRD has a timezone field, unlike the n8n
  workflows which set `Europe/Madrid` explicitly. Write cron in UTC with the
  local time in a comment.
- **Every CRD-defaulted field is stated.** `mcpServers[].timeout`,
  `schedule.firstTick`, `memory.maxSizeKB` and `sharedMemory.storageSize` all
  carry a `default:` in the Ensemble CRD, so the API server writes them into the
  live object at admission and ArgoCD reports permanent drift against a manifest
  that omits them. Write the value out even when it *is* the default;
  `scripts/validate.py` enforces the list, and re-derive it after a control-plane
  bump (`kubectl get crd ensembles.sympozium.ai -o json | jq '.. | objects |
  select(has("default"))'`). Note that `kubectl diff` cannot see this class of
  drift — it defaults both sides; diff a `--dry-run=server` apply against the
  rendered manifest instead. Core's ApplicationSet also carries
  `ignoreDifferences` on `memory.maxSizeKB` and `schedule.firstTick`; keep them
  as a backstop for a future default, not as the mechanism.

#### The thinking to carry forward

These are the judgement calls behind the current fleet. Apply the same reasoning
rather than copying the outcomes, since the constraints will change.

- **Verify names against the running system; never infer them.** Every skill,
  MCP server and tool name here was read off the cluster (`kubectl get
  skillpacks`, and a `tools/list` call against each MCP server) because a wrong
  name fails *silently* — the tool simply never appears and the agent produces a
  blander report. Core's own catalog had this bug twice: its k8s server denied
  `delete_resource`/`create_resource`/`update_resource` and its postgres server
  denies `execute_write_query`, and **none of those tool names exist**. The k8s
  half was fixed on 2026-08-23; postgres is still open, and github, argocd and
  grafana carry no catalog denies at all. Personas here re-deny the real names
  themselves, which is the only reason none of it was ever exploitable.
  Re-check after image bumps — every MCP image is pinned `:latest`.
  A whole *server* fails the same silent way: core's `mcp-k8s` was the one
  MCPServer declared `transportType: http`, the discovery bridge asked for the
  service root, and `kubernetes-mcp-server` serves `/mcp` — so it 404'd and every
  `k8s_*` tool was missing from every persona from its creation until
  2026-08-23, with `MCPServer.status.ready` reporting `true` throughout. Read
  `kubectl logs <run-pod> -c mcp-discover` after any transport or image change;
  it prints the per-server tool counts.
- **Split ensembles on trust boundaries, not on subject.** Ensemble-level
  settings apply to every persona inside, so the one agent holding a write tool
  (`renovate-reviewer`, which may only comment) lives in its own ensemble. The
  blast radius is then visible in the directory listing.
- **Breadth comes from more personas, not fatter ones.** A persona carries
  exactly one schedule, so "same agent, different focus on a different day" is
  not expressible — it has to be another persona. When a role grows a second tool
  surface, split it (`db-steward` came out of `service-janitor` for exactly
  that reason) rather than growing the checklist. Keep each run to one question
  and roughly five to seven tools.
- **A correct metric name is not a correct reading.** `sre-sentinel` was told to
  query `kubelet_volume_stats_available_bytes / kubelet_volume_stats_capacity_bytes`
  and flag anything above 80%. Both metrics exist and were verified present — but
  that ratio is the fraction *free*, so it flagged the emptiest volumes and could
  never flag a full one. It called a 2%-used volume "97.9% full, write operations
  failing" on every run for days, and because a non-empty **Filling up** section
  is one of the change conditions, it also forced a Slack post every time. Fill
  expressions now read `100 * (1 - available / capacity)` and carry a
  `group_left` join on `kube_persistentvolumeclaim_info` restricting them to
  `longhorn|longhorn-no-replica`, because all five `nfs` PVCs report the same
  shared 1.9 TB capacity and a per-volume percentage there is meaningless.
  `scripts/validate.py` fails an uninverted division. Give a small model the
  literal expression, not a description of it — it will not assemble a join from
  prose, and it will report whatever it computes with total confidence.
- **Verify the telemetry exists before writing a prompt against it.** Every
  metric named in a prompt was confirmed present in this Prometheus. Two traps
  found this way: Valkey is scraped by a redis exporter so its metrics are
  `redis_*` and never `valkey_*`, and node-exporter's SMART series is
  `smartmon_temperature_celcius` (upstream typo). A small model cannot recover
  from a plausible-but-wrong metric name. Where telemetry is genuinely missing —
  systemd units, OS package updates, Garage/S3 — the prompt must not pretend
  otherwise; record the enabling change instead
  (`agents/sympozium/README.md#follow-ups-to-share-with-the-other-repos`).
- **Seed the noise.** Most alerts in this cluster fire permanently, including
  `KubeSchedulerDown`/`KubeControllerManagerDown`, which are artifacts of k3s
  embedding those components with no separate metrics endpoint. A small model
  cannot deduce that, so the known-chronic set lives in `sre-sentinel`'s memory
  seeds and reports are shaped new / still firing / resolved. Re-seed when the
  chronic set changes.
- **Read-only by default.** Every persona denies `write_file` and
  `execute_command` — the latter is a shell, and with MCP servers wired it is
  also redundant. An agent that changes things should be a separate, explicitly
  authorised one, not a capability quietly added to a reporter.
- **The model constrains the design.** Inference is cluster-local Ollama
  (`qwen3.5:4b`, one 6 GiB GPU, one resident model, a 65,536 context as of
  2026-08-23 — read the effective value from Ollama's `GET /api/ps` with the
  model resident, not from `/api/show`, which reports the architecture ceiling).
  Hence
  `workflowType: autonomous` rather than `delegation` (too small to be trusted
  with `delegate_to_persona`), five-to-eleven-tool allowlists, two skills per
  persona, `runTimeout: 30m` against a 10m default, and staggered schedules with
  `firstTick: afterInterval` so enabling everything does not queue five cold runs
  on one GPU. Prompts name the tools to call in order and end with a required
  section layout and a "no report, no run" rule. Loosen all of this if a hosted
  model is wired in — that is a `baseURL` change plus an `authRefs` secret.
- **`policyRef: permissive` is deliberate.** `restrictive` and
  `network-isolated` both set `networkPolicy.denyAll` with no `allowedEgress`,
  which would cut agents off from Ollama *and* every MCP server; `restrictive`
  also gates tools deny-by-default against a rule list containing only built-in
  names, denying every MCP tool. Restriction is enforced per-persona in
  `projects/`, where it is reviewable, instead.
- **Don't duplicate n8n.** `agents/n8n/workflows/credentials_expiry_review`
  owns n8n credential expiry; `service-janitor` stays strictly cluster-side
  (certificates, tokens, secrets). Check the n8n workflows before giving a
  Sympozium agent a job.

### Test structure

- dbt `tests/` are lightweight: project/profile structure, model SQL, and `dbt parse` — no warehouse. `tests/example_db/test_integration.py` seeds the bronze source in DuckDB, runs `dbt build` **in a subprocess** (avoids DuckDB's per-process "file already attached" conflict), and asserts the medallion tables.
- dlt `tests/example_db/` covers the local DuckDB ingest+export integration test; `tests/test_config.py` covers `projects/example_db/config.py` helpers (cross-project, stays at the tests root).
- airflow `tests/` import the DAGs and check the dbt/dlt task arguments, env, and ordering — `test_pi_dag.py` covers the pi DAG; `test_example_db_dag.py` covers example_db.
- `agents/sympozium/` has no pytest suite — the checks live in `scripts/validate.py` (skills, MCP server names and prefixes, tool/server coherence, schedule enums, prompt references, orphaned prompts, DNS-1123 names) and run in CI via `.github/workflows/test-agents.yaml`, which then renders the chart. Both matter: the validator catches what would fail *silently* at runtime, the render catches what would fail the deploy.
