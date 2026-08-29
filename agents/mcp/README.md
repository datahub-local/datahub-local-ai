# datahub-local-ai-mcp

MCP servers for the Sympozium agents in [`agents/sympozium/`](../sympozium/).

The first and only project, `homelab_facts`, exists to move the *gathering* out
of the model. Every failure in the agent fleet this replaces was a tool-loop
failure rather than a writing failure: a 4B model was made a careful API client,
asked to assemble `100 * (1 - avail/cap)` with a `group_left` join, to remember
that `increase(m[1h])` is not `m[1h]`, to diff alerts against its own memory, and
to know that one node's kernel is not drift against another's. Each incident
added a paragraph to a system prompt and a regex to a validator, and it did not
converge — prompts reached 6–12 KB and roughly 600 lines of validator were
regexes policing English.

**Code gathers; the model writes.**

## Layout

```
agents/mcp/
  src/mcp_runner/          the reusable server
    __main__.py            python -m mcp_runner --project homelab_facts
    server.py              MCP over HTTP: registry, JSON-RPC, /healthz
    prometheus.py          the only module that queries Prometheus
    loki.py                the only module that queries Loki
    fleet.py               deriving hardware classes from the cluster
    kube.py                Kubernetes reads: list, and one bounded log tail
    budget.py              per-tool byte budgets
    render.py, state.py, config.py
  projects/homelab_facts/  the tools and their thresholds
    tools/                 alerts, volumes, nodes, databases, lifecycle, gitops,
                           lookup, diagnose, raw
    config/                chronic_alerts.yaml, thresholds.yaml
  tests/                   127 tests, no cluster required
  Dockerfile               multi-arch: arm64 AND amd64
```

## Commands

Run from the repository root.

