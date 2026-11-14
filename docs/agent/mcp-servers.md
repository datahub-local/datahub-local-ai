# MCP servers

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
- **The timeout budget.** A tool call is bounded by the server's backend timeout,
  the bridge timeout and the Hermes client timeout, in that order of increasing
  patience. The Pod probe is a separate layer: it decides whether the process
  survives, not whether the call completes, which is why it is the layer that
  restarted postgres. The bridge applies `mcpServers[].timeout` on the persona;
  the `MCPServer.spec.timeout` is inherited only when that entry omits one
  (Sympozium `resolveMCPServerURLs`, v0.13.0), so raising the catalog alone
  changes nothing for an agent that states its own value. Every persona states
  the same value as the catalog entry it mounts, and the chart fails the render
  when one is lower. `homelab-facts` is 90s because its name-resolving tools
  list thirteen kinds from the Kubernetes API; the measured p-max was 60.2s, not
  because of its 20s Prometheus and Loki ceilings. The effective values and the
  ordering rule are in
  [`datahub-local-ai-mcp/docs/deployment.md`](https://github.com/datahub-local/datahub-local-ai-mcp/blob/main/docs/deployment.md#timeouts).

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
