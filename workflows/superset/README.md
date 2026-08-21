# Superset dashboards

Superset dashboard definitions, organised by project like the other sub-projects,
plus a Helm release that deploys them as ConfigMaps for the Superset **dashboard
sidecar** running in [datahub-local-core](https://github.com/datahub-local/datahub-local-core)
(`releases/data/files/scripts/superset/superset_dashboard_sidecar.py`).

The sidecar imports every ConfigMap labeled `superset_dashboard=1` whose
`binaryData` carries a Superset v1 export bundle (`.zip`), marks the dashboards
and charts as externally managed (read-only in the UI, drift is reverted), and
deletes them from Superset when the ConfigMap disappears.

## Layout

```
workflows/superset/
  projects/
    <project>/
      dashboard_export/     Superset v1 export bundle sources (plain YAML)
        metadata.yaml
        databases/          database connection(s) the bundle ships with
        datasets/           physical + virtual datasets
        charts/             one YAML per chart
        dashboards/         dashboard layout, tabs and native filters
  scripts/
    build_bundles.py        zips every projects/*/dashboard_export into release/files/
  release/
    Chart.yaml              Helm chart packaging the zips as labeled ConfigMaps
    helmfile.yaml.gotmpl
    templates/superset_dashboard.yaml
    values/default.yaml.gotmpl
    files/<project>.zip     built bundles (committed)
```

## Workflow

1. Edit the YAML under `projects/<project>/dashboard_export/`.
2. Rebuild the bundles (reproducible zips — no diff churn on rebuild):

   ```bash
   python3 scripts/build_bundles.py
   ```

3. Deploy the ConfigMaps — either manually:

   ```bash
   cd release
   helmfile apply
   ```

   or via ArgoCD (same pattern as
   [datahub-local-secrets](https://github.com/datahub-local/datahub-local-secrets);
   the repo-server's `helmfile` plugin renders the release). One-time setup, after
   this folder is merged to `main`:

   ```bash
   kubectl apply -f - <<EOF
   apiVersion: argoproj.io/v1alpha1
   kind: Application
   metadata:
     name: datahub-local-ai-superset
     namespace: automation
   spec:
     project: namespace-automation
     source:
       repoURL: https://github.com/datahub-local/datahub-local-ai.git
       targetRevision: HEAD
       path: "workflows/superset/release/"
     destination:
       server: "https://kubernetes.default.svc"
       namespace: "data"
     syncPolicy:
       automated: {}
       syncOptions:
         - CreateNamespace=true
         - ServerSideApply=true
   EOF
   ```

   From then on every push to `main` deploys automatically. The sidecar picks the
   change up on its next sync cycle (default 60 s).

Per-bundle sidecar annotations (`tags`, `certified-by`, `publish`) are configured
in `release/values/default.yaml.gotmpl` under `superset_dashboards.<project>`.

## Conventions

- Every object (database, dataset, chart, dashboard) carries a stable `uuid` —
  the sidecar and Superset use them as identity across re-imports. Never reuse or
  regenerate them once deployed.
- Bundles ship their own database entry with a project-prefixed name
  (e.g. `Bodega - Trino Gold`) instead of reusing the shared `trino-*`
  connections provisioned by datahub-local-core, so imports never collide with
  externally managed connections (same pattern as core's `sample` dashboard).
- Chart `slice_name`s are prefixed with the project name (`Bodega - ...`) so they
  are recognisable in Superset's global chart list.

## Projects

- [`bodega`](projects/bodega/) — five-tab household grocery analytics dashboard
  over the bodega dbt gold layer.