```bash
uv sync --extra mcp --extra dev
uv run pytest agents/mcp/tests/ -q
uv run ruff check agents/mcp/

# Print the tool manifest without binding a port
uv run python -m mcp_runner --project homelab_facts --list-tools

# Serve. In-cluster the defaults are right; locally, point at a port-forward.
kubectl -n monitoring port-forward svc/datahub-local-core-kube-pr-prometheus 9090:9090 &
PROMETHEUS_URL=http://127.0.0.1:9090 uv run python -m mcp_runner --project homelab_facts --port 8080

curl -s localhost:8080/healthz
curl -s -X POST localhost:8080/ -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

`PROMETHEUS_URL`, `PROMETHEUS_TIMEOUT_SECONDS`, `LOKI_URL`,
`LOKI_TIMEOUT_SECONDS`, `MCP_STATE_DIR` and `MCP_CONFIG_DIR` are the only
environment variables.

## The tools

Thirteen tools. Nine take **no arguments at all**, and the other four take free
text where any string is valid. Both halves are the same rule: an argument is
safe when there is no format to get wrong. The prompts used to spend 2.3 KB
explaining that `endTime` was the literal word `now`, three characters, and that
the quotation marks around a JSON string are not part of the value; `chatId` had
exactly one correct shape and cost two days of reports.

| Tool | What it replaces |
| --- | --- |
| `find_object(term)` | the exact namespace and name of anything, from the words a person typed — searched three ways over thirteen kinds |
| `why_failed(term)` | the whole investigation: the object, its pods through their own owner references or selector, each container's state, the Warning events, and the log of the container that broke — including its *previous* instance when it is crash-looping |
| `logs(term, contains)` | pod name, container, kubelet-or-Loki fallback, the LogQL selector and the datasource uid |
| `endpoints(term)` | what `curl: (7)` actually means: ready and not-ready endpoint counts, the pods the Service's own selector picks, and any IngressRoute hostname |
| `alerts_snapshot()` | the firing-alert query **plus** the new / still-firing / resolved diff, computed against a stored snapshot, **plus** the chronic classification |
| `volume_fill()` | the full `group_left` expression, already the *used* fraction, already restricted to the storage classes where a percentage means anything |
| `node_fleet()` | the entire node table — disk, stalls, temperature, SMART, uptime, updates, UPS, kernel — with machine identity joined in the query and drift computed within hardware class |
| `postgres_health()` | the archiver **increase**, backends, database sizes, cluster objects |
| `cache_health()` | Valkey via `redis_*`, with no percentage because there is no ceiling to divide by |
| `cert_expiry()`, `backup_freshness()` | dates turned into days and ages, and hundreds of backup objects summarised per schedule |
| `argocd_drift()` | sync/health state plus a consecutive-run counter |
| `promql(expr)` | arbitrary Prometheus, with the datasource, the time and the query type supplied server-side |

They do **not** replace reach. Every persona keeps the raw `k8s_*` tools for
following up on whatever these surface. The win is budget reallocation: the
mandatory readings drop from eight-plus calls to one or two, leaving the
iteration budget for real investigation — which is exactly where the last run
before the teardown ran out and drifted, spending 13 consecutive calls hunting a
namespace that does not exist.

The last three tools in the table extend that from *gathering* to *sequencing*.
`find_object` closed the gap between the word a person types and the string the
API needs; what remained was the chain after it — object, pods, containers,
events, logs — which is four calls of exact arguments in a fixed order, and the
step every failed run here got wrong. Asked the question from the incident
(`grafana setup job`), `why_failed` answers in **one call and 1,651 bytes** with
the Job, its pod, the log line and a verdict; the run it replaces spent eight
calls, guessed a label key in five of them, and concluded that a running grafana
did not exist.

## The four properties that remove failure classes structurally

**1. A wrong query is not expressible.** The expression builders in
`prometheus.py` are the only way to ask. `used_percent()` cannot be written as
the bare ratio; `increase_()` cannot lose its wrapper; `by_nodename()` cannot
drop the join. Each of these was a real report: the bare ratio called a 2%-used
volume "97.9% full, write operations failing" every run for days, and a missing
join produced a node table that was wrong in five ways at once.

**2. Absence is a value, and it has a definition.** `unavailable` means *the
query gave no value for this node*; `n/a` means *this node has no such sensor*.
Two words, because one word absorbed a bug: `unavailable` was introduced so a
missing metric could be stated rather than invented, and it then silently
absorbed a broken join. A mandatory report format that cannot express absence
gets filled with invented numbers — that is how `k8s_nodes_top` memory came to be
relabelled as disk and a 5%-full disk reported as "79% (CRITICAL)".

**3. Every answer is bounded, in code.** "Fat tool" means *few calls*, never *big
answers*. A single ~16 KB tool result reproducibly ends a run with no report at
all: four calls for 24,126 result bytes produced `terminal turn had empty text`,
where five calls for 8,483 bytes the same day wrote a normal report. It is not
context overflow — cumulative input was 25,423 tokens against a 65,536 window. So
each tool declares a budget, truncates by whole lines, and *says* it truncated. A
full nine-reading sweep of this cluster is about 14.7 KB total, and no single
answer exceeds 4 KB — the three investigation tools carry the largest budgets and
were measured against the live cluster at 0.8–4.0 KB.

**4. Trends are measured, not remembered.** The server holds snapshots, so "new
since last run" and "climbed 15 points this week" are computations. A lost
snapshot degrades to "first observation", which every tool states — it can never
produce a wrong diff.

## Nothing about the homelab is written down here

Node names, hardware classes and which machine carries which sensor are all
derived at query time; see `fleet.py`. A checked-in copy of the topology goes
stale silently, and a stale node list produces the exact failure this server
exists to prevent — a row of `unavailable` for a machine whose figures were
available all along.

- **A hardware class is the kernel flavour plus the architecture**, and that is
  not an approximation of the rule, it *is* the rule: kernels are comparable only
  within one tree, so "same flavour" and "comparable" are the same predicate. A
  numeric difference inside a flavour is real drift; a different flavour is
  different silicon and can never converge. Adding, renaming or re-imaging a node
  needs no change here.
- **Sensor coverage is whether the sensor answered.** A capability probe decides
  per node, so moving a disk or adding a UPS needs no change either.
- **The node inventory is the Kubernetes node list**, and comparing it against
  what Prometheus answered is what makes a dropped join legible.

The two files that remain in `config/` are the ones that genuinely cannot be read
off a cluster: `chronic_alerts.yaml` (whether an alert is noise is a judgement,
and it names alert *rules*, never machines) and `thresholds.yaml` (where to draw
a line). Every tool states the threshold it applied, so a report never implies a
judgement the reader cannot check.

## Two properties worth stating

**The server holds no credential.** Prometheus needs no auth on this cluster and
Kubernetes reads go through the pod ServiceAccount. ArgoCD state is read from
`Application` custom resources rather than the ArgoCD API, and Postgres state
from the CloudNativePG operator's metrics rather than a database connection — so
there is no token and no DSN anywhere in this sub-project. Query-level Postgres
analysis stays on the existing postgres MCP server, which already has the
credential for it.

**It cannot return a Secret's contents.** `kube.py` exposes `list` and one
bounded `pod_log`, strips `data`/`stringData` at the boundary, and `cert_expiry()`
narrows its request with a field selector rather than filtering afterwards — an
unfiltered cluster-wide Secret list transfers every value in every namespace,
which on this cluster is 25 MB and broke the connection outright.

The log tail is the one read that can echo a value an application printed itself,
and no boundary here can prevent that — it is a property of logs, not of this
server. It is not a new exposure: every persona already held core's
`k8s_pods_log`, and the oracle no longer does, because `logs()` reads the same
thing with the pod name resolved, the byte count bounded and the source stated.
Secrets and ConfigMaps stay out of `find_object`'s kind list for the separate
reason that a name search over them is credential enumeration.

## Deployment

The chart in `agents/sympozium/` owns the `Deployment`, `Service` and
`MCPServer`. Two details that are load-bearing there:

- The pods **must** carry `app.kubernetes.io/name: mcpserver`, or core's
  `agent-allow-tools` NetworkPolicy blocks port 8080 and every call times out
  with no useful error.
- The `MCPServer` uses the `url:` form, which stops the controller reconciling a
  deployment of its own.
- The ClusterRole is **enumerated, never a wildcard**, so every kind a tool reads
  has to be added to it — `events` and the `pods/log` subresource arrived with
  `why_failed`. A kind the ServiceAccount cannot read is a 403, which
  `KubeForbidden` keeps distinct from an empty list: a lookup that could not run
  must never render as a lookup that found nothing.

The MCP endpoint answers on **every** path, which is deliberate. Core's `mcp-k8s`
404'd for three days with `MCPServer.status.ready: true` throughout, because the
discovery bridge asked for the service root and the server served `/mcp` — every
`k8s_*` tool was missing from every persona for that whole time and nothing
failed loudly. The bridge's path is not documented anywhere readable, so rather
than guess it, any non-health path is the MCP endpoint. After a deploy, read
`kubectl logs <run-pod> -c mcp-discover`: it prints the per-server tool counts,
and a whole server failing is otherwise silent.
