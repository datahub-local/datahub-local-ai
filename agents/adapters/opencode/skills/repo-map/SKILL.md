---
name: repo-map
description: Which datahub-local repository owns which concern, and which one to open for a given question. Use before choosing a repository, cloning one, or answering a question about where something lives.
---

# Repository map

Fifteen repositories are public under `github.com/datahub-local`. Five are the
platform and get the work; the rest are support artifacts and get touched only
when a task names them.

## The workspace

| Repository | Owns | Read first |
| --- | --- | --- |
| `datahub-local` | The published documentation site (MkDocs). Project pages, architecture, lessons learned. | `mkdocs.yml`, `docs/` |
| `datahub-local-core` | The helmfile releases ArgoCD applies: every service, its values, its patches. | `releases/<namespace>/helmfile.yaml.gotmpl`, `releases/<namespace>/values/` |
| `datahub-local-ai` | AI workflows and the data pipelines: n8n exports and prompts, Sympozium ensembles, dbt/dlt/Airflow, Superset bundles, adapter images. | `AGENTS.md`, then the deep dive for the path you touch |
| `datahub-local-ai-mcp` | The MCP servers agents call: `homelab_facts`, `semantic`, `semantic-finance`, `utils`, `opencode`. | `README.md`, `servers/<name>/` |
| `datahub-local-bootstrap` | Ansible that brings a machine up as a cluster node. Owner only. | `README.md`, `playbook/` |

## Where to go with a question

- "How is this deployed, and why does this Pod fail?" `datahub-local-core`. The
  values file for that release is the answer; the chart is upstream.
- "Why did this automation fail?" `datahub-local-ai`, under `agents/n8n/`.
- "What does this metric mean, and what SQL computes it?" `datahub-local-ai-mcp`
  (`semantic`) with the registry in `datahub-local-ai/workflows/dbt/semantic/`.
- "Add or fix a dashboard." `datahub-local-ai/workflows/superset/`.
- "Change a page or a diagram." `datahub-local`.
- "Change what an agent reports or when it runs." `datahub-local-ai/agents/sympozium/`.
- "Add or fix an MCP tool." `datahub-local-ai-mcp`.
- "Why does a host behave like this?" `datahub-local-bootstrap` for the role, read
  only. The running host itself is the owner's machine.
- "How do I describe the platform?" `datahub-local`, which is the published text.

## Support repositories

`garage-helm`, `spark-apps-helm`, `node-exporter-textfiles`, `ollama-metrics`,
`servarr`, `Byparr`, `dagster-celery-k8s-oci`, `dagster-user-code-example`,
`container-helm-version-updater`, `docker-lineageos`. They carry a chart, an
image or an example the platform consumes. Nothing routine lands here, and a task
that names one is the only reason to open it.

## Never

`datahub-local-secrets` and `datahub-local-private-config` are private. They are
out of scope: do not clone them, read them, quote them or infer their values.
If a task needs a value that lives there, ask for that one setting.

## Rules that hold across repositories

- A change belongs in one repository. If two must move together, do one and
  report the other as a dependency with the exact change it needs.
- The repository's own `AGENTS.md` or `CLAUDE.md` outranks this skill.
- `datahub-local-core` deploys what `datahub-local-ai` and
  `datahub-local-ai-mcp` build. An image change is a commit and a digest bump in
  core, in that order, and neither half is done alone.
