# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

A monorepo of data workflow definitions for a local/homelab Datahub stack. Sub-projects are grouped by what they are: `agents/` holds AI agent definitions, `workflows/` holds the data pipelines and the dashboards built on them. The Python ones have their own `pyproject.toml` and `uv` environment:

- `agents/n8n/` — n8n workflow JSON exports, LLM prompt templates and JSON config datasets, plus one operational script that pushes export changes back to the live instance; see [n8n workflows](#n8n-workflows)
- `agents/sympozium/` — Sympozium agent ensembles (Kubernetes CRs) plus a Helm release that deploys them onto the control plane datahub-local-core runs in `automation`; also deploys the MCP servers and owns the data they mount (`config/`), though the server code itself lives in [`datahub-local-ai-mcp`](https://github.com/datahub-local/datahub-local-ai-mcp); see [Sympozium agents](#sympozium-agents) and [MCP servers](#mcp-servers)
- `workflows/airflow/` — Airflow DAGs that orchestrate the dlt + dbt tasks via Kubernetes pods
- `workflows/dbt/` — dbt Core pipelines on **Trino** (homelab) / **DuckDB** (local), Iceberg + Apache Polaris, medallion architecture; a thin Python `dbt_runner` wraps `dbt build`
- `workflows/dlt/` — [dlt](https://dlthub.com) ingest/export pipelines (CSV → bronze; silver/gold → Postgres) that run *around* dbt
- `workflows/superset/` — Superset dashboard export bundles per project (`workflows/superset/projects/<name>/dashboard_export/` YAML) plus a Helm release (`workflows/superset/release/`) that ships them as ConfigMaps labeled `superset_dashboard=1` for the dashboard sidecar in datahub-local-core. After editing YAML: `python3 workflows/superset/scripts/build_bundles.py` rebuilds the zips under `release/files/` — the build refuses a dataset that reads bronze, and the archive is deterministic in contents and timestamps but not byte-for-byte across interpreters, because the deflate stream is the building zlib's — then `helmfile apply` from `workflows/superset/release/` deploys them. Object `uuid`s are the stable identity across re-imports — never regenerate them once deployed.

## AI prompt policy

This applies to **every** prompt in this repository, including n8n templates,
Sympozium persona prompts, and any future AI workflow. Prompts must be short,
literal, and action-oriented — like a compact GitHub/Copilot prompt. State the
job, required inputs or tools, bounded steps, no-result behavior, and required
output. Put deterministic logic in code and durable rationale in documentation;
do not turn prompts into tutorials, copied schemas, or background essays.

**Every instruction a model reads is declared in a prompt file or the authoring
brief.** In n8n that is `agents/n8n/prompts/*.md`, fetched by `DownloadTemplate`
with its placeholders filled; in Sympozium it is `systemPromptFile` /
`schedule.taskFile`. The brief (megaprompt) is assembled in a Code node from those
files plus values, and may own selection and formatting — never a rule, a
definition or an example that exists nowhere else. An inline instruction in a Code
node, a model node's `text`, an HTTP body or a tool description is a gap: the model
reads it and a reviewer does not, and editing the prompt file cannot fix it. A
definition the model must follow — what a scene is, what a form means — is written
where the model reads it, never inferred from a count or a field name.
`agents/n8n/scripts/test_prompt_sources.py` fails a new inline prompt unless it is
recorded in its allowlist with a reason.

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

### n8n workflows

`agents/n8n/` is a **backup, not a source.** The `Backup N8N Workflows` flow
reads the live instance and writes here — core points `BACKUP_GITHUB_REPO_*` at
this path — and nothing reads the other way. So editing a `*.workflow.json`
changes nothing in the cluster, and the next backup run overwrites the file and
commits the revert.

The one time an export edit is legitimate is *alongside* the live apply below,
so the change is reviewable in a commit now instead of whenever the backup next
runs. Write the same value live and in the file, and match the API's key order
so the next backup regenerates the same bytes rather than a reformat — read the
order off the live node (`executeOnce` sits between `typeVersion` and
`alwaysOutputData`, not where a hand edit would put it). An export edit with no
live apply behind it is still a revert waiting to happen.

**Every workflow must have error handling before it is considered done.** A new
or edited workflow is not finished until its failure path is wired: an entry
point carries `settings.errorWorkflow`, a sub-workflow raises so its parent
reports, and no node swallows a failure that nothing downstream handles. This is
a hard requirement, not a preference — a workflow without it fails completely
silently. n8n logs no line for a failed execution (verified: a Loki query across
every n8n pod for 7 days matches nothing at `log_level: info`), so an unwired
failure is invisible in Slack, in the logs and in Prometheus at once. Thirteen of
fifteen workflows were in that state, for months.

`test_workflow_invariants.py` enforces the mechanical half of the rule, so the wiring is no
longer review-only: an entry point (a schedule, webhook or form trigger) must set
`settings.errorWorkflow`, a workflow that only a parent workflow calls must leave it unset — or
one failure posts twice — an error handler must set none, and the target must be a workflow in
the repository, must be **active**, and must itself carry an error trigger. What remains review
is the judgement the triggers cannot see: whether a workflow belongs in the category its triggers
put it in, and what a manual-only workflow's failures are worth, since n8n does not invoke an
error workflow for a manual execution. When adding a workflow, state in the PR which of the three
categories it is and how its failure surfaces.

**A workflow edit is not done until it is tidy.** Two halves, and only the first is
automatable. `agents/n8n/scripts/test_workflow_invariants.py` holds the objective part,
parametrized over every export: both copies of the graph agree, node names are unique and
non-empty, no node is left with no connection in either direction, no two nodes share a
position, every literal `$('node')` reference resolves, every literal
`executeWorkflow`/`errorWorkflow` target is a workflow the repository has, and no `main`
edge lands on an input index the target node does not have. Each of those has bitten: a
rename left `file_webhook`'s 404 branch reading `$('Set Vars1')` for months,
a graph edit left the LinkedIn image approval's rejection edge dangling, and
`if_raster`'s never-authored output was wired to a one-input `noOp` at index 2
(`visual_studio`, found 2026-10-15) — n8n pads the inputs a node was not given with `[]`,
so that node ran, read input 0, found nothing and emitted nothing, which took the whole
chain with it: `merge_branches` never fired, `set_result` never ran, the studio answered
with no items at all, and the caller's run ended `success` with no fallback and no error.
An edge onto an input that does not exist is silent in every direction. The
judgement half is yours: node names that read the same way as their neighbours, grouping
and stickies, and spacing in the editor — a fixed box size would fail a legitimate layout,
so only exact-duplicate positions are an error. Tidy the export *and* the live instance:
apply, read back, and diff (above), because a tidy export that nothing applied is a tidy
file and an untidy graph.

**Always ask before applying workflow changes to the live instance.** Editing
the JSON here is cheap and reviewable; writing it back is not. `PUT
/api/v1/workflows/{id}` replaces the nodes and connections of a running
automation that may be mid-execution, it carries no `active` field so a trigger
can come back deactivated, and the export in git may be older than the live
version. Show the diff, ask, and only then apply — reading each workflow live
and writing back the changed fields, never posting a whole exported body.

`scripts/apply_workflow_changes.py` is that apply step, and the reason it
exists is the same one `reseed_memory.py` exists for in `agents/sympozium/`: a
source edit that nothing reconciles is not done when it is merged. It reads each
workflow live, sets only the named fields, prints the plan, and writes on
`--apply` and not before. `--print-pod-overrides` emits its own pod spec with
the key wired from the secret, so the payload can never drift from the file
being run.

It is deliberately **generic — do not write a second one.** A change is
`--set 'node:field=value'` (dotted paths reach into `parameters`),
`--set-setting 'field=value'` for `settings.errorWorkflow` and its neighbours,
and `--changes file.json` for a batch across many workflows. `--workflow` takes
an id or an exact name. It re-reads after the PUT to confirm each field landed,
and re-activates the workflow if `active` flipped, since the PUT carries no
`active` field.

`--create file.json` is the one documented exception to "never post a whole
exported body": a workflow that does not exist yet cannot be edited, and an
export edit with no create behind it is a revert waiting for the next backup. It
POSTs the body once, keyed by name, writes by default (`--dry-run` prints the
plan), prints the new id, and leaves an existing same-named workflow untouched so
a re-run after a partial apply is safe. Only `name`/`nodes`/`connections`/
`settings` are read from the body. Everything after creation goes back through
the field-level path. Two mechanical notes for running it: the pod has no copy of
the script or the export, so `kubectl cp` them in (an `exec -i` stdin stream
drops past ~8 KB, which silently truncates a `--changes` file), and the pod dies
on `sleep` — recreate it rather than trusting an existing `n8n-apply`.

**A probe workflow created active cannot be deleted until it is deactivated**, and
the refusal names the reason: `DELETE /api/v1/workflows/{id}` answers `409 Cannot
delete a published workflow. Unpublish it before deleting.` — `POST
/api/v1/workflows/{id}/deactivate`, then `DELETE`, then read the id back to
confirm it is gone. Measured 2026-10-16 deleting a temporary read probe, and the
first attempt left it live because the delete was the only step that failed.
Measured again 2026-10-18 on the article probe: the `deactivate` answered `200` and
the `DELETE` immediately after **still** answered `409` while the object already read
`active: false, activeVersionId: null` — the retry a second later answered `200` and
the read-back `404`. So treat the pair as "deactivate, delete, retry the delete",
not as one attempt each.

**The public API cannot fire a manual trigger.** `POST
/api/v1/workflows/{id}/test-runs` is the *evaluation* runner ("The workflow must
contain a configured evaluation trigger") and there is no execute endpoint, so a
workflow whose only triggers are a `manualTrigger` and a `scheduleTrigger` is
started from the UI or by a temporary webhook workflow that calls it with
`executeWorkflow` — the shape every live verification here has used. The full
public API surface is readable from the running instance:
`GET /api/v1/openapi.yml` (YAML, ~870 KB).

**The API accepts no `settings.binaryMode`, on `POST` or on `PUT`** — the field is
UI-only, so a create body copied from an export that carries it lands without it,
and `--set-setting binaryMode=separate` reports `MISMATCH` because the value is
read back from the response. Measured 2026-10-15 on `Article Creator`: `POST`
stored `{executionOrder, callerPolicy, timeSavedMode, availableInMCP}` from a body
naming five, and the `PUT` that followed changed nothing. The `Visual Studio` and
`LinkedIn Post Creator` exports carry it because both were edited in the UI; a
workflow created through the API does not, and a create body should leave it out
rather than promise a setting the API will drop.

**An API-created Google Sheets write node needs `columns.schema`, which the UI
supplies and the API does not.** With `mappingMode: defineBelow` and a `value`
map, the node throws `columns.schema is required when columns.mappingMode is
defineBelow` before writing anything. `Content Board Curator` failed its first
two scheduled runs on exactly that (14174 and 14322, the latter caught by the
error workflow), so `append_article_queue` had never written a row. Build the
schema from the sheet header — every column, `removed: false` only for the ones
an update writes, plus `row_number` (`readOnly`; `removed: true` on append) —
and `test_content_board_curator.py` now fails on a write node without one.

**The UI is a writer the API cannot mirror, so the nightly backup is the only
reconciler.** Two directions, both measured on the 2026-10-17 backup, which
rewrote eight exports after the workflows were opened in the editor:

- **The UI drops a parameter that holds its default.** `search_hn`/`search_feeds`
  lost `method: "GET"` and `Article Creator`'s two `toolWorkflow` nodes lost
  `source: "database"` and `options: {}`. Nothing changed behaviour — those are the
  defaults — but an offline test that asserts the *field* fails while the node is
  correct, which is how `test_content_research.py` broke. Assert the effective
  value (`search.get("method", "GET") == "GET"`), not its presence.
- **The UI adds `settings.binaryMode`**, which no API write can produce or remove
  (above). A workflow edited in the editor therefore reads as drift against its
  export until the next backup, and `--set-setting` cannot close it.

So an export is the backup's output, not a body to be hand-edited back: after a
UI session the export is behind live until 02:00, and a test that pins a
UI-owned field pins something the editor may rewrite at any time.

Pair every change with `--require-edge 'src>dst'`. A change is argued from the
graph — "these two nodes sit downstream of a per-item stream" — and the graph
is exactly what may have moved since; a mismatch aborts before writing. This is
not hypothetical: the fan-out below was reasoned about correctly in a node
`notes` string that had been false in every committed version of the export.

The API is reachable **in-cluster only**: the public host routes `/api/` through
oauth2-proxy, which an API key does not satisfy. The key is
`security/n8n-root` → `N8N_API_KEY`; mount it into a pod rather than reading it
into a shell.

Eight structural things worth knowing before editing an export:

- **Every export carries its nodes twice**, at the top level and inside
  `activeVersion`. Edit both or the file is self-inconsistent.
- **`settings.errorWorkflow` is per workflow and there is no instance-wide
  default** — verified against `@n8n/config` in the running image, no such env
  var exists. A workflow without it fails silently. The target must also be
  **active**: n8n logs `Calling Error Workflow for "<wf>". Workflow "<id>" is not
  active and cannot be executed` and the failure goes unreported (hit 2026-09-28,
  Visual Studio's error path, which looked wired and did nothing until the handler
  was activated).
- **n8n does not invoke `settings.errorWorkflow` for a manual execution**, so a manual
  test that fails is silent — no notice, no row update, and nothing in the logs at info
  level. Read off the running image: `execution-lifecycle-hooks.js` guards the call with
  `if (!isManualMode && !suppressErrorWorkflow && fullRunData.status !== 'success' && …)`,
  and `isManualMode` is `this.mode === 'manual'`. The consequence is measurable:
  `Article Content Writer Error` (`33uWLrAzZMm4SOP8`) is active, is named by the entry
  point's `settings.errorWorkflow`, and has **never** run — because every entry-point
  execution so far has been started from the editor. A failure path is therefore only
  exercised by a *triggered* run: drive one through a temporary webhook probe, and read
  the execution list rather than waiting for Slack.
- **Entry points notify, sub-workflows raise.** A workflow a schedule, webhook
  or form starts sets `errorWorkflow`, because nothing upstream could report for
  it. A workflow only ever called by a parent leaves it unset, so the error
  propagates and the parent reports once with its own context; setting it on both
  notifies twice for one failure. An error handler never sets it — it would
  trigger itself. Derive which is which from the `executeWorkflow` call graph,
  not from the trigger nodes present: two workflows here carry an
  `executeWorkflowTrigger` that nothing calls.
- **`onError: continueRegularOutput` makes a failure invisible to every alerting
  path** — the execution reports success, no error workflow fires, and the
  Prometheus histogram records `status="success"`. Use it only where a downstream
  node actually handles the empty result, and say where in a node `notes`.
  Worse for anyone branching on it: for a non-AI node n8n does **not** add
  `json.error` — it forwards the node's *input* unchanged
  (`workflow-execute.js`, `handleNodeExecutionError`, `nodeSuccessData =
  [executionData.data.main[0]]`), so an `IF` on `!($json.error)` takes the
  success branch on failure. Branch on a marker only the success path sets, or
  have the node report the failure as data (`ExecuteCommand` and the Puppeteer
  node handle `continueOnFail` themselves and *do* set `json.error`; the puppeteer
  script's own `catch` is the reliable place). Hit 2026-09-28. Note the mode: that
  is `continueRegularOutput`, which forwards the input. **`continueErrorOutput` is
  the opposite** — it puts the failure on a second output with `json.error` set
  (`{message, name, stack}`, measured with a probe 2026-10-18), which is the mode
  to use when a thrown failure has to be reported.
- **A node past `typeVersion` 4.1 re-runs its operation once per input item**,
  so a read node's cost is the size of the stream reaching it, not one call.
  (Sheets is explicit about it: `read.operation.ts` does `let length = 1; if
  (nodeVersion > 4.1) length = items.length;`.) Two chained Sheets reads on the
  Content Feed Curator's per-candidate stream therefore issued N and then N×L
  `spreadsheets.values.get` calls against a 60/min quota, and failed every run
  with a non-trivial candidate pool. `executeOnce` on each is the fix and takes
  it to two calls; reordering does not, because the second read still fans out
  over the first one's rows. It was safe to set because the consumer pulls both
  tabs with `$('node').all()` rather than consuming the stream — check that
  before setting it, or the change is a correctness bug rather than a saving.
  The same trap hit `Content Board Curator` on 2026-10-19: four open issues made
  a 198-row `article_queue` read come back as 792 items (execution 14349), and
  `executeOnce` on `read_article_queue` took it to 202. Its dedupe used a Set, so
  no duplicate row was appended, but the ceiling saw every stale row four times.
  Note this bug is invisible in the export: nothing records a node's effective
  input cardinality, so it is read off the connection graph or not at all. A
  node `notes` claiming otherwise is the same second-copy-of-a-decision problem
  as a comment beside a value, and drifted the same way.
- **A sub-workflow's response is its last node's *last run*, so a caller cannot receive two
  branches' items from one call.** `Visual Studio` answers with one item per asset branch —
  `merge_branches` is a Merge v3 whose append mode runs once per arriving branch, so `set_result`
  runs per branch and each item's `ASSETS` holds one asset. Two of them exist in the studio's own
  execution, and the caller sees **one**: the other branch's item never leaves the sub-workflow.
  Measured 2026-10-17 on the article flow — the studio authored and rendered both assets
  (execution 13722, `svg_wide` stored at `visual-studio/13722-svg_wide.svg`) while the caller
  received a single asset (execution 13720) and the publish gate reported `svg_wide=MISSING`. The
  fix is one call per type (`split_pending_types` in the article flow fans the pending set out to
  one item per type, and the studio call reads `$json.ASSET_TYPE`), not a caller that reads more
  items: there is nothing more to read. A Merge cannot express the join either — append runs per
  input and `combine` merges fields rather than listing items — so a multi-type caller is a
  per-type caller.
- **An agent's tool node must implement `execute`, and the obvious node does not.** n8n's v3
  agent hands a tool call to the workflow engine, which runs the node through its own executor,
  so a tool node carrying only `supplyData` fails on **every** call with `The node
  "@n8n/n8n-nodes-langchain.toolHttpRequest" has a "supplyData" method but no "execute" method.`
  — while connecting cleanly, publishing cleanly and appearing in the editor's own catalog. Hit
  2026-10-16 in `Article Creator`: two `toolHttpRequest` tools were wired, the model did call
  them (`search_web` ×2, `check_feeds` ×1), every call died, the agent's final text came back
  empty and the draft returned `EMPTY_DRAFT` — and the failure is invisible in the export, which
  shows a connected tool. Read the usable set off the image, not the catalog:
  `grep -L "async execute" .../n8n-nodes-langchain/dist/nodes/tools/*/*.node.js` lists the ones
  that cannot run. `toolWorkflow` (v2), `toolWikipedia`, `toolSearXng`, `toolSerpApi`,
  `toolCode`, `toolThink` and `toolVectorStore` implement both. It is also the reason an HTTP
  lookup belongs in a workflow called as a tool, which additionally hands the model a shaped
  result instead of a raw API payload. `test_workflow_invariants.py` now asserts the type of
  every `ai_tool` source in every export, so the next one fails offline rather than at the model.
- **A rule the gate enforces must be satisfiable by the rules the drafter
  follows.** `LinkedIn Post Creator` drafts text and then reviews it in the same
  execution against `linkedin_post_rules.md` *plus* the row's `EXTRA_PROMPT`,
  retrying a rejection from scratch. On 2026-09-30 that made one article
  unpublishable: row 58 is about an agent *harness*, `harness` was on the banned
  AI-speak list, and the drafting rules at the same time require naming the
  technology from the source — so no draft could satisfy both, and five drafts
  ended in `MAX_RETRIES_EXCEEDED` (execution 11728, via 11726). The same word had
  been accepted days earlier with 7 and 8 uses (executions 11311, 11317), so the
  gate's verdict on a legitimate technical term was a coin flip. A banned-word
  list must ban a word in its *hype* usage and allow it where it names the
  subject; that rule lives in **two** files that have to change together —
  `prompts/linkedin_post_rules.md` for the drafter,
  `prompts/linkedin_post_review.md` for the gate — and a retry carries the gate's
  own `<explanation>` into the next prompt so a rejection for the same reason
  cannot repeat. Both are prompt files, read from GitHub `main` by
  `DownloadTemplate`, so this class of fix is live on push; a node change is not,
  which is how the export half of that fix was reverted by the nightly backup
  before it had been applied.
- **The subject owns the judgment; the source owns the work.** `LinkedIn Post
  Creator` is handed a third-party article and told to write from the poster's
  expertise, so a first fix that only asked it to *name* the company failed: on
  2026-10-12 a Spotify engineering post still drafted as "I built two [Portal]
  AiKA Modes" and "a Java monorepo I was working in", with Spotify named in the
  same paragraph (execution 13154, row 71). Naming a product and claiming its
  work are independent, and three other rules push the other way — L5 "from your
  own experience", L14 "confident because you build these systems daily", L35
  "whatever the post presents as experience belongs to that subject" — so the
  split has to be stated in those rules and not only in the attribution one. The
  pair is `prompts/linkedin_post_rules.md` (drafter) and
  `prompts/linkedin_post_review.md` (gate), live on push. The composer is not
  affected: it is briefed with the post text and renders it impersonally, which
  is why the video can read truer than the post it came from.
- **A `PUT` edits the draft; only publishing changes what runs, and publishing
  validates every node.** Adding the animated-media branch left live's top-level
  graph at 40 nodes while `activeVersion` still held 29 — the schedule would have
  kept running the old graph, and the backup would have committed that asymmetry,
  which the "nodes twice" rule above and the tests that read both copies then
  fail on. Publishing a draft takes a deactivate/activate cycle (`POST /activate`
  on an already-active workflow is a 400), and activation re-validates the graph:
  with four new Slack nodes missing `credentials.slackApi` it answered `Cannot
  publish workflow: 4 nodes have configuration issues`, and the workflow was left
  **deactivated** — so an activation attempt on a live workflow is an outage until
  it succeeds. Hit 2026-10-02: cloning a node's parameters is not cloning the
  node, and the tests caught that only after the fix was written. So after any
  apply that adds or removes nodes: re-read `activeVersion`, re-activate, confirm
  `active`, and diff the export against live afterwards.

- **An export's `jsCode` is a string, so a line break in the file is `\n` and a `\n` inside a JS string is `\\n` — write the pair where the single belongs and the node is a syntax error.** Nothing offline catches it: the JSON is still valid, the diff still reads as two lines, and every textual assertion still passes. n8n parses the node only when a run reaches it, so the whole node fails for every run, and the apply ships it silently. Hit on 2026-10-16 adding the still-type branch to `build_author_brief`: `\n` landed between `stillPlanLine` and `stillSceneLine`, live took it, and every agent-authored asset would have failed. `agents/n8n/scripts/test_code_nodes_parse.py` now parses every Code node with `node --check` inside an async wrapper (a top-level `return` is legal there and illegal in a plain script), and the `agents/n8n` CI job installs node for it. Check a jsCode edit by executing it, not by reading it.

- **Every model node waits 120 s, because the gateway's failover outlasts the client's default.** `lmChatOpenAi`'s `options.timeout` defaults to **60000 ms** (`LmChatOpenAi.node.js`, applied both to the undici dispatcher and to the LangChain client), and the gateway is LiteLLM with a fallback chain: a primary that stalls is not a failed call, because the gateway waits on it and then fails over, so the client has to outlast the whole failover or it abandons the call during it and reports a timeout the gateway never made. Hit 2026-10-18: `check_article_llm` answered `litellm.Timeout: Timeout passed=30.0` and the run died with the failover still in flight. All twelve model nodes in this repository now set `options.timeout: 120000`, swept by `agents/n8n/scripts/test_model_timeouts.py` over every export's both copies — a per-file assertion would be one copy of the rule per workflow and a new workflow would be silently exempt. Neither the credential nor the instance carries a timeout, so it lives on each node. Note the node's own `maxRetries` multiplies with it (5 × 120 s is twelve minutes for one hung node), and the gateway's per-attempt timeout is a `datahub-local-core` LiteLLM setting — the tighter of the two, and not in this repository.

#### Visual Studio

One workflow turns a source text into visual assets, driven by the type registry
`agents/n8n/datasets/visual_types.json`. Adding a type is a change to that file, not a
branch in the graph. Eleven types: `image` (authored by the Gemini image model, png),
`image_wide` (the same raster at 16:9), `animation` (authored by the composer agent, mp4),
`animation_linkedin` (authored by the composer agent, gif, inside LinkedIn's GIF cap),
`animation_linkedin_video` (authored by the composer agent, mp4, at the feed's 4:5 aspect),
`tiles` (authored by the composer agent, a looping tiled pattern drawn by a seeded walk, mp4
at the feed's aspect; a pattern is not a sequence, so it declares no per-scene floor),
`tiles_wide` (the same loop at 16:9), `svg` (authored by the composer agent, a self-contained
animated SVG), `svg_wide` (the same
animated SVG at 16:9), `deck` (authored by the composer agent, a self-contained HTML
presentation that the same run also renders to mp4) and `launch_card` (authored by the
composer agent, a still png at the announcement frame). A type declares its `brandKind`
(`diagrammatic` or `photographic`), its output format and the frame the composer is briefed
to produce, and it may declare the `form` it means — the studio honours a type's form ahead
of the caller's `FORCE`, because choosing the type is choosing its shape (`svg_wide` is the
article's diagram, so it pins `diagram`; a type that declares none takes the caller's
`FORCE`, and with neither the composer chooses). No animated type declares a `holdSeconds`,
because a frozen final frame is the cheap-motion tell the framework names, and a still type
declares no clip at all — no `durationSeconds`, no `secondsPerScene`.

**The frame is the type's data, in both halves of the raster branch.** `aspect` is what the
composer is briefed to author, and for a raster it must also reach the image request and the
prompt that directs it — it did neither until 2026-10-17: `generate_image` hardcoded
`aspect_ratio: "4:5"` and the director, told nothing, invented "landscape 3:2" for a type
declaring 16:9, so the model composed one shape and the API cropped it to another. Now
`aspect_ratio` is `$('if_raster').all()[$itemIndex].json.ASPECT` (the chain node emits only
`{text}`, so the item's own field is not reachable from `$json` and `$itemIndex` is the
pairing), and `download_raster_prompt` passes `ASPECT` to `prompts/visual_raster.md`, which
composes to it. A caller that wants a different frame picks a type; the wide pair exists
because an article is read on a screen and the LinkedIn types are 4:5 for their feed.

**An artifact's container is the type's, and the runtime conforms it after the render.** A
type declares `aspect`, `budget.viewport`, `durationSeconds` and `frames`; the composer's brief
states them and nothing made the delivered file match them — measured on run 13762
(2026-10-17), a `tiles_wide` request for 16:9 / 1280 / 12 s / 360 frames came back as
`ffprobe` **1080×1350, 30 fps, 90 frames, 3.000 s** while the record's `WIDTH 1280` /
`HEIGHT 720` / `FRAME_COUNT 360` / `DURATION_MS 12000` asserted the request, so the record
described a file nobody had. `hyperframes render` has **no viewport or size flag** (v0.8.158),
so the composition's own `data-width` is the frame and a wrong one can only be conformed
afterwards. The session therefore probes the engine's output with `ffprobe` and, when the
frame, rate or length differ, re-encodes **before** the stills — `scale=W:H:force_original_aspect_ratio=increase`
then `crop=W:H`, because a declared frame means *filled* and an aspect mismatch is covered and
cropped rather than letterboxed, and `-t <declared seconds>`, which trims and never extends: a
held last frame is the frozen tail the motion rules forbid, so a short render is delivered short
and reported. `mp4` used to return `null` from `transcodeArgs` — the one kind every video type
uses was the one kind never conformed. The note rides back on the response and onto the asset
(`CONFORMED`, `AUTHORED_FRAME`, `SHORT`), so `WIDTH`/`HEIGHT`/`FRAME_COUNT`/`DURATION_MS`
describe the declared container *because the artifact now is it*, and a drift is readable from
the record instead of hidden inside the bytes. A render that already matches pays no second
encode, and a conformance that cannot run is a note with `fit: unknown` rather than a lost
asset.

**A render is looked at before a human is asked to look at it, and the workflow does the
looking.** `Visual Studio` runs a bounded self-review after the authoring turn. The session
hands back stills of what it rendered — `stills: [...]` in the response, made with the tools the
render already uses (Chromium for an SVG or a deck, `ffmpeg` frames for a clip, the final frame
always, since "nothing fully stops" means a frozen clip hides there) — and serves them beside
the artifact, because the artifact is in the pod and the gateway cannot reach the pod's route.
The workflow fetches them, asks a **different** vision model on the gateway
(`opencode-go/glm-5.3-flash`, reusing `generate_image`'s bearer credential) with
`prompts/visual_review_composition.md` and the brief the composer was given, and on findings
takes another authoring turn **in the same session** with them as the reviewer's correction,
bounded by `REVIEW_CYCLES` (2). **The critic's call is the workflow's, never the adapter's**: the
agent renders and reports what it rendered, and deciding whether that is good is orchestration —
an API call inside the adapter was the first shape and was rejected for putting a model
dependency and an opinion inside the agent. The verdict is data (`VERDICT`, `RETRY`, and a
`REVIEW` that rides on the asset), a still that cannot be made or a prompt that is missing
records the review as not run rather than failing the asset, and an unreadable verdict is a pass
with the raw answer kept — the other direction spends every cycle and ships the same defect.
What it cannot see is motion, which the framework's `check` gate owns, and the stills' bytes are
the only bytes the review adds to the graph. **A critique is expensive and slow**: four stills took
102 s on the first live call (2026-10-17), so the critic's node allows 300 s and — this matters more
— carries `onError: continueRegularOutput`, because a critic that cannot answer must not fail the
run it was checking. The first live review proved the cost of not having that: its second call hit a
120 s node timeout, the authoring run errored, and an asset that had already been fixed once died
with it (execution 13762). One asset with one fix cycle is ≈ 18 minutes against ≈ 8 without. **A still of an animated
document must be captured after its entrances run**: Chromium screenshots an SVG at t=0, so the
first live review's finding was "no diagram content is visible" on a frame no reader ever sees
(execution 13770), and a fix cycle went on it. `--virtual-time-budget` advances the page's clock
before the capture and costs no wall time — measured against a page whose content appears after 3 s:
3,886 bytes at t=0, 8,011 with the budget — so an animated SVG gets the declared duration's offsets
plus its settled frame, and a deck (whose page is not a timeline) one settled shot. The clip case
was already right: `ffmpeg` frames plus the final one.

**A correction turn keeps the container the request declared, and a still is of the turn it
judges.** Both came out of run 13785 (2026-10-17), a `tiles_wide` request whose registry entry
says 16:9 / viewport 1280 / 12 s / 360 frames / 30 fps. The review loop's items are built from
the asset (`agent_result` → `prepare_stills` → `parse_verdict` → `review_feedback`), and the asset
carried none of `ASPECT`/`VIEWPORT`/`FRAMES`/`DURATION_SECONDS`, so `build_author_brief`'s four
silent defaults fired at once and **both** correction turns were asked for 1080×1350 / 3 s / 24
frames / 8 fps. The composer authored what it was told and the conformance delivered it exactly
(rate resampled 30 → 8) — so the critic, handed that degraded brief, named the *correct* 16:9
composition as the defect, and because an asset's object key is per run and per type
(`visual-studio/<run>-<type>.mp4`) turn 0's right artifact was overwritten as well. The
declaration now rides on the asset beside what was delivered (`WIDTH`/`HEIGHT`/`FRAME_COUNT`/
`DURATION_MS`), and `build_author_brief` refuses an item that carries none, naming the missing
field, because a plausible default is indistinguishable from the caller's request once the run
has produced an artifact; `parse_registry` completes the container for a type that declares no
length (the launch card) from its own budget, so every real type satisfies that requirement. The
raster half never had this defect: its frame comes from `if_raster`, not from the item in hand.
Separately, the settled-frame still is sought at one frame interval of the **served** rate (the
conformance's declared rate, not the `ffprobe` taken before it), and a capture counts as a still
only when it wrote bytes: at 8 fps the old fixed `-sseof -0.1` exited 0 and wrote nothing, so
turns 1 and 2 both reported four stills and served turn 0's `review-final.jpg` under that name
while the review prompt tells the critic to judge geometry on the last still. A still that was
not produced is now removed-first and absent from `stills`, so the review judges one frame fewer
rather than the wrong turn's frame, and never fails the asset.

**Authoring is one composer turn.** For an agent type the request's `CONTENT` is a brief
sent to the `pi-render` session, which plans a **storyboard** (form, style, scenes) and
then authors a HyperFrames composition and renders it, in the same turn. The workflow
never sees the composition markup, only the rendered file; the composer's own report is
kept on the asset as `STORYBOARD` in the run record, so a bad visual is diagnosable.
There is no typed content spec and no markup template: the old `spec_markup`/`spec_raster`/
`spec_service` branches, the browser frame capture and the render service are all gone.
The `image` type stays on Gemini — a different medium, not a fallback for an animation.
A `deck` run returns two assets from that one turn: the deck (`out.html`) and its paired
video (`out.mp4`), fetched by `fetch_paired_artifact` and emitted as `deck` +
`deck_video`.

**A still is the render's last frame, and that is measured, not assumed.** `launch_card`
is the one agent-authored raster, and its artifact is the **final** frame of the
composition the composer renders: the session's `png` transcode is
`ffmpeg -sseof -0.1 -frames:v 1` (`agents/adapters/pi-render/session-lib.mjs`,
`transcodeArgs`). It was the *first* frame until the type's first live run, which is
exactly the trap: an authored composition animates its subjects in, so frame 1 of the
real card (run 13581) was **4,107 bytes and exactly one colour** — a blank page — while
its final frame was **251,865 bytes and 12,257 colours** with content in every row band.
No brief wording fixes that reliably: the framework's motion rules ask for entrances and
a model will write them, so the artifact must not depend on the composer's timing. The
still brief therefore names the final frame and forbids only what would break it —
nothing may leave, dim or hide before the end — and the animated branch is not used for a
`png` type at all. A `SCENES` count on the still type becomes the card's parts within the
one frame rather than a sequence. So the studio holds two different stills and they are
not the same medium: `image` is Gemini's raster, `launch_card` is a frame the composer
composed. `openspec/changes/archive/2026-10-16-add-launch-card-type/` is the record.

**When a launch card, and when something else.** A launch card announces **a thing we
ship** — a product, a feature, an integration, a release — and it is the one visual whose
subject is our own work rather than someone else's article. Its form, `launch`, is the
only place the card's parts are defined: one brand lockup, one status badge, a headline
with its supporting line, the feature set as a few short chips, a window of the product's
own interface with the working part accented, and one call to action. Reach for it when
the reader's next act is to click, download or try. Everything else is one of the other
types: an `image` when the visual is *about an article* — an infographic of its facts, or
an art-directed photographic frame, never exact lettering or an interface, both of which
`prompts/visual_raster.md` forbids outright — an `animation` or `animation_linkedin_video`
when the idea needs time (a sequence, a flow, a build-up), `animation_linkedin` for the
same thing as a looping image inside the platform's pixel cap, `svg` for something small,
sharp and vector, and `deck` when the argument has chapters. No hook defaults to `launch`:
the registry classifies articles someone else wrote and is in no position to announce our
product, so the form is reached by `FORCE=launch` (or by the composer's own choice under
`auto`, since every brief carries the vocabulary). A **paged carousel** — a LinkedIn
document post of N slides — is not this type and is not built: it needs a new format, an
authoring path the composer cannot take (it writes HTML, not a PDF) and a publish path the
installed LinkedIn node cannot take either; the timed equivalent is already `SCENES` on an
animated type.

**The composer's guide is sandbox facts; the brief is the work.**
`agents/adapters/pi-render/prompts/authoring.md` states only what the brief cannot and the
framework does not: the working directory, `hyperframes` on `PATH`, the skills path, the
vendored GSAP, no network, how to run the render, and that the composer cannot see images.
It must not regain a method section, a composition-contract restatement or a review
checklist: the framework's own skills own the contract and `hyperframes lint`/`check` are
the automated gate. The **brief carries the motion grammar**, from the one committed copy
`agents/n8n/prompts/visual_motion_rules.md`, which `download_visual_rules` →
`visual_rules` fetches the way `brand.json` is; changing the grammar is a prompt-file
change, live on push, and it is not restated in the workflow. The brief also carries the
request's `FEEDBACK` (a reviewer's correction) and `EXTRA_PROMPT` (the caller's free
direction) verbatim, appended last, so a rejection reaches the composer on the next turn.
The image **fetches the framework's full skill set at the pinned release** in `docker
build` (`hyperframes-animation`, `-keyframes`, `-registry`, `-creative`, `-studio`,
`-core`) — the npm dist ships only three — asserts each `SKILL.md` exists so a subset
cannot ship quietly, and vendors `@hyperframes/shader-transitions` from the same release.
Its egress policy admits 443, so the session reaches the registry at author time (verified
`raw.githubusercontent.com` → 200 from the session pod, 2026-10-11); the vendored
primitives remain the always-available effects surface.

**The brand is one committed document.** `agents/n8n/datasets/brand.json` is the only copy
of the palette and typefaces; every surface that describes a look reads it — the authoring
brief, the raster prompt and the type registry — and `agents/n8n/scripts/test_brand.py`
fails on a colour or a typeface that appears anywhere else. The workflow fetches it once
(`download_brand` → `brand_tokens`), which resolves the requested scheme and hands the
composer a `{{ BRAND }}` text block and the raster prompt the `photographic.artDirection`.
A `diagrammatic` asset uses the brand's dark or light scheme; a `photographic` one is
described by the art direction instead, and the raster prompt keeps both modes. The tokens
are extracted from the site repository (`mkdocs.yml`, `docs/stylesheets/extra.css`);
re-sync with `BRAND_REPO=... python agents/n8n/scripts/extract_brand.py`, which is a
byte-identical no-op when the site is unchanged.

**Three triggers, one contract.** An `executeWorkflowTrigger` (sub-workflow call),
`POST /webhook/visual-studio`, and a form all take `CONTENT` (required), `ASSET_TYPES`
(comma-separated; blank means the registry's `default_types`; over
`max_types_per_request` is reported as skipped, never silently dropped), `FEEDBACK`,
`FORCE`, `SCENES` (an optional scene count; blank leaves the count to the composer's own
storyboard), `EXTRA_PROMPT` (optional free text appended to the brief after the
content and the rules) and `SESSION_ID` (optional; see *A session is a thread*). The studio
reads no caller state: everything it needs arrives on the trigger, it writes nothing to a
DataTable, and the rendered asset goes to object storage.

**A session is a thread, and a named one is an edit.** `SESSION_ID` is durable state, not
just an address: the adapter spawns Pi with `--session-id` against a PVC-backed transcript
directory, and `runs/<id>/` persists, so a turn that reuses an id continues the same
transcript and directory. `build_author_brief` uses the caller's `SESSION_ID` verbatim and
falls back to `<type>-<run id>` when it is blank, which keeps a first authoring isolated.
Whether a turn authors or edits is **only** the adapter's call: it checks for `index.html`
(or `out.svg`/`out.html` for those types) and picks the instruction, so a caller that names
a swept session degrades to a first authoring instead of editing nothing, and a caller that
names a brand-new one is not told to keep a composition that does not exist. The brief
itself never claims one — it did until 2026-10-14, inferring a continuation from
`SESSION_ID` alone, which contradicted the adapter for exactly those two cases: run 13356
named an empty `manga-cncf` and the brief said "apply the change below to it and keep
everything else", while the adapter said first authoring, and the composer reported a
restructure of a composition that was never there.
State expires: the session server sweeps `runs/<id>/` and `pi-sessions/*_<id>.jsonl` older
than `PI_RENDER_SESSION_TTL_DAYS` (default 7, matching the prune window below; `0` disables)
on startup and throttled after each turn, never the session in flight.
`openspec/changes/add-visual-studio-iteration/` is the record.

**FORCE and STYLE.** `FORCE` is `auto | diagram | story | data | poster | code | chart | timeline | quote | ui | manga | retro | launch | tiles`;
`auto` lets the composer choose the form, anything else pins it, and a forced form is honoured or
reported, never silently replaced. The vocabulary is one committed file, `prompts/visual_forms.md`,
fetched by the studio (into the brief) and by the curator (into the judge prompt as `{{ FORMS }}`),
so the judge that overrides a hook's default and the composer that builds it read the same
definitions — but the **enum** is duplicated into the graph, so adding a form is a registry *and*
graph change, not a prompt push: `normalize_input`'s `const FORCES` and the curator's `parse_judge`
and `parse_judge_backfill` `const FORMS` must carry the new name, and `test_hook_registry.py` and
`test_visual_studio_graph.py` fail until all three do. A missed copy is loud at run time as well —
`normalize_input` refuses a `FORCE` its enum lacks, naming the value. `STYLE` names a brand scheme (`dark | light`). `FORCE`
is validated in `normalize_input`, which is where a fixed enum belongs; `STYLE` is resolved
and validated in `brand_tokens`, because the scheme names are data in `brand.json` and a
hardcoded default would be a second copy of that decision. An unknown value in either
fails loudly, naming it.

**Creating it on a fresh instance**, in order:

    # 1. the workflow itself (--create prints the new id)
    export N8N_URL=http://datahub-local-core-automation-n8n.automation.svc.cluster.local
    export N8N_API_KEY=...          # mount security/n8n-root; do not read it into a shell
    OV=$(python3 scripts/apply_workflow_changes.py --print-pod-overrides)
    kubectl -n security run n8n-apply --restart=Never --image=python:3.12-alpine \
      --override-type=strategic --overrides="$OV" --command -- sleep 7200
    kubectl -n security cp scripts/apply_workflow_changes.py n8n-apply:/tmp/s.py
    kubectl -n security cp workflows/visual_studio.workflow.json n8n-apply:/tmp/vs.json
    kubectl -n security exec n8n-apply -- python3 /tmp/s.py --create /tmp/vs.json

    # 2. every later edit is field-level and guarded by the graph
    kubectl -n security exec n8n-apply -- python3 /tmp/s.py --workflow 'Visual Studio' \
      --require-edge 'parse_registry>if_agent' --set 'some_node:field=value' --apply

    # 4. and the handler it points at, which must be active to fire
    kubectl -n security exec n8n-apply -- python3 /tmp/s.py --create /tmp/vse.json
    curl -X POST -H "X-N8N-API-KEY: $N8N_API_KEY" "$N8N_URL/api/v1/workflows/<id>/activate"

**The composer is a Sympozium `HarnessSession`, not a core service.**
`sympozium_pi_render` (template `pi-render-session.yaml`) in `agents/sympozium/` runs the
`agents/adapters/pi-render/` image. A session Deployment honours
`AgentRuntime.spec.resources` where a Job's agent container is hardcoded to 1 GiB. It is
kept running (no `idleTimeout`), its PVC is **pre-created at 8 GiB** because the
controller's fixed 1 GiB claim is below the engine's 1024 MiB disk gate, and two additive
NetworkPolicies give n8n ingress on 8080 and the session egress to LiteLLM on 4000.
`PI_RENDER_URL` on the n8n deployment points at the session's own Service
(`datahub-local-ai-pi-render-api.automation.svc:8080`). The session server returns Pi's
report, not the file, so the artifact is a second request: the authoring
`POST /v1/chat/completions` carries a run-scoped `session_id` and an output `format`, the
turn runs in `<workspace>/runs/<session_id>/`, and `GET /artifacts/<session_id>/out.<ext>`
serves it (validated; traversal refused). The requested format is produced after the engine
render with the image's `ffmpeg` — `animation_linkedin` declares `format: gif`,
`animation_linkedin_video` declares `mp4`; a `deck` declares `format: html`, which is
authored directly (no transcode) and whose paired `out.mp4` the composer renders in the
same turn. The vendored GSAP is served as a sibling of the composition (`gsap.min.js`),
staged into the run directory by the session server: an absolute `/opt` path 404s at
render time. Rationale and the rollout are in
`openspec/changes/add-agent-authored-assets/` and
`openspec/changes/upgrade-visual-studio-authoring/`.

**Failure and retention.** `settings.errorWorkflow` points at `Visual Studio Error`, which
posts the reason to the `workflows` Slack channel and removes the run's temp files; the
studio's own graph has no Slack, no schedule, no GitHub node and one terminal node. A
failed composer costs one asset, not the run: `execute_author`, `store_artifact` and
`store_paired_artifact` continue on error and `agent_result` turns the empty result into
that asset's `ERROR` (for a deck, the deck is kept and the missing paired video is
reported). `Visual Studio Prune` runs daily at 04:00 UTC and deletes rows of
`TemporalFiles` whose `updatedAt` is older than an hour — the same rule `File Webhook`
applies on request, and the reason a quiet week cannot leave its rows behind — and the
bucket objects under `visual-studio/` older than **two days** — the delete is proven by
probe, while a 04:00 run *meeting* a stale object is still unobserved, because S3 sets
`LastModified` itself and a stale one cannot be staged.

**The asset lives in Garage and nothing writes a run row.** An **agent** asset is stored by
the `utils` MCP server, not by the workflow: `store_artifact` (and `store_paired_artifact`
for a deck) call `temp_store` with the session's own `/artifacts/...` URL and the key
`visual-studio/<RUN_ID>-<ASSET_TYPE>.<ext>`, and answer with the key and the byte count.
The bytes go from the session's HTTP route to Garage without passing through n8n at all,
which is the only shape that works here — a session pod **cannot be given a credential**
(`AgentRuntime.spec` has no `env`, `HarnessSession.spec` has four fields, and the Agent's
`env`/`volumes`/`volumeMounts` are AgentRun-only, verified by rebuilding the pod), and a
workflow that fetches and uploads stores the asset as surely as one that carries it
(measured: +6 `binary_data` rows and ~1 MB for one still run). `agent_result` parses the
answer into `S3_KEY`/`S3_BYTES` and `set_result` carries them, plus the resolved
`SESSION_ID`. There is no `visual_studio_table`: it reached **202.5 MB against its 200 MB
cap with only 12 rows**, four of them 32-34 MB, because the row carried each asset as a
base64 data URL, so every run failed at `record_run` *after* authoring and rendering
correctly — and when the row was emptied the table was deleted, because nothing had ever
read a row. `LinkedIn Post Sharing` reads the key and fetches the bytes through a signed
URL, which is what `temp_retrieve` is for.

**The studio now holds no S3 node at all**, and the raster path is why that is a decision
rather than an omission. `prepare_uploads`/`upload_assets` were left in place at first,
on the reasoning that they skip any asset without a data URL — which, once an agent asset
stopped carrying one, is every agent asset, leaving them to handle the raster asset alone.
That reasoning is wrong and the run said so in one line: with an agent-only run
`prepare_uploads` emitted **zero items**, `upload_assets` and `set_result` never ran, and
the webhook answered `No item to return was found` (execution 13401). A node that filters
its input can empty a chain, so the chain is gone: `merge_branches` feeds `set_result`
directly. A raster asset keeps the data URL the image model returned — those bytes are made
*inside* n8n, so no store can fetch them, and nothing read its key: the LinkedIn image path
takes its bytes from the image creator's `omImage`. A still run therefore costs its own
data URL in `execution_data` where an agent run costs none — **2,330 kB measured** on
2026-10-15 (execution 13417, a 1080x1350 PNG), against the 12-13 kB an agent run records. Two traps survive in
`Visual Studio Prune`, which still uses the S3 node: `list_assets` lists the prefix
**`visual-studio/` with its trailing slash**, because `file:getAll` sets a `/` delimiter and
with `visual-studio` the key's own slash makes it a CommonPrefix, so the object is never
listed (measured against the live node: 0 items, then 2) — the same delimiter is why the
store refuses a nested key. The error workflow writes no row either;
the node that used to write one (`record_failed`) carried `onError:
continueRegularOutput` and hid its own failure the same day — the write hit the size limit,
the workflow reported `success`, and no `FAILED` row existed for the run. Both nodes are
gone with the table.

**`Visual Studio` records its runs again, and the others must not.** `saveDataSuccessExecution`
is `all` on the studio — the point of moving the bytes out — and `none` on
`Visual Studio Test`, `LinkedIn Post Sharing` and `Visual Studio Prune`, whose payload still
*is* an asset (the test workflow's binary, the downloaded video it hands to LinkedIn, the
rows `deleteRows` returns). Without `none` n8n persists a copy of every rendered asset per
successful run: measured, `Visual Studio Test` alone was 511 MB across 46 runs and
`Visual Studio` 377 MB across 92, against a 1 GB `execution_data`. `saveDataErrorExecution`
is left at its default, so a failure still records everything needed to diagnose it. Note
that n8n persists *binary* data too, in Postgres, not only the JSON payload: measured on
2026-10-14, `binary_data` is **249 MB across 903 rows** and `execution_data` **1060 MB across
1405 rows**, in a 1335 MB database — so a run that carries an asset as binary costs the
asset's size as surely as one that carries it as a data URL. Recording is safe on the studio
only while its graph carries no bytes, which is what
`agents/n8n/scripts/test_storage_retention.py` asserts: it splits the workflows that may
record from those that must not, and fails if a data URL or a `fetch_artifact` returns to
the studio. **Measured 2026-10-15, execution 13406**: a run that produced a 9,326,134-byte
asset recorded a **13 kB** payload holding the key — where run 13356 recorded 80,838,754
characters for the same asset as a data URL — and `binary_data` gained no row for it. The
four binary rows a studio run does add are its `DownloadTemplate` children fetching the
config files, ~10 kB in total, which is a pre-existing cost of that fetch.
`openspec/changes/archive/2026-10-15-upload-assets-from-the-producer/` is the record, including the three
measurements that closed the other shapes.

**Verification is manual — there is no CI coverage for n8n.** The claims above were checked
by POSTing to the live webhook and by `--require-edge` graph checks. Read the live workflow
back after every apply and diff it against the export before believing a change landed.

**The studio can be exercised without touching a pipeline.** `Visual Studio Test` holds its
parameters in a Code node and ends in one item per asset — the summary plus the asset
itself as binary — so it runs from the editor's *Execute workflow*, or by POSTing
`/webhook/visual-studio-test` with any of `CONTENT`, `ASSET_TYPES`, `FEEDBACK`, `FORCE` or
`STYLE`. Its `params` and `call_studio` nodes carry no `SCENES` and no `EXTRA_PROMPT`, so a
scene count cannot be passed through it: send that request to the studio's own
`POST /webhook/visual-studio`, which takes the full contract. Its default is the cheap path
(one `image`, no
composer turn); set `ASSET_TYPES=animation`, `animation_linkedin` or `deck` to exercise the
composer, and `FORCE` to pin the form. It computes `TOTAL_PIXELS` and
`LINKEDIN_GIF_CAP_OK` for a GIF, which is how the platform's pixel cap can be checked by
eye rather than by memory.

**A webhook whose path declares a parameter is served under its `webhookId`, and that URL
is not the obvious one.** `File Webhook`'s path is `76a3521f-…/:fileId`, and the address
that works is `/webhook/76a3521f-…/76a3521f-…/<fileId>` — the id, then the declared path
with the parameter substituted. `/webhook/76a3521f-…/<fileId>` answers 404 "not
registered", which is presumably why `Image Content Generator` already publishes the
doubled-id form; the shape was verified by fetching a real asset on 2026-10-01. `Visual
Studio Test` uses it to hand back the assets it produced: each is written to
`TemporalFiles` and returned as a `DOWNLOAD_URL`, and the links stop working about an hour
later because `File Webhook` deletes rows whose `updatedAt` is older than that on every
request.

#### Post hooks and the visual intent

A post's **hook** is decided once, by the curator's judge, and carried on the row. The
single list is `agents/n8n/datasets/hook_types.json` (15–20 hooks grouped by intent —
argument, evidence, news, reference, narrative), and it is the only copy: the judge prompt
is injected the list as `{{ HOOKS }}`, the post generator reads the chosen hook's opening
shape from it, and the LinkedIn Image Creator reads the chosen hook's raster composition
device from it. Each hook declares `when` (eligibility), `opening` (the shape the post's
first lines take — format, length and closing stay the generator's own variety), `visual`
(`form` one of `FORCE`, `scenes`) and `image`. **Animation is unconditional**: no hook
declares a motion flag and the judge has none to set, so every admitted row is
`POST_MEDIA=ANIMATED`; the still-image path is only the fallback when the visual author
fails, and the manual `POST_MEDIA=STATIC` override.

The judge returns `hook` and a `visual` intent in the same call that reads the article;
`admit_to_backlog` writes them as the `HOOK`, `VISUAL_FORM`, `POST_MEDIA` and `SCENES`
columns (`POST_MEDIA` is `ANIMATED` or `STATIC`). `LinkedIn Post Creator`'s `set_variety_directives` reads `HOOK` and maps it through
the registry — it no longer re-picks a hook at random, and `classify_content` is retired. A
list-shaped article (a roundup, a state-of — the `ROUNDUP` hook) *may* declare
a scene count — the file defaults every hook to 0 and the judge sets it — so it is authored
as one item per scene in the existing `animation_linkedin` type, with no new media kind.
Because the lane usually sends no count, an intro cannot key on one: the three animation
types declare `introScene`, and `build_author_brief` asks for an opening title naming the
subject whether `SCENES` is declared or blank (run 14335 opened cold on 2026-10-19, and only
a human retry asked for the title). A queued row that predates the columns is re-judged by the
curator itself (`select_unclassified_queue` → a bounded loop, 12 rows a run) so the
backlog is backfilled over a few days and a row that slips through is repaired on the next
run; an unreadable verdict leaves the row unclassified rather than recording a guess. The
registry and the prompts are read from GitHub `main`, so
those halves are live on push; the workflow edits are live only after
`scripts/apply_workflow_changes.py`. The single-source property and the wiring are asserted
offline in `agents/n8n/scripts/test_hook_registry.py`.

#### LinkedIn post media

`LinkedIn Post Sharing` carries one media item per post, and which one is the **row's**
decision: `content_queue.POST_MEDIA` of `ANIMATED`/`AGENT` requests the animation and
anything else (`STATIC` or blank) takes the still path; `VISUAL_FORM` forces the
composer's form and `SCENES` carries a list's item count. `POST_MEDIA` is written by the
curator from the judge's intent and stays human-editable, so a person can force either way
by editing it — one media column, not two. An animated row asks `Visual Studio` for
`animation_linkedin_video` (mp4, the feed's 4:5 aspect) and attaches the approved asset; a
blank or `STATIC` row takes the `LinkedIn Image Creator` path exactly as before.

Both media kinds pass through the same **decision point**, `if_video_publish`, which sits
on the text approval's output and reads the asset's own `CONTENT_TYPE`, never the
requested type name: `video/mp4` takes the video path, anything else
(`image/gif`, `image/png`) keeps the existing node path (`send_2_linkedin_omImage`, which
still picks whichever conversion ran with `$('convert_animation').isExecuted ? … :
$('convert_image')…`). **The installed `n8n-nodes-base.linkedIn` node cannot upload video**
— its `shareMediaCategory` is `IMAGE`/`ARTICLE` only (verified in the live pod,
2026-10-11) — so the video path is the LinkedIn API directly: `linkedin_register_video`
(`POST /v2/assets?action=registerUpload`), `linkedin_video_upload` (the signed
`uploadUrl`, used as-is with no credential), `linkedin_post_video`
(`POST /v2/ugcPosts` as `shareMediaCategory: VIDEO`), reusing the same `linkedInOAuth2Api`
credential; the post id is read from the `x-restli-id` response header and the published
link resolves from whichever path ran. The video path is **verified against LinkedIn**: a
live publish on 2026-10-15 (execution 13429, task 8.7 of `upgrade-visual-studio-authoring`)
answered `201` from `linkedin_post_video` with `urn:li:ugcPost:7516401811025719298` read
back out of `x-restli-id`. The `animation_linkedin`
GIF type stays available for a caller that wants the animated image.

Four things about the branch are deliberate:

- **It branches on the asset, not the run.** The studio reports its run `STATUS: PARTIAL`
  whenever a requested type is unavailable, so `check_animation_result` tests the asset's
  own `STATUS`/`ERROR`.
- **A failed animation never blocks the post.** The failure output lands on a Slack form
  naming the article and the reason, which offers a re-author or the still, and an answer that
  never comes takes the still on a 30-minute bound (`options.limitWaitTime.values`) — either
  way it continues into the image branch *before* the image's own approval gate, so the
  substitute is reviewed as an image instead of silently replacing the animation. The branch
  tests for the retry **action**, not for the still, because an expired `sendAndWait` resumes
  with the node's own input and no `data.Action`: the inverse wiring would re-author an
  unanswered failure forever.
- **A rejection continues the thread.** A post has one media asset, so nothing needs
  keeping in step; the retry form's feedback is passed straight back to the studio as
  `FEEDBACK`, and the animated branch names a session derived from the article
  (`lips-<row_number>`), so the retry *edits* the composition the rejection named instead of
  authoring a new one. This reverses the earlier "free to re-author" stance, which was
  chosen when the composer could not see its own previous work; the cost of losing an
  approved composition now outweighs the freedom, and a caller that genuinely wants a fresh
  take sends no `SESSION_ID`. See *A session is a thread* above.
- **The reviewer sees the motion**: the asset is uploaded to Slack before the double
  approval, and the approval names the studio run, the frame count and the content type.

The GIF type's budget (8 fps, 48 frames, 776 px = 36,130,560 pixels) is what keeps the GIF
inside LinkedIn's documented cap of 500 frames or 36,152,320 pixels; frames and viewport
are a trade — more frames read smoother but must shrink to stay under the cap. No animated
type declares a hold: the brief asks for an ambient idle, not a frozen final frame. The
branch's wiring is asserted offline in
`agents/n8n/scripts/test_linkedin_animated_media.py`, which also fails if a node that needs
a credential has none or if the export has no published version.

#### Article Creator

Two workflows. `Article Content Writer` is the entry point (a manual trigger and a cron at
08:00 UTC Tuesday and Thursday) and owns the sheet, the slug, the assets and the publish;
`Article Creator` is the sub-workflow that drafts, called with `TOPIC`, `DESCRIPTION`, `URL`,
`CONTENT`, `MAX_WORDS`, `ASSET_TYPES`, `EXTRA_PROMPT` and `FEEDBACK`. The creator's
`executeWorkflowTrigger` is why the public API cannot start it — a verification run goes
through a temporary `webhook → executeWorkflow` probe, as every live check here has.

**A draft is reviewed before it is returned, and an over-budget one is retried rather than
fatal.** The loop mirrors `LinkedIn Post Creator`: `parse_article` →
`download_article_review_prompt` → `check_article_llm` → `parse_article_check_output` →
`merge_article_verdict` → `switch_article_check`, whose three outputs are `set_output`
(accepted), `set_error_max_tries` (bound reached) and a fallback back to
`download_article_prompt`. The retry re-renders the drafting prompt, so a rejection cannot
resubmit the same prompt. The bound is `{{ $runIndex + 1 }} > MAX_TRIES` with `MAX_TRIES = 3`,
copied from the LinkedIn lane rather than re-derived — which means it admits **four** drafts,
measured live (executions 13892, 13913, 13994): the name bounds the retries, not the drafts.

**The budget is checked in code and beats the reviewer.** `parse_article` counts the body's
words itself (markers excluded) and reports `PROBLEM` as *data*, never a throw; a count asked
of a model is a count that gets invented. `merge_article_verdict` rejects on that `PROBLEM`
whatever the reviewer's `<output>` said, and prefixes the reason with the parser's own numbers
— so the answer carries `OVER_BUDGET: 462 words against MAX_WORDS=400 Body is 462 words, so cut
62 words to meet the 400-word limit.` A `MAX_WORDS` that is missing or non-positive still
throws: that is a caller bug, not a draft to retry.

**The gate reads the writer's own rules file.** `RULES` is
`$('download_system_prompt').output` — the same `prompts/article_writer_system.md` the drafter
was given, fetched once — never a second copy that could drift.

**The reviewer's model call retries.** `check_article_llm` carries `retryOnFail: true,
maxTries: 5, waitBetweenTries: 5000`, matching the `check_rules_llm` it mirrors and the
drafting agent beside it. It did not at first, and one 30 s LiteLLM timeout ended a run that
had already produced four drafts (execution 13975, 2026-10-18): a reviewer that fails the run
it is checking is worse than one that reports no verdict.
`test_the_reviewer_retries_a_transient_model_failure` pins it.

**The gate must name the marker's form, not its id.** The reviewer's check read "spelled as the
type id", the reviewer took that to mean the bare id, and the first live runs rejected a
*correct* `<!-- asset:image_wide -->` twice — after which the writer dropped the marker
altogether, so the gate destroyed the thing it was checking (executions 13892 and 13913). The
publishing step is the authority: `build_commit_files` matches
`new RegExp('<!--\\s*asset:' + type + '\\s*-->')`. `prompts/article_review.md` now states that
form, and `test_both_prompt_files_name_the_same_marker_form` holds it to the writer's rule. This
is the 2026-09-30 LinkedIn failure in a new place: a rule the gate enforces has to be one the
drafter can satisfy.

**A caller's `EXTRA_PROMPT` reaches both passes, so an instruction that fights the budget makes
the loop unsatisfiable.** It is injected into the drafting prompt and into the reviewer's own
`## Extra rules`, so "write at least 500 words" against `MAX_WORDS=400` overshoots on the first
draft, is cut back on the retry (the feedback outranks it) and is then rejected by the reviewer
for breaking the very rule that forced the overshoot — the loop cannot converge and burns its
bound (execution 13975). Recorded as an open question in the change, not fixed: the LinkedIn lane
passes `EXTRA_PROMPT` to both passes the same way. Keep an extra prompt compatible with the
budget.

**The commit carries the entry's requested set and nothing else.** `read_asset_rows_for_publish`
filters the asset table on `ENTRY_ID` alone — no type, no status — so a row for a type the entry no
longer requests used to be committed as well: an orphan image under `docs/img/` that no marker
references, and a commit that did not match the asset set the run reported. Found 2026-10-17 while
applying 4.17 and worked around by deleting the stale row by hand, which is a workaround nobody
would remember on the next entry whose requested set changed. `select_article_to_queue` now emits
`REQUESTED_ASSETS` — the set it already derives with the hero rule — and both consumers read that
field: the publish gate stops deriving the rule a second time, and `build_commit_files` filters the
rows it commits to it and logs the types it left out. `PHASE === 'publish'` already implies every
requested type is `APPROVED` (the selector computes `pending` from the same set), which is why the
filter is on the type and not on the status: a status condition could only drop an asset the gate
had cleared. `test_the_requested_set_is_derived_once_and_read_by_its_consumers` pins that the hero
rule exists in exactly one node.

**A retry is handed the draft it rejected, in both lanes.** The reviewer's reason says "apply these
changes", and the drafting prompt carried the reason and no draft — so the drafter rewrote from
nothing, and on 2026-10-18 it went looking for material instead of editing: the retry turn called
`research_sources` with the same query seven times and `read_page` on the same page six times, 13
tool calls and 16 model calls, until the agent answered `Max iterations (12) reached` (executions
14018, 14020) and the run was lost with no draft. `download_article_prompt` now passes the rejected
draft as `PREVIOUS_DRAFT` and `download_post_prompt` as `PREVIOUS_POST`; both prompts say to edit it,
and the article one says not to research again. Measured on the next run (14071): 617/400 words →
retried → 387/400 accepted, the retry carrying 3,717 characters of the rejected draft and keeping
its opening sentence, with **one** lookup in the whole run. Three things about the expression:
`.last()` and never `.item`, because the paired-item lineage runs back through the switch and
silently resolves to `undefined` (the 2026-09-30 `VARIETY_DIRECTIVES` failure); not `.first()`, or a
third attempt edits the first attempt's draft and never converges; and `isExecuted`, because the
first attempt renders the same node with `parse_article` not yet run. The graph must be applied
**before** the prompts are pushed: a pushed prompt naming a placeholder the graph does not pass stops
every run, while a graph passing a var the prompt does not use is harmless.

**A human retry had the same gap in a new place, and it was the one the owner hit.** `PREVIOUS_DRAFT`
lives *inside* the sub-workflow, so it spans one invocation — and a person answering the approval
re-enters `execute_article_creator` as a **new** invocation, where `parse_article` has not run. Run
14178 (2026-10-18, still `waiting`) measured it: 14180's internal retry carried its rejected draft
(24,675-char prompt), while 14187 and 14191 — two human rounds — each rendered an empty
`## Previous Draft` and wrote a fresh article, the second against feedback naming a single section.
Both lanes now hand the retry the draft the human read, taken from the call node's **own** earlier run
(`$('execute_article_creator').last().json.text`, `$('execute_post_creator')` likewise), and the
sub-workflow prefers it only when it holds none of its own, so the internal loop is unchanged. No
store was read instead: the post lane has none (`content_queue` carries no post column) and the
article's `article_drafts` row is a copy of what the run still holds. That a node may read its own
earlier runs is measured rather than assumed — a probe cycle on 2026-10-18 (execution 14195) had
`$('step').last()` answer the previous run's value on the second pass. No prompt file changed, so no
push order applies this time.

**The drafting agent's iteration cap is a cost cap, not a spiral fix.** `maxIterations` went from 8
to 12 in October for a measured reason — every model failure inside the agent loop spends an
iteration, and a run with three failures exhausted 8 before writing (execution 13603). It does not
stop a spiral: 13603 spiralled to 16 tool calls at 8, and 14020 to 13 at 12, both ending on the cap.
Lowering it trades one failure for another, so it stays at 12 and the fix is the draft the retry is
handed.

**The requested asset set names each type once.** `select_article_to_queue`'s `requested()`
de-duplicates `ASSET_TYPES` before applying the hero rule: a row naming a type twice — the live test
row held `svg_wide,svg_wide` — was requested twice, which is two studio calls for one type and two
committed files at one `docs/img/` path. One de-duplication in the selector covers every consumer,
because the gate and the commit path read the field it derives.

**The gate judges the checks it is given, and nothing else.** `prompts/article_review.md` states its
scope: the checks listed, plus the human feedback. The entry's `TOPIC` and `DESCRIPTION` are context —
what the piece is for — not checks. Until 2026-10-18 they were enforced as checks, and the failure was
total: execution 14055's row said *"Plain language and no deep Kubernetes detail"*, the subject is a
Kubernetes-native CRD project, and the human's retry feedback asked for the opposite. The gate rejected
**four** drafts for the same reason — naming a custom resource, a controller, an admission webhook,
Helm — which is the vocabulary the subject is made of and which the writer's own rules invite by
calling the reader a practitioner. The run spent 20 minutes, burned its bound and failed with no draft.
An invented check is unfixable by construction: the drafter cannot read the reviewer's inference, so
the retry just carries it. The same prompt now also says the draft it is given is the **body only** —
`parse_article` strips the H1 into `TITLE` and passes the two separately — so an H1 is not required in
it; two of those four rejections demanded one, which no body can ever have. Both lines are pinned by
`test_the_reviewer_judges_only_the_checks_it_is_given` and
`test_the_reviewer_is_not_asked_for_an_h1_the_body_cannot_carry`.

**A run that fails before publishing records it and tells a human.** `fail_draft` was a bare
`stopAndError` and no node in the entry point wrote `STATUS=ERROR`, so a failed run left whatever the
last phase wrote: execution 14055 posted a draft for review at 09:14, failed at 10:14, and the row
still read `WAITING_APPROVAL` with an empty `ERROR` — claiming a live approval nobody would review.
Nothing else reported it either, because the run was **manual** and n8n does not invoke
`settings.errorWorkflow` for one. The failure path now runs `build_failure` → `record_failed_draft`
(`STATUS=ERROR`, `ERROR=<reason>`, `UPDATE_DATE`) → `notify_draft_failed` (the `workflows` channel) →
`fail_draft`. Two details are load-bearing: `fail_draft` reads the reason from `build_failure` rather
than `$('execute_article_creator').item`, because a paired-item read through new nodes is the
2026-09-30 failure in a new place; and `ERROR` had to be set `removed: false` in the Sheets node's
schema, or the column is silently not written. A row in `ERROR` is **not** picked up again —
`pick_candidate` selects `QUEUE` rows and stale claims — so it waits for a person, which is the
deliberate direction.

**The writer's tools are attached only when the entry has no source of its own.** A first attempt can
spiral exactly as a retry did, and the retry carry cannot help it: on 2026-10-18 execution 14147 —
whose prompt already held the README — called `research_sources` **seven times** with the same query
and `read_page` **six times** on the same page, 13 tool calls with three losing an iteration to a
gateway failure, and hit `Max iterations (12)` with no draft at all. `download_system_prompt` now
feeds `if_needs_research`, which branches on whether the entry's `CONTENT` already carries its source:
with a source, `create_article_ai_plain` runs and has **no tools attached**, so a spiral is
impossible; without one, `create_article_ai` keeps `research_sources` and `read_page`. Both agents
share the model nodes over `ai_languageModel` and both feed `parse_article`, and both are handed the
same prompt — the tool surface is the only difference. The researching agent's budget is raised to
**20** (the owner's call) and the no-tools agent stays at the measured floor of **8**; note the
trade, because `maxRetries` multiplies with the 120 s timeout, so a spiralling turn there can now
cost twenty steps. An agent node needs its `Chat Model` and `Fallback Model` inputs connected or the
PUT is refused (`Workflow cannot be activated because required inputs are not connected`), which is
how the first attempt at this change was caught.

**A failure the creator *throws* is reported the same way as one it returns.** The reporter added for
a returned failure covered only half the cases: `check_draft_error` never runs when the sub-workflow
call itself throws, so execution 14145 (`Max iterations (12) reached`) stopped the graph at
`execute_article_creator` and left the row `IN_PROGRESS` with no `ERROR` and no notice. The call node
now carries `onError: continueErrorOutput`, and its second output joins the returned-failure branch at
`build_failure`. Unlike `continueRegularOutput` — where n8n forwards the node's input and sets no
`json.error` (the 2026-09-28 note) — `continueErrorOutput` **does** set it: a probe measured
`{"message":"connect ECONNREFUSED 127.0.0.1:9","name":"Error","stack":…}` on the error output, so
`build_failure` reads `$json.ERROR` or `$json.error.message` and the row carries the real reason
either way.

**The article is written for a reader who is new to the subject, and it has a spine.** Until
2026-10-18 the rules said *"the reader is a practitioner, not a buyer"* and said nothing about the
article's shape, which is how a Sympozium introduction came back dense with custom resources,
admission webhooks and Helm for someone who had never seen the project — and how the gate then
rejected four drafts for it. `article_writer_system.md` now defines the reader as smart, busy and
**new to the subject** — an engineer from another field — and states the simplicity rules: explain
every term where it first appears (naming a custom resource is not the failure; naming it without
saying what it is for is), one idea per sentence, lead with the concrete, no sentence whose only job
is to sound impressive. It also states **the frame**, which is the same for every article: the opening
names the subject and the problem it answers, and **the close points at what to read or do next** and
never restates. The body comes from `prompts/article_structures.md`, fetched into the drafting prompt
as `{{ STRUCTURES }}`: seven named shapes — *introduction to a thing* (why the category exists → what
else is out there and where it stops → why this one → what it does best → how it is built), *a
decision and what it cost*, *an incident and the rule it produced*, *a comparison*, *a myth
corrected*, *getting started*, *the state of a thing*. The writer picks by fit, and `EXTRA_PROMPT`
can name one, the way the post lane's extra rules can name a subject.

**The AI-speak list is one file, fetched by both lanes.** `prompts/ai_speak.md` holds the banned
words, the filler phrases and the robotic scaffolding, and each lane injects it into its own rules
file as `{{ AI_SPEAK }}` — so the drafter and the gate of *both* lanes read one copy. The clause that
matters is kept with it: a listed word is banned as filler and allowed when it names the subject, an
article about a harness says "the Standard harness". `test_shared_prompts.py` holds the two lanes to
it and fails if any prompt restates the list, because the 2026-09-30 failure was exactly a gate
enforcing a list the drafter was not reading.

**The gate checks the objective half and not the judgement.** The new checks are the directional
close, the AI-speak from the rules, and a term the subject is built from used without saying what it
is for. "Is it simple enough" is deliberately **not** a check: that judgement is what rejected four
drafts for a Kubernetes subject and cost a run, and a rule the drafter cannot read is unfixable by
construction. The gate's scope line, added the same day, is what keeps the two apart.

**The hero a row does not name is animated: `svg_wide`, not a still raster.** The rule read *"either
raster counts as one, so a row naming the portrait `image` keeps its own choice and a row naming
neither gets the wide one, which is the frame a page wants"* — and `image_wide` is a **Gemini png**,
so a row whose own `ASSET_TYPES` was `svg_wide` (animated, `author: agent`) had a still prepended to
it. Article run 14196 measured it: `REQUESTED_ASSETS = "image_wide,svg_wide"`, the splitter's first
call was `image_wide`, and studio execution 14219 died on it — the animated asset the row actually
asked for was never authored. The prepend is now `svg_wide`, and a row naming its own raster still
keeps it: a page lead image is a legitimate still, a still nobody asked for is not. The
`split_pending_types` fallback for a row naming nothing matches. Note this is *not* the post lane's
rule — `POST_MEDIA` and its unconditional animation govern `content_queue`, and the article lane has
no motion flag at all; what it has is the requested set, and the hero is the first type in it.

**An SVG commits with an `.svg` extension, which the content type does not give you by splitting it.**
`build_commit_files` derived the extension as `CONTENT_TYPE.split('/')[1]`, and an SVG asset reports
`image/svg+xml` — so the path came out `docs/img/<slug>-svg_wide.svg+xml` and the article referenced
it. Measured by executing the committed node: the same call with `image/png`, `video/mp4`,
`image/gif` and `text/html` maps to `png`, `mp4`, `gif` and `html`, so the slash split was right for
every type except the one now used as the default hero. It is a lookup on the content type with the
slash split as its fallback, and `test_an_svg_asset_commits_with_an_svg_extension` pins it.

**The first published article exposed four defects at once, all in the commit and marker paths.** Run
14228 published the Sympozium introduction on 2026-10-18, and the result was a post whose only image
was an empty file referenced at a path the site does not serve, from a URL that 404s.

- **The fetch branch was inverted.** `plan_asset_uploads` marks an agent asset `NEEDS_FETCH: true`
  (it has an `S3_KEY` and no local bytes), and `if_asset_needs_fetch` sent that **straight to
  `create_blobs` with `FILE_BASE64: ''`**, while the fetch path
  (`presign_asset_publish` → `download_asset_publish` → `asset_bytes_from_download`) hung off the
  *false* output. The run proves it: those three nodes did not execute, and the committed file is
  **0 bytes** — the GitHub API reports `size: 0`, `sha e69de29b…`, git's empty blob. The outputs are
  swapped, and `test_a_raster_is_stored_and_an_agent_asset_is_refetched` used to *pin* the inversion.
- **The reference path was `/docs/img/…`.** `docs/` is the MkDocs *source* directory; the site serves
  from the root, and every hand-written post says `/img/…` (`202609-oss-trojan-horse.md`). The
  committed file still lands at `docs/img/…` — the two are different strings, and `sitePathOf` is the
  second one.
- **The published URL is not the entry's slug.** The site serves
  `https://www.alvsanand.com/blog/2026/10/18/sympozium-when-one-ai-agent-isnt-enough/` while the run
  announced `https://alvsanand.com/blog/2026/10/18/sympozium-when-one-ai-agent-isn-t-enough/`: the
  host is `www.`, and the blog plugin slugifies the **title** — `"isn't"` loses its apostrophe rather
  than gaining a hyphen — so the filename's `202610-` prefix never appears. Both are now built from
  the title and the day.
- **The writer was handed the raw `ASSET_TYPES`.** The row read `svg_wide,svg_wide`; the selector
  deduplicated it to `REQUESTED_ASSETS = "svg_wide"`, but `execute_article_creator` passed the raw
  field, so the prompt said two types and **both drafts carried the marker twice**
  (`['<!-- asset:svg_wide -->', '<!-- asset:svg_wide -->']`). The commit replaced both with the same
  reference — one illustration shown twice — and the gate's "exactly once" check, a model judgement,
  passed them. The entry point now passes `REQUESTED_ASSETS`, and `parse_article` **counts the markers
  in code** (`MARKERS: svg_wide x2`, `… x0`, `… not requested`), because how many markers a draft
  carries is a count and a count is not a judgement.

**The republish exposed a fifth defect one layer below the branch: the fetched bytes were the word
`database`.** Run 14259 (2026-10-19) took the fetch branch correctly, the signed URL served 14,338
bytes, and the published SVG was **8 bytes spelling `database`** (`content-length: 8`, GitHub blob
`ab1891c9…`). n8n is deployed in queue mode, where the default binary data mode is `database`: the
payload lives in the store and the item's `binary.data.data` is the literal placeholder `database`,
with the real handle in `binary.data.id`. `asset_bytes_from_download` base64-encoded
`bin.data` — `Buffer.from('database')` is `ZGF0YWJhc2U=` — so every agent-authored publish would
have committed that word. Read a payload with `helpers.getBinaryDataBuffer`, which is an RPC method
in the task-runner sandbox too, and which Visual Studio's `encode_stills` already used successfully
(run 14342, four stills). The node's guard now also rejects an empty buffer, and
`test_the_fetched_asset_bytes_are_read_from_the_binary_store` executes the committed `jsCode`
against an item shaped exactly like the live one — placeholder in `data`, bytes only behind the
helper. A textual assertion cannot see this class: the old code read plausibly and the JSON was
valid.

**A draft is improved before the human sees it.** `Article Content Writer` runs one improvement
pass between `check_draft_error` and `derive_slug`: five `DownloadTemplate` fetches, then
`build_improvement_context` (one item always; **throws** when `datasets/article_aspects.json` is
missing, unparsable or empty — the semantic-registry rule), `split_aspects` fans one item per
registry aspect, `download_aspect_prompt` fetches that aspect's own file by expression
(`template_name: "={{ $json.ASPECT_PROMPT }}"`, verified live on execution 14402 — three aspects
fetched and answered; the documented fallback is fixed download nodes per aspect, at the cost of
duplicating the enum into the graph), `review_aspect_llm` reviews the draft, `merge_aspect_findings` merges the
`<findings>` blocks tagged by aspect, and `if_has_findings` skips the improver when there is
nothing to apply. `improve_article` is an agent with **no tools** (`maxIterations: 8`, the
measured no-tools floor) that edits only what a finding or the feedback names.

The two improvement model nodes carry `options.timeout: 240000`, not the 120 s floor: the
improver edits the whole draft, and at 120 s it answered `Request timed out` (execution 14450),
which fell back to the gate-passed draft exactly as designed; the same edit completed at 240 s
(execution 14468, 1153 words). Keep the multiplier in mind — the model node's own retries multiply
with it.
`check_improved_draft` counts the budget and the asset markers **in code** — the twin of
`parse_article`, held together by a test that runs both on one fixture and asserts the same
verdicts — and `switch_improved_ok` retries once with the objective problem, after which
`select_final_draft` is the single convergence node `derive_slug`, `store_draft` and
`draft_to_file` read (nothing else in the lane may read the sub-workflow's answer). The findings
are **advisory, never gates**: the only gates stay the drafting gate, the re-check and the
human, because a judgement gate a drafter cannot read is unfixable by construction (the 14055
lesson) and the pass exists to *apply* judgement, which is only safe on the advisory side.

**The aspects are a registry, not a graph enum.** `datasets/article_aspects.json` lists
`structure`, `clarity` and `flow`, each with its prompt file and focus; adding one is a dataset
entry plus a prompt file, and the graph holds no aspect id. Correctness is deliberately absent —
facts, budget and markers stay with the drafting gate and the re-check, so an aspect finding can
never contradict a correctness check. One reviewer call per aspect, and `merge_aspect_findings`
reads the reviewer's own `text` field rather than its input: a chain node carrying
`continueRegularOutput` forwards its input on failure, and that input is the downloaded prompt,
which contains the literal `<findings>none</findings>` the instruction asks for.

**The audience is one column, four levels, one file.** `article_queue.AUDIENCE` is
`NONE | LOW | MEDIUM | ADVANCED`; blank reads as `NONE`, so no row needs a backfill.
`prompts/article_audiences.md` is the only copy of what each level means, and
`article_writer_system.md` points at the task prompt's Audience section instead of restating the
`NONE` reader. `select_article_to_queue` uppercases and trims the cell and **refuses** an unknown
level naming it — a mistyped level read as `NONE` would publish advanced orientation to a general
reader and nothing would ever say so — and the enum exists in three copies by necessity (the
definitions file, that const, and `board_intake.json`'s `defaults.audience`), held together by
tests that fail until all three agree. The board intake writes the default and a person edits
the cell; no model is consulted, because the audience is a person's decision like the board idea
itself.

**The Slack Retry re-enters the improvement pass**, not the drafting call.
`build_improvement_context` resolves the draft of record in this order: `select_final_draft`'s
own last run (a human retry improves the draft the human read, in the same execution),
`execute_article_creator`'s answer (the first pass of this execution), then the `article_drafts`
row (`read_draft_for_improvement`, `alwaysOutputData` so a missing row cannot stop the chain).
The call node's `PREVIOUS_DRAFT` mapping is gone — the sub-workflow now runs at most once per
execution, so it was dead — and the sub-workflow keeps only its internal `parse_article`-based
carry. `IMPROVED` / `FALLBACK` / `FAILED` / `NONE` and the per-aspect findings count ride to
`notify_article_review`, whose message names them, because the reviewer sees the motion. A
re-presented review resumed in a **later execution** reaches this via `switch_phase`, where the
stored-row source covers it.

**Push order, and it matters.** The new files first (`article_audiences.md`,
`article_improver.md`, the three aspect prompts, `article_aspects.json`) — inert until fetched,
but they must exist before the graph that fetches them is applied or the first run dies at the
404. Then the graphs (`content_board_curator`, `article_creator`, `article_content_writer` in one
`--changes` batch, guarded with `--require-edge`). Then the edits to `article_writer.md`,
`article_writer_system.md` and `article_review.md`: a pushed prompt naming a placeholder the
graph does not pass stops every run, while a graph passing one the prompt ignores is harmless.
The `AUDIENCE` column is added to the `article_queue` page by hand before the first append —
writing a column the sheet lacks is [UNVERIFIED] and not relied on.

**The pass is cheap and degrades rather than blocking.** +4 model calls per accepted draft in
the common case (three aspects + the improver; +1 on an objective retry), the improver skipped
when there is nothing to apply. Every new payload is prose, so the queue-mode binary placeholder
trap does not apply and the studio's storage rule is untouched. An aspect that exhausts its
retries contributes no findings and the rest run; a failed improver falls back to the gate-passed
draft; an improved draft that drifts over budget or drops a marker is retried once and then falls
back **recorded** — a failed improvement costs the improvement, never the draft.

**A chain whose entry edge was replaced is invisible to the isolation check.** Execution 14382
(2026-10-19) improved its draft, ended at `select_final_draft` as `success`, and stored, uploaded
and reviewed nothing: the new improvement chain had replaced `check_draft_error -> derive_slug`
and nothing wired the convergence node to it, while `derive_slug` kept its own outgoing edges so
`test_no_node_is_left_unconnected` counted it as touched. `test_workflow_invariants.py` now walks
every edge type forward from every trigger and fails on any node no path reaches — `ai_*`
sub-nodes excluded, because a model or tool is reached *from* its consumer.

**Firing the entry point with a probe needs care in queue mode.** `executeWorkflow` with
`waitForSubWorkflow: false` can have its child execution marked `crashed` by the queue recovery
before the worker picks it up, and then resumed minutes later — execution 14402 did exactly that,
reaching `waiting` on the review after being reported `crashed`. Read the newest execution again
before firing another, and remember `pick_candidate` takes the **lowest** `QUEUE` row: a second
probe during a wait drafted row 200, a different pending idea, because row 2 was already
`WAITING_APPROVAL`. A test row has to be the only `QUEUE` row, and the failure path recorded row
200 as `ERROR` when the drafting gate rejected its four drafts.

**A resumed execution's persisted data lags the live one.** After the Slack approval,
`GET /executions/{id}?includeData=true` kept answering `lastNodeExecuted: notify_article_review`
for minutes while the run had already passed `update_article_approved` and reached
`split_pending_types`; the newer checkpoint only appeared once the execution was cancelled
(2026-10-19, execution 14468). Read the execution's `status` and wait, or read
`executionData.nodeExecutionStack`, before calling a resumed run stuck — cancelling a live run on
one stale read loses the phase it had reached.

**The lane is otherwise unexercised by CI.** Nothing here has a live gate: the wiring is
asserted offline in `agents/n8n/scripts/test_article_review_gate.py` and
`test_article_entry_point.py`, and the behaviour was measured by hand on 2026-10-18 — the
over-budget retry that published (13994: 462/400 → 412/400 → 345/400, accepted), the bound
reporting `MAX_RETRIES_EXCEEDED: <the reviewer's own words>` (13892, 13913), the reviewer
carrying the committed rules file verbatim, and the hero marker landing where the writer put it
rather than at `build_commit_files`' fallback position. A live publish was not run: it writes a
commit to the blog repository, and the placement is a pure function of the draft and the asset
rows, which
`test_the_hero_reference_replaces_the_marker_where_the_writer_put_it` takes from run 13994.

Two traps in reading this lane's history. `OVER_BUDGET` is a substring of every export's own
`parse_article` jsCode, so a grep across execution data matches every run including ones that
never drafted — read the node's own `WORD_COUNT`/`PROBLEM`, not the blob. The over-budget cases
are 13849 (1276 against 1200), 13622 (369 against 350) and 13491 (331 against 50); execution
13844, which this change's proposal first cited, is an *authorization* failure in
`create_article_ai` that produced no draft at all.

Separately, this lane's model calls are the least reliable thing in the fleet right now: on
2026-10-18 three of eight runs died in the gateway — `opencode-go/deepseek-v4.1-flash`
answering `Duplicate 'call_id'`, and the `opencode-go/glm-5.3-flash` fallback answering
`Model does not support this protocol`, which makes the fallback useless whenever the primary
fails. Both are `datahub-local-core` LiteLLM settings, not this repository's, and they are why
the numbers above were collected over several runs.

#### Content board intake and the queue ceiling

Two queues, one writer each. `Content Feed Curator` owns `content_queue` (the post lane) and a
new `Content Board Curator` owns the board and `article_queue` (the blog lane) — a separate
workflow because the board is a different source with a different failure surface, and putting a
GitHub read and a second sheet's writes inside the feed curator's tuned caps and prompt budget
was the rejected shape. `openspec/changes/add-board-intake-and-queue-ceiling/` is the record.

**The board is issues, not a Project board.** The intake reads the open issues labelled `post`
in `datahub-local/datahub-local` — four today (#79, #80, #91, #95). The installed GitHub node has
**no issue-list operation**: the `issue` resource carries only create/get/edit/lock, and listing
is `resource: repository, operation: getIssues` with the label and state under
`getRepositoryIssuesFilters`. A design that used `resource: issue, operation: getAll` would
connect and never run. An imported row is `ENTRY_ID: gh-<number>`, the title as `TOPIC`, the body
as `DESCRIPTION`, the URL as `LINK`, and the `board_intake.json` defaults — no model is
consulted, because a board idea is a person's decision. Dedupe is `ENTRY_ID` and `LINK`, so an
issue is imported once and **the board is never written to**: no label, comment or close. A
pull request returned by the same read is dropped by its own marker.

**The 7-day ceiling is the row's own clock.** `cancel_after_days` in `curator_config.json`
(`datasets/`) cancels any row still `QUEUE`, `IN_PROGRESS` or `WAITING_APPROVAL` whose
`UPDATE_DATE` is older than a week — one value, read by both workflows. The clock is the last
write any phase made, which is what makes it safe: a live run rewrites `UPDATE_DATE` every phase
and is never a week old, while a run that died mid-claim or an approval nobody answered is. A
board row is fresh by construction, so the ceiling cannot swallow its own import. **The two lanes
spell it differently** — `content_queue` writes `CANCELED` (one L, its lane) and `article_queue`
writes `CANCELLED` **and** `ARTICLE_STATUS=CANCELLED`, because `pick_candidate` resumes a stale
claim by reading `ARTICLE_STATUS`; a single spelling in either would match nothing. The ceiling
is deliberately shorter than every hook TTL (10–60 days), so it, not the TTL, is what actually
retires a queued post — watch the curator digest's depth line.

**One pass owns a row.** `build_expire_rows` keeps the hook TTL, the per-category cap and
displacement, and returns early on any row past the ceiling — measured on the ceiling's own clock,
the row's `UPDATE_DATE`, not the `PUBLISHED_AT` its TTL check uses — so the two passes never write
the same row in one run (two writes, `EXPIRED` and `CANCELED`, would otherwise race), and no row
escapes both (an old article rewritten recently did, in the first version). Both reads
carry `alwaysOutputData`: n8n does not execute a zero-item node, so without it a quiet board
would stop the chain before the ceiling ran — the same failure shape as a filter emptying a
chain. The intake is **live** (created `RCSPaKMKsckAnJ9B`, active, error workflow wired), and
since the 2026-10-20 backup its committed file is a full export carrying its id and
`activeVersion`, so the two-copy invariant and the rest apply to it like any other workflow.

### MCP servers

The servers live in
[`datahub-local-ai-mcp`](https://github.com/datahub-local/datahub-local-ai-mcp),
one image per server (`ghcr.io/datahub-local/mcp-homelab-facts`,
`mcp-semantic`), both `linux/amd64,linux/arm64`. The design rationale — why
code gathers and the model writes, the four structural properties, the byte
budgets — is that repository's `README.md` and is not duplicated here.

What stays this repository's concern:

- **The deployment.** `agents/sympozium/templates/mcpservers.yaml` owns the
  `Deployment`, `Service`, `MCPServer` and the enumerated read-only
  `ClusterRole`. A kind missing from that role is a 403, which the server keeps
  distinct from an empty result. Pods must carry
  `app.kubernetes.io/name: mcpserver` or core's `agent-allow-tools`
  NetworkPolicy blocks 8080; the `MCPServer` uses the `url:` form so the
  controller reconciles no workload of its own; and the MCP endpoint answers on
  every non-health path, because the discovery bridge's path is undocumented
  and guessing wrong fails silently with `status.ready: true` throughout. Read
  `kubectl logs <run-pod> -c mcp-discover` after a deploy — it prints
  per-server tool counts, and a whole server failing is otherwise silent.
- **The data.** The images are generic; everything describing this cluster is a
  mounted ConfigMap at `/etc/mcp/<server>/`. Never mount under `/app`: it is
  WORKDIR and lands on `sys.path`, so `/app/semantic/` shadows the `semantic`
  package and the server dies with `module 'semantic' has no attribute
  'register'`.

| Server             | ConfigMap              | Source of the data                                                                                                                                         |
| ------------------ | ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `homelab-facts`    | `mcp-homelab-facts`    | `agents/sympozium/config/homelab_facts/`, rendered by `templates/mcp-configmaps.yaml`                                                                      |
| `semantic`         | `mcp-semantic`         | `config/semantic/registry.yaml`, a symlink to `workflows/dbt/semantic/bodega.yaml`                                                                         |
| `semantic-finance` | `mcp-semantic-finance` | `config/semantic-finance/registry.yaml`, a symlink to `workflows/dbt/semantic/finance.yaml` (scopes `silver.finance,gold.finance`, `toolsPrefix: finance`) |
| `utils`            | none — a Secret        | the temp bucket's endpoint, region, bucket and prefix, plus the key, from `mcp-utils-s3` |

**`utils` is the one server here that writes, and it exists so that no workflow carries an
asset's bytes.** Two tools: `temp_store(source_url, key)` fetches a URL and writes it to
`datahub-local-temp`, and `temp_retrieve(key)` signs a short-lived download URL. It is
called over HTTP by n8n rather than by an agent — the `MCPServer` object is rendered like
every other server's, but no persona mounts it, so no agent's prompt pays for it. Three
things make it safe rather than merely convenient, and all three are enforced in
`mcp_runner/s3.py` rather than trusted from the caller: the Garage key is read+write on
**one bucket** and nothing else, a key outside the one prefix this deployment owns is
refused, and a **nested** key is refused because the prune lists the prefix with a `/`
delimiter and would never see such an object to delete. It takes its configuration from
`envSecret` (`mcp-utils-s3`), the one `envFrom` in `mcpservers.yaml` — the values carry the
image and the prefix is in the Secret, so no address is baked into a workflow: n8n reads
`$env.MCP_UTILS_URL`, set beside `PI_RENDER_URL` in `datahub-local-core`'s n8n values.

The semantic ConfigMap carries **one** key: `registry.yaml`, the metric
contract. Everything describing the warehouse — table names, which columns are
documented, cardinality, dimension values — is read live from Trino by the
server and cached with a TTL, because the warehouse is authoritative about
itself and a copy is stale the moment the pipeline runs. A pruned dbt manifest
and a precomputed sample file used to be shipped alongside; both are gone, and
so are the scripts that built them.

The server reads **one** registry, verified in
`datahub-local-ai-mcp/servers/semantic/settings.py` (`SEMANTIC_REGISTRY_PATH`),
so `semantic-finance` is a second `MCPServer` over the same image rather than a
second registry in one process. `templates/mcpservers.yaml` therefore takes an
optional `configDir` and keys the semantic env block on `warehouseScopes`, not
on the name: the served module (`--server semantic`), the config directory and
the `toolsPrefix` are three separate things, and the finance server needs the
bodega module with its own mount and a non-colliding prefix (`finance`). A
second server that shares a `toolsPrefix` duplicates every tool name in the
catalog.

Two consequences worth knowing. `persist_docs` is **load-bearing** in
`workflows/dbt/projects/bodega/`: the server's documentation gate reads Iceberg
column comments, and dbt writes a NULL comment for a column listed in
`schema.yml` with a blank description — indistinguishable from undocumented, so
the gate would silently weaken to "the column exists". A test in
`workflows/dbt/tests/bodega/test_project.py` fails the build if any description
is blank. And `SEMANTIC_WAREHOUSE_SCOPES` has no default: the registry names
models by `ref()`, which carries no catalog, so a guess would resolve nothing
and report as a broken registry rather than a missing setting.

The registry reaches the chart as a **symlink** —
`agents/sympozium/config/semantic/registry.yaml` → `workflows/dbt/semantic/bodega.yaml`
(and `config/semantic-finance/registry.yaml` → `finance.yaml`, same mechanism).
Helm's `.Files` cannot read above the chart root but does follow a symlink
whose target is inside the repository, which is what avoids a committed
generated copy. Git stores it as mode `120000`, so ArgoCD's checkout resolves it
identically; `helm template` prints a warning about it and uses the contents,
`helmfile template` prints nothing.

`chronic_alerts.yaml` and `thresholds.yaml` are judgements no cluster can
answer — whether an alert is noise, and where a reading becomes a finding — and
their absence is loud but never fatal. The semantic registry, by contrast, is
fatal: without it the server has no metric definitions and must not answer.

`PROMETHEUS_URL` and `LOKI_URL` are **required** with no default: a guessed
address reports every reading `unavailable`, which renders a wrong endpoint as
an absent one. Garage stays optional — no token means the bucket section
reports itself unavailable and nothing else changes.

`top_services()` names no ingress controller, so `INGRESS_REQUESTS_METRIC` and
`INGRESS_SERVICE_LABEL` are required on the same reasoning — a guessed counter
matches no series, and no series reads as a fleet nobody uses. The label is
required rather than derived because it is not guessable even knowing the
controller: a ServiceMonitor owning `service` makes Prometheus relabel the
exporter's to `exported_service`, and grouping on the wrong one *succeeds*,
returning one row carrying the whole fleet under the scrape job's name.
`INGRESS_STATUS_LABEL` and `INGRESS_SERVICE_STRIP_PATTERN` are optional; the
latter trims a router hash that would otherwise make a service look new on
every run. All are set in `agents/sympozium/values/default.yaml.gotmpl`.

The semantic gate (`workflows/dbt/semantic/compile.py`) imports `registry.py`
from the MCP repository rather than copying it, so the gate and the server
apply identical rules instead of two copies that drift. It expects that repo
checked out beside this one; `MCP_REPO` overrides, and a missing checkout is a
readable error rather than an ImportError.

Two ordering rules when deploying: both ConfigMaps must exist before the pods
start — a missing facts mount degrades loudly but works, a missing semantic
registry is fatal — and after a sync read
`kubectl logs <run-pod> -c mcp-discover` for the per-server tool counts
(**18** and **5**). A whole server failing to register is otherwise silent.

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
  MEMORY.md                          why every knob is set the way it is
  values/default.yaml.gotmpl         per-cluster knobs only
  templates/ensembles.yaml           assembles the Ensembles at render time
  templates/mcpservers.yaml          Deployment + Service + MCPServer per MCP server
  templates/mcp-configmaps.yaml      renders config/<server>/ into a ConfigMap
  config/<server>/                   the data a server mounts at /etc/mcp/<server>/
  templates/_delivery.tpl            the postRun hook and the prompt block
  prompts/delivery/hook.md           the delivery contract, substituted per persona
  projects/<ensemble>/
    ensemble.yaml       team-level spec + `defaults:` stamped onto each persona
    agents/<persona>.yaml   skills, schedule, MCP servers, tool policy, memory seeds
    prompts/<persona>_{system,task}.md
```

Three ensembles, split on trust boundaries and not on subject:

| Ensemble            | What                                                    | Inbound?                |
| ------------------- | ------------------------------------------------------- | ----------------------- |
| `homelab-ops`       | six scheduled read-only reporters, one question each    | no — no channel binding |
| `homelab-responder` | one persona you can ask a question in Slack             | **yes**, the only one   |
| `homelab-reviewer`  | `renovate-reviewer`, the only persona with a write tool | no                      |

The reporters take their readings from the facts server in `datahub-local-ai-mcp`, so their
prompts are a report contract rather than a method — see
[MCP servers](#mcp-servers).

#### Conventions

- **Write the reasoning in `MEMORY.md`, not in the config files.** The YAML under
  `projects/` and `values/` carries values and one pointer line, nothing else;
  `agents/sympozium/MEMORY.md` carries why each knob is set that way, the
  per-persona decisions, and each new incident. That is also where a new lesson
  goes — `README.md` holds the structure and the long write-ups that already
  exist and is not growing further. A comment restating a decision beside the
  value is a second copy of it: the `toolsAllow` note had been pasted into nine
  persona files and the `grafana_list_datasources` note into four before this
  split. Stripping all of it changed neither the parsed YAML nor a byte of
  `helm template` output.
- **A prompt or seed names the lookup; the server holds the data.** Write what a
  persona should *do* — which tool answers which question, how to read a result,
  what to say when nothing comes back — and never what the data currently
  contains. No dimension lists, no column names a tool returns, no shop or
  product or namespace names, no counts, no "every invoice is X". Those are rows,
  and a copy of a row in a prompt or a `memory.seeds` entry is stale the next
  time the pipeline runs, with nothing to revalidate it: the agent cannot tell a
  remembered value from a retrieved one, so it states the stale copy with the
  same confidence. Prefer the shape over the instance — `semantic_list_dimensions
  (metric) says which dimensions exist` outlives `it carries supermarket,
  store_name and store_vat_id`, which was wrong the moment a dimension was added.
  Keep an example generic (`a shop with no rows`, not a brand) so it illustrates
  the rule instead of asserting a fact. What legitimately stays is wiring that is
  true by construction — that S3 here is Garage, that bodega-as-dataset is
  answered by `semantic_*` — because that describes the plumbing rather than what
  flowed through it. This is the same objection as the `toolsAllow` comments and
  the committed manifest above, and it has now cost four incidents; the concrete
  numbers belong in `MEMORY.md`, which is documentation and is read by people.
- **Prompts are files, never inlined.** A persona sets `systemPromptFile` and
  `schedule.taskFile`; the build script *rejects* a literal `systemPrompt` or
  `schedule.task`. Same reasoning as `agents/n8n/prompts/`.
- **Nothing is generated into the repository.** `templates/ensembles.yaml` reads
  `projects/` at render time, so the sources are the only copy. Do not reintroduce
  a committed manifest — it is a second copy that silently drifts from its source.
- **A `memory.seeds` edit is not done when it is merged.** The controller writes
  seeds once, at install, into `ConfigMap/<ensemble>-<persona>-memory` and never
  reconciles them, so a sync updates the Ensemble, `systemPrompt` and
  `toolPolicy` while the run's `## Memory Context` still carries the install-time
  text. Nothing fails and `kubectl diff` cannot see it. Run
  `uv run --with pyyaml python agents/sympozium/scripts/reseed_memory.py`
  (`--apply` to repair) after any seed edit, and when a persona behaves as though
  it never got a correction. It diffs seed *text* rather than counts — a matching
  count with different text is what hid `homelab-oracle`'s drift for eleven days,
  and both drifts found so far were found by accident.
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
  load-bearing.** The persona carries the type (`channels: [slack]`) and, in hook
  mode, a `{{ DELIVERY }}` token in its
  system prompt; values carry the credential secret (`channelConfigs`) and the
  `sympozium_delivery` knobs — `channel` and `deliveryMode`, with per-persona
  overrides. No CRD field
  carries a destination, so the channel only ever reaches the agent as prompt
  text: the templates substitute exactly `{{ DELIVERY }}`, `{{ CHANNEL }}`,
  `{{ AGENT }}`, `{{ ENSEMBLE }}` and `{{ SCHEDULE }}` and `fail` on any token
  left standing. `{{ DELIVERY }}` expands to one file,
  `prompts/delivery/hook.md`. Chart-only knobs must stay out of
  `sympozium_ensembles` — the webhook decodes `spec` strictly and rejects an
  unknown key outright. Nothing cross-checks the two halves, so read both files
  together whenever either changes. Note the binding is *bidirectional* — an inbound Slack message can start an `AgentRun`
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
  against 2 in one day. A hook posts unconditionally, so reach for
  `schedule.interval` if a channel gets too busy. A persona with no
  `sympozium_delivery` channel gets no hook at all, which is what keeps
  `homelab-reviewer` silent by design, and `hook.md` deliberately names no tool:
  a 4B model reads a tool name as permission to call one.

  The other mode is **`reply`**, which the responder uses: a bound persona that
  answers in the thread that asked, through the channel sidecar. It takes no hook
  and needs no configured destination — the hook hardcodes one, and that is how
  two questions asked in two different channels were both answered into a third.
  A `reply` persona carries its own answering contract in its prompt instead of a
  `{{ DELIVERY }}` token, and `templates/ensembles.yaml` fails the combination. **A `reply` persona must not allowlist `send_channel_message`
  either**, for the same reason a hook one must not: the reply is the run's own
  final text, `status.result`, posted into the asking thread by the controller,
  while the tool is a separate path that resolves no destination on a reply run.
  Keeping both cost two answers on 2026-08-31 — the model sent the real answer
  with an empty `chatId` (rejected `channel_not_found`) and then wrote a summary
  of having sent it, which is what the reader got. `tool` mode is gone: it cost a
  duplicate copy of every report per bound persona, and nothing used it.
- **`send_channel_message` takes the destination in `chatId`.** Its `channel`
  argument is the *transport* (`slack`, `telegram`, …), never a `#name`. With
  `chatId` unset the tool still answers `Message sent`, targets "owner (self)",
  and on a scheduled run — which has no owner — Slack rejects it as
  `channel_not_found` in the `<persona>-channel-slack` sidecar log, the only
  place a delivery failure is ever visible. This cost every scheduled report for
  two days. Naming the argument was not enough: the prompts showed the call as
  `chatId: "{{ CHANNEL }}"` and a 4B model copied the quotes into the value, so
  Slack rejected the same way for another two days. A prompt for a model this size
  must never show a value inside syntax the model is also expected to strip.
  **No persona holds this tool any more** — the responder was the last and lost
  two answers to it (previous bullet), so both delivery modes now deliver the
  run's final text and nothing in this chart posts by tool call. Full write-up in
  `agents/sympozium/README.md`.
- **The report names its agent; it never invents a time.** Nothing in this fleet
  returns the current time (verified — the runtime injects no clock and no MCP
  server exposes one), so the header carries agent, ensemble and cadence, the
  prompts forbid any date or duration not read from a tool result, and Slack's
  message stamp is the run time. An authoritative in-message timestamp needs a
  `lifecycle.postRun` gate hook, which is the CRD's mechanism for rewriting
  agent output.
- **An HTTP endpoint replaces a persona's schedule; it does not add to it.** The
  `sympozium_web_endpoint` values tree, the render-time skill append and the
  validator's guard for it are all **removed** — nothing in this chart exposes an
  HTTP trigger any more, and the responder covers "ask it something" properly.
  The three reasons it went are worth keeping, because `webEndpoint` is now a
  first-class persona field and someone will be tempted again. A serving
  `AgentRun` makes the schedule controller skip every tick for that agent,
  silently, with the `SympoziumSchedule` still `Active` and no run failing. A web
  run gets **neither `toolPolicy` nor `lifecycle`**, so it is both unbounded — 60
  tools including `write_file` and `execute_command` — and undeliverable, which is
  how one wrote a full CRITICAL report and delivered none of it. And it
  **truncates the task to its first line**, so anything the `taskFile` said past
  the opening sentence is gone. Never put a requirement in a field a caller can
  replace. If an HTTP trigger is ever wanted again, use
  `agentConfigs[].webEndpoint` and re-verify all three.
- **Test with a hand-applied `AgentRun`, not the HTTP endpoint.** It suppresses
  no schedule and takes `systemPrompt`, `task` and `toolPolicy` inline, so a
  probe can differ from the real thing. The pod is deleted on completion
  whatever `cleanup` says, so stream the log while the run is live. A run that
  has *already* finished is still readable, though: Loki keeps every container
  of it, keyed by `status.podName` over the `startedAt`/`completedAt` window,
  which is the only way to diagnose a scheduled run after the fact — and the
  way to count a failure mode across the fleet instead of guessing at it. Tool
  *results* are logged nowhere; replay the query to see what the model saw. But `status.result` is
  dropped whenever the reply contains invalid UTF-8: the runner ships it to the
  controller over gRPC, protobuf refuses to marshal a bad `string`, and the run
  still reports `Succeeded` with no `error`. Our own header caused it — the model
  was told to echo `·` (U+00B7) verbatim and sometimes emitted a broken byte pair
  — so the delivery prompts are ASCII-only inside every indented block. Nothing
  enforces that now, so grep a prompt you touch for non-ASCII inside an indented
  block (`grep -nP '^\s+.*[^\x00-\x7F]'`). A model can still corrupt a character on its
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
  unprefixed. Drift between the two lists is silent — it costs prompt budget and
  fails nothing — so diff them by hand when editing either. The `toolsDeny` lists are now redundant by construction and kept only as a record
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
  that omits them. Write the value out even when it *is* the default, and
  re-derive the list after a control-plane bump (`kubectl get crd ensembles.sympozium.ai -o json | jq '.. | objects |
  select(has("default"))'`). Note that `kubectl diff` cannot see this class of
  drift — it defaults both sides; diff a `--dry-run=server` apply against the
  rendered manifest instead. Core's ApplicationSet also carries
  `ignoreDifferences` on `memory.maxSizeKB` and `schedule.firstTick`; keep them
  as a backstop for a future default, not as the mechanism.

#### The thinking to carry forward

These are the judgement calls behind the current fleet. Apply the same reasoning
rather than copying the outcomes, since the constraints will change.

- **The `mcp-k8s` ClusterRole in core is what actually grants Kubernetes read
  access — the SkillPack RBAC is not.** Every `k8s_*` call a persona makes goes
  through the `datahub-local-core-automation-sympozium-mcp-k8s` ServiceAccount,
  whose ClusterRole is `apiGroups: ["*"], resources: ["*"], verbs:
  [get,list,watch]`. That is the reason a new object kind — a Longhorn volume, a
  CloudNativePG `Cluster`, a cert-manager `Certificate` — works without a core
  change, and it is deliberate: an unlisted group fails silently and the agent
  just writes a blander report. A `SkillPack`'s `sidecar.rbac` grants a *separate*
  identity used only by that pack's sidecar, so narrowing it protects nothing
  unless a persona mounts the pack — none do. Check which of the two you are
  looking at before changing either.
  The cost of the wildcard is that `k8s_resources_get` returns whole objects,
  which for a Secret is the base64 values in full (verified against
  `mcp-slack-token`, 2026-08-24). So that tool is in `BANNED_TOOLS`:
  `k8s_resources_list` returns a table — names, types, key counts, the kind's own
  printer columns — and is the shape a reporter should have. If a persona ever
  genuinely needs an object's contents, narrow the ClusterRole to enumerated
  groups first rather than allowlisting the tool against a wildcard.
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
  The expression now lives in `datahub-local-ai-mcp`, where a test asserts the direction
  rather than a regex reading the prompt. Give a small model the
  literal expression, not a description of it — it will not assemble a join from
  prose, and it will report whatever it computes with total confidence.
- **A discovery tool that returns several plausible answers is a liability.**
  `grafana_list_datasources` was allowlisted so the Prometheus uid would not be a
  hardcoded guess. It produced one: this Grafana serves three datasources, and
  Loki's uid is the hex string `P8E80F9AEF21F6940` while Prometheus's is the
  literal word `prometheus`. A 4B model takes the hex string for the real
  identifier and the bare word for a placeholder to resolve, so every PromQL
  query went to Loki and answered `404 page not found` — against a prompt that
  stated the right value two paragraphs above. The tool is gone from all four
  Prometheus-reading personas and the uid is pinned; the datasource is
  provisioned `readOnly` by kube-prometheus-stack, so the literal is stable, and
  if it ever changes the agent reports every metric unavailable, which is loud.
  Prefer a pinned literal plus a loud failure over a lookup the model has to
  choose from.
- **A mandatory report format will be satisfied with invented numbers.** With
  Prometheus 404ing, `endpoint-warden` still owed seven columns per node, so it
  filled the disk column from the only tool that answered — relabelling
  `k8s_nodes_top` memory as disk and calling a 5%-full control-plane disk "79%
  disk fill (CRITICAL)", then emitting the whole report twice with different
  numbers. The standing "never report a number you did not retrieve" rule lost to
  the format demanding a value. A format is only safe if it makes absence
  expressible: a column with no metric is now the literal `unavailable`, a row of
  those is a legitimate row, each figure must come from the metric named for it,
  and the sections are emitted exactly once. Verified with a hand-applied
  `AgentRun`, which now returns the real 2-35% spread in one tool call.
- **An instruction to investigate needs a budget and an exit.** `sre-sentinel`
  was told to root-cause every new alert and given no cap. On 2026-08-24 it read
  a real new `TargetDown{job="longhorn-backend"}`, then spent five lookups on it
  — a scrape-job name passed as a pod name, `namespace` written as a term inside
  `labelSelector`, the same call repeated byte-for-byte — and every one returned
  empty. It then emitted a turn with neither text nor a tool call, which the
  runner logs as `terminal turn had empty text`, reports as `Succeeded` with a
  null `result`, and the delivery hook renders as a placeholder. The alert went
  unreported. A model this size does not decide on its own that it has learned
  enough to start writing, so the prompt grants *at most 3 lookups* per alert and
  names what to write when they yield nothing (`cause not determined`, stated to
  be a legitimate finding). Both halves matter: a cap with no escape hatch just
  relocates the silence, exactly as `endpoint-warden`'s mandatory table produced
  invented numbers until absence became expressible as `unavailable`. Give the
  model the literal shape of the call too — `namespace` is its own argument on
  every `k8s_*` tool and never a label — and remember that hook mode removed the
  *dominant* cause of an empty result, not the mechanism. `db-steward` then
  repeated the whole failure the same day against `k8s_resources_list`, because
  the fix had been written for the persona that broke rather than for the tool:
  seven of its fourteen calls guessed selectors for one CloudNativePG `Cluster`
  (`name` as a label, `namespace` inside `labelSelector` again, two contradictory
  equalities on one key, one call repeated byte-for-byte) and the day's Postgres
  and Valkey readings, already in hand, were never written down. So the budget,
  the exit and the selector rules now attach to any prompt naming
  `k8s_events_list`, `k8s_pods_log` or `k8s_resources_list`. Write them into any
  new prompt that names one of those three; nothing checks it for you.
- **`MAX_TOOL_ITERATIONS` is a real ceiling and hitting it is silent.** The
  runner caps tool calls per run at 50; five runs have hit it, and the failure is
  worse than a truncated report — the run ends `status: error` and the whole
  sweep is lost, leaving the delivery hook a failure notice to post instead of a
  report. (The hook *does* run on a failed run — `postRun` is best-effort and
  fires whatever the phase; this file said otherwise until 2026-09-13.)
  `endpoint-warden` used 48 of 50 one run and failed on 50 the next. Both
  ensembles set it to `"100"` in `defaults:`, quoted because the CRD types `env`
  as `map[string]string` and the webhook decodes strictly. The real limit is the
  65536 context every accumulated tool result must fit inside, so raising this is
  headroom, not permission to sweep wider.
- **A cumulative counter is not a state, and the suffix will not tell you
  which is which.** `db-steward`'s prompt called
  `cnpg_pg_stat_archiver_failed_count` "the most important number you look at"
  and never said it was a counter, so a lifetime total of 2 — two failures 5.4
  days old, against a successful archive 95 seconds old and
  `increase(...[24h]) = 0` — paged CRITICAL "recovery is silently broken" on
  every run, twice into Slack. Same class as the fill inversion: right metric,
  wrong reading. Prompts now carry the literal
  `increase(cnpg_pg_stat_archiver_failed_count[1h])` and a rule that a non-zero
  total with a zero increase is *healthy*. Two traps found fixing it.
  `cnpg_backends_total` and `cnpg_backends_waiting_total` are **gauges** despite
  the `_total` suffix, so a suffix rule fails a correct prompt — read the type
  from Prometheus's metadata API instead (`curl -sG .../api/v1/metadata
  --data-urlencode metric=<name> | jq -r '.data[][0].type'`), which is what
  the MCP repo's tests assert. And prose does not work: `endpoint-warden` said
  "take the rate, not the raw counter" twice and still handed the model bare
  metric names, so both prompts now write the window out. A model this size also
  drops the wrapper — given `increase(m[1h])` it sent `m[1h]` and labelled the
  answer as the increase — so the prompts state that an `expr` is the whole
  line, function call included, which is the `chatId` lesson in a new place.
- **A permanent finding is a bug in the prompt, not a problem in the fleet.**
  `endpoint-warden` reported orpi-0's kernel as drift against orpi-1/2/3 every
  run for days. It is not drift: orpi-0 is an Orange Pi 4 LTS (RK3399, rockchip64
  tree), orpi-1/2/3 are Orange Pi 5B (RK3588, rk35xx vendor tree), the amd nodes
  are Debian trixie amd64 and the NAS is TrueNAS. Different SoC families cannot
  converge on a kernel, so the finding could never be actioned and never clear.
  Versions are comparable only *within* a hardware class — the one real pair here
  is amd-1's 6.12.96 against amd-2's 6.12.101 — and a class of one is never the
  odd one out. Check that a rule you give a persona is one the fleet can actually
  satisfy, especially where a non-empty findings section is itself a change
  condition that forces a post.
- **Verify the telemetry exists before writing a prompt against it.** Every
  metric named in a prompt was confirmed present in this Prometheus. Two traps
  found this way: Valkey is scraped by a redis exporter so its metrics are
  `redis_*` and never `valkey_*`, and node-exporter's SMART series is
  `smartmon_temperature_celcius` (upstream typo). A small model cannot recover
  from a plausible-but-wrong metric name. Where telemetry is genuinely missing —
  systemd units, OS package updates, Garage/S3 — the prompt must not pretend
  otherwise; record the enabling change instead
  (`agents/sympozium/MEMORY.md#follow-ups-to-share-with-the-other-repos`).
- **Seed the noise.** Most alerts in this cluster fire permanently, including
  `KubeSchedulerDown`/`KubeControllerManagerDown`, which are artifacts of k3s
  embedding those components with no separate metrics endpoint. A small model
  cannot deduce that, so the known-chronic set lives in `sre-sentinel`'s memory
  seeds and reports are shaped new / still firing / resolved. Re-seed when the
  chronic set changes.
- **Read-only by default, and `toolPolicy` is not the boundary.** Every persona
  denies `write_file` and `execute_command` — the latter is a shell, and with MCP
  servers wired it is also redundant. An agent that changes things should be a
  separate, explicitly authorised one, not a capability quietly added to a
  reporter. But the deny filters *schema registration*, not dispatch: the runner
  logs `tool policy: denied tool "execute_command"`, omits the schema, and then
  executes the call anyway if the model produces it. A SkillPack is what makes it
  produce one — `sre-observability` says "Use `execute_command` for all shell
  commands" and `k8s-ops` claims "full cluster admin access ... kubectl works out
  of the box", and 744 shell commands ran across the fleet in a week on personas
  that denied it. Both packs also declare sidecar RBAC that the controller binds
  to the *shared* `sympozium-agent` ServiceAccount, so mounting one granted every
  agent in `automation` create/delete on pods, `pods/exec`, secrets, deployments
  and rolebindings. Both are removed, and nothing stops a third being mounted, so
  read a pack's `.spec.skills[].content` **and** `.spec.sidecar.rbac`
  before mounting it: a skill is prose competing with the persona's prompt, and
  prose wins.
- **The model constrains the design.** The fleet runs on the LiteLLM gateway in
  `data` (`http://datahub-local-core-data-litellm.data.svc.cluster.local:4000/v1`),
  model `opencode-go/deepseek-v4.1-flash`, with `opencode-go/glm-5.3-flash` as
  the gateway's router fallback. The cluster-local Ollama GPU queue is no longer
  on the path; the 90K window and `OLLAMA_NUM_PARALLEL` reasoning that used to
  live here are history, not constraints. **Every agent prompt must still stay
  short and literal, like a compact GitHub/Copilot prompt:** one job, exact tool
  order, a small lookup cap with an explicit no-result exit, exact output shape,
  and final delivery instruction. Put deterministic gathering, reusable context,
  and detailed method in MCP code or `MEMORY.md`, not prompt prose. Do not
  restore long tutorials, copied schemas, or repeated background explanation.
  `toolsAllow` bounds injected schema and is a context-budget control, not merely
  permission. `workflowType: autonomous`, five-to-eleven-tool allowlists, two
  skills per persona, `runTimeout: 30m` (45m for the reviewer) and staggered
  schedules with `firstTick: afterInterval` all stay as reviewable defaults —
  revisit them with measurements, not assumptions, now that the serving model
  changed. Note the staggering still only holds for cron ticks: the Ensemble
  controller starts a run within the same second as every `SympoziumSchedule` it
  rewrites, so one `helmfile apply` touching N personas queues N real runs —
  they post to Slack, spend `MAX_TOOL_ITERATIONS` and write memory — whatever
  `firstTick` says and with `status.nextRunTime` still pointing at tomorrow.
  Apply once and probe with a hand-applied `AgentRun`. Prompts name the tools to
  call in order and end with a required section layout and a "no report, no run"
  rule.
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
- MCP server tests moved with the code to `datahub-local-ai-mcp`. They need no
  cluster, and are where nine prose validators went: regexes that policed
  English in a prompt became assertions about the expression the server sends.
  Worth knowing that the counter/gauge test shows a suffix rule failing this
  cluster in both directions — `cnpg_backends_total` is a gauge despite
  `_total`, `cnpg_pg_stat_archiver_failed_count` a counter despite `_count`.
- `agents/sympozium/` tests only the delivery hook (`tests/test_deliver_slack.py`, the one piece of code there that runs in production). It has no source validator: `scripts/validate.py` was deleted on 2026-08-31 because most of it mirrored the cluster and the upstream CRD, and a mirror that drifts fails correct config. CI runs the hook tests and then renders the chart through `helmfile` — the render is the only gate on `projects/`, so anything it cannot see reaches the admission webhook (loud) or the running agent (silent). See `agents/sympozium/MEMORY.md` for what is now unguarded.
