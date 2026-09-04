# Semantic registry

One definition per metric, in git, consumed by the `semantic` MCP server in
[`datahub-local-ai-mcp`](https://github.com/datahub-local/datahub-local-ai-mcp).
This directory holds the **definitions**; the code that serves them is there,
and the image carries none of this — it is mounted as the `mcp-semantic`
ConfigMap. Design rationale is in
[`docs/semantic_layer_spec.md`](../../../docs/semantic_layer_spec.md).

It lives here, beside the dbt projects, because every `expr` is a column of a
dbt model and `semantic-compile` resolves it against dbt's own manifest.

```
semantic/
  bodega.yaml   the metrics and the models they read
  PHASE0.md     every number, measured against live Trino
  compile.py    the CI gate. Offline
```

`bodega.yaml` reaches the cluster as a **symlink**,
`agents/sympozium/config/semantic/registry.yaml`, so the chart renders the
ConfigMap from this file and nothing is generated or committed twice. It is the
only key that mount carries: table names, documented columns, cardinality and
dimension values are all read live from Trino by the server.

## Commands

```bash
# The gate. Runs dbt parse, validates, stamps registry_version. No warehouse.
uv run python semantic/compile.py --project bodega

# The ConfigMap is rendered by the chart from the symlink; there is nothing to
# build. Deploying a definition change is a sync plus a pod restart, because
# the server loads the registry once.
```

## Rules the gate enforces

Every one of them fails the build, and all problems are reported at once rather
than one per run.

- **`excludes` is mandatory.** A metric that does not state what it leaves out
  cannot be audited, and writing the exclusion is what surfaces a disagreement
  between two metrics before a dashboard does.
- **Every `expr` is a bare column that dbt builds.** This is the G3 gate:
  renaming a gold column without updating the registry fails CI. It works only
  because `invoices`, `invoice_items` and `category_spending` document *all*
  their columns in `models/schema.yml` — dbt's manifest carries documented
  columns only, so an undocumented column is indistinguishable from a missing
  one. Adding a measure over a new column means documenting that column too.
- **No SQL fragment may appear in an `expr`.** Anything the compiler cannot
  validate is rejected outright.
- **No `avg`/`min`/`max` over a `pre_aggregated: true` model.** `total_spent` in
  `category_spending` is already a `SUM`; averaging it is the mean of daily sums,
  which answers nothing anyone asked. A type check cannot catch this — the column
  is a perfectly ordinary double.
- **No metric spanning two models** without a declared join, which v1 does not
  have. The error names both models rather than the compiler guessing a path.
- Unique metric names; `grain_min` no finer than the model's time granularity.

## Adding a metric

1. Check the column exists **and is documented** in the dbt project's
   `models/schema.yml`.
2. Add the measure to the right `semantic_models` entry, then the metric.
3. Write `excludes` before anything else. If you cannot say what it leaves out,
   the definition is not ready — that is the point of the rule, not an obstacle
   to it.
4. `uv run python semantic/compile.py` until green.
5. Hand-run the SQL `explain` produces against Trino and record the number in
   `PHASE0.md`. A metric nobody has ever checked against the warehouse is a
   guess with a schema.

## Read PHASE0.md before changing a measure

Two definitions in `bodega.yaml` are shaped by a measurement that contradicted
the original design, and both look wrong without that context:

- `blended_unit_price_eur` reads `invoice_items` and **not**
  `gold.bodega.price_trends`, because that model's `HAVING COUNT(*) >= 2` drops
  208 of 428 products and 12.9% of spend.
- `grocery_spend_eur` and `category_spend_eur` were predicted to disagree and
  measured **equal to the cent** — so their `excludes` say "equal today, not
  equal by construction" rather than repeating a difference that does not exist.
