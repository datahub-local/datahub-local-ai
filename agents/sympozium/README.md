# Sympozium agents

Agent definitions for the [Sympozium](https://github.com/sympozium-ai/sympozium)
control plane that [datahub-local-core](https://github.com/datahub-local/datahub-local-core)
deploys into the `automation` namespace, plus a Helm release that ships them.

Core owns the *platform* — the controller, API server, NATS, the MCP server
catalog, the SkillPacks and the policies. This sub-project owns the *agents*:
what they are told to do, when they run, and what they are allowed to touch.

The unit of deployment is an **Ensemble** — a team of personas. Installing one
stamps out an `Agent` and a `SympoziumSchedule` per persona and seeds their
memory. Ensembles default to disabled in the CRD ("catalog-only"), so a manifest
that does not say `enabled: true` deploys but never runs.

## Layout

The chart root **is** this directory. Helm's `.Files` cannot read above the chart
directory, and the templates read `projects/` directly, so there is no `release/`
subdirectory here — unlike `workflows/superset/`, which needs a build step
because its bundles are binary zips. Nothing is generated into the repository.

```
agents/sympozium/
  Chart.yaml
  helmfile.yaml.gotmpl
  values/default.yaml.gotmpl   per-cluster knobs: enabled, baseURL, policyRef
  templates/ensembles.yaml     assembles one Ensemble per projects/<name>/
  projects/
    <ensemble>/
      ensemble.yaml            team-level spec, plus the `defaults:` stamped
                               onto each persona
      agents/
        <persona>.yaml         one persona: skills, schedule, MCP servers, tool
                               policy, memory seeds — prompts by reference
      prompts/
        <persona>_system.md    -> agentConfigs[].systemPrompt
        <persona>_task.md      -> agentConfigs[].schedule.task
  scripts/
    validate.py                field checks Go templates cannot do
```

## Workflow

1. Edit anything under `projects/<ensemble>/`.
2. Validate and preview (from the repository root):

   ```bash
   uv sync --extra sympozium
   uv run python agents/sympozium/scripts/validate.py
   cd agents/sympozium && helm template datahub-local-ai-sympozium . \
     -n automation -f values/default.yaml.gotmpl
   ```

3. Deploy — either `helmfile apply` from `agents/sympozium/`, or let ArgoCD sync
   it. Note the two `ignoreDifferences` entries: the Sympozium controller writes
   back `memory.maxSizeKB` and `schedule.firstTick`, so without them every sync
   shows permanent drift.

   ```bash
   kubectl apply -f - <<EOF
   apiVersion: argoproj.io/v1alpha1
   kind: Application
   metadata:
     name: datahub-local-ai-sympozium
     namespace: automation
   spec:
     project: namespace-automation
     source:
       repoURL: https://github.com/datahub-local/datahub-local-ai.git
       targetRevision: HEAD
       path: "agents/sympozium/"
     destination:
       server: "https://kubernetes.default.svc"
       namespace: "automation"
     syncPolicy:
       automated: {}
       syncOptions:
         - CreateNamespace=true
         - ServerSideApply=true
     ignoreDifferences:
       - group: "sympozium.ai"
         kind: "Ensemble"
         jqPathExpressions:
           - ".spec.agentConfigs[]?.memory.maxSizeKB"
           - ".spec.agentConfigs[]?.schedule.firstTick"
   EOF
   ```

With a cluster reachable, `kubectl apply --dry-run=server` on the rendered output
checks it against the real CRD schemas and the admission webhook — worth doing
before committing, since rendering is the only build step there is.

## The ensembles

Between them the six personas cover what an IT crew covers: on-call, hardware,
database administration, backup continuity, configuration management and change
management. They are split into two ensembles on a trust boundary rather than by
subject — everything read-only lives in one, and the single agent that can write
anywhere at all lives in the other.

### `homelab-ops` — read-only, no write tool of any kind

| Persona | Schedule (UTC) | What it answers | MCP surface |
| --- | --- | --- | --- |
| `sre-sentinel` | heartbeat, 30m | What is firing, and why? | `grafana`, `k8s` |
| `gitops-auditor` | sweep, 1h | Does the cluster match what git says? | `argocd` |
| `endpoint-warden` | daily 04:30 | Are the machines themselves degrading? | `grafana`, `k8s` |
| `db-steward` | daily 05:30 | Are Postgres and Valkey healthy and roomy? | `pg`, `grafana`, `k8s` |
| `service-janitor` | Mon 05:00 | Is the homelab recoverable? What is expiring? | `k8s`, `grafana` |

Each persona is **one question with five to seven tools**. That is the whole
reason there are five of them rather than three fatter ones — see
[the model constrains the design](#the-model-constrains-the-design). A persona
carries exactly one schedule in the CRD, so "same agent, different focus on a
different day" is not expressible; it has to be another persona.

### `homelab-reviewer` — the only write surface

| Persona | Schedule (UTC) | What it answers | MCP surface |
| --- | --- | --- | --- |
| `renovate-reviewer` | Mon–Fri 06:00 | Is this bump safe, and what does migrating cost? | `github`, `argocd` |

Its one write tool is `github_add_issue_comment`. Merging, pushing, approving
and branch creation are denied at the server edge, not merely left out of the
allowlist. That comment is also the only notification path there is — a
`DO NOT MERGE` verdict on the PR *is* the alert, since no Slack channel is
wired.

## Conventions

- **Prompts are never inlined.** A persona references `prompts/*.md`; the
  validator fails if `systemPrompt` or `schedule.task` appears literally. Same
  reasoning as `agents/n8n/prompts/` — a 40-line instruction buried in a YAML
  block scalar is not reviewable.
- **Names are DNS-1123.** Ensemble and persona names become Kubernetes object
  names, so they are kebab-case (`sre-sentinel`), not the `snake_case` used for
  project directories elsewhere in this repo. Prompt *files* stay `snake_case.md`
  to match `agents/n8n/`. The validator enforces both, and that a persona's
  `name` matches its file name — and the templates re-check the name/filename
  match, since a mismatch there would produce the wrong object.
- **Nothing is generated into the repository.** `templates/ensembles.yaml` is
  the build step: it reads `projects/` at render time, so the sources are the
  only copy of anything. There is no committed manifest to fall out of date with
  its source, and no rebuild to forget. The cost is that a pull request shows the
  prompt as Markdown rather than the assembled CR — run `helm template` to see
  what the cluster will actually get.
- **Source describes the agent; values describe the cluster.** Prompts, skills,
  schedules and tool policy live in `projects/`. Only `enabled`, `baseURL` and
  `policyRef` — the three things that could legitimately differ between clusters
  — live in `values/default.yaml.gotmpl`, merged over `spec` at render time. The
  validator rejects those keys in `ensemble.yaml`.
- **`toolPolicy` is prefixed, `toolsDeny` is not.** `toolPolicy.allow` lists
  agent-facing names (`k8s_pods_list`), because that is what the model sees.
  `mcpServers[].toolsDeny` lists the server's own names (`pods_delete`), because
  that filter runs at the server. Getting this backwards produces a deny that
  matches nothing — see below. The build script checks both directions.
- **Schedules are UTC.** No Sympozium CRD has a timezone field, unlike the n8n
  workflows which set `Europe/Madrid` explicitly. Every cron here is written in
  UTC with the local time in a comment, and shifts by an hour twice a year.
- **Read-only by default.** Every persona denies `write_file` and
  `execute_command`. `execute_command` is a shell; with the MCP servers wired it
  is also redundant.

## The model constrains the design

Inference is the cluster-local Ollama that core deploys, on one 6 GiB RTX 3060
Laptop (`datahublocal-amd-2`) holding a single resident model. That is not a
footnote; it shapes most of the choices here.

The model is `qwen3.5:4b` — 3.16 GiB of weights, so essentially the same VRAM
footprint as the `gemma4:e2b-it-qat` it replaced, for roughly double the
parameters. It is a hybrid-attention model: its GGUF reports
`full_attention_interval = 4` and `head_count_kv = [0,0,0,4, …]`, meaning only
8 of 32 layers keep a growing KV cache, at ~32 KiB/token — about 4.5× cheaper
than a uniform-GQA model of the same size. That is what makes a useful context
affordable on 6 GiB, but it does not stretch to Gemma's 131k: the context is set
to 32768, which is far more than any of these runs needs.

- **`workflowType: autonomous`, not `delegation`.** Delegation needs a model
  that reliably emits `delegate_to_persona` calls with a coherent payload. At
  this size it would fail quietly and often, so each persona runs on its own
  schedule instead. The relationship graph and `stimulus` are unused for now.
  Worth revisiting now that the model is a 4B rather than a 2B — but revisit it
  by testing, not by assuming.
- **Breadth comes from more personas, not fatter ones.** Five to seven tools per
  persona in `homelab-ops`, and one question per run. Handing a small local model 60
  Grafana tools is how you get an agent that calls none of them; handing it a
  fourteen-item checklist is how you get an agent that does the first three
  items and writes a confident summary. `renovate-reviewer` is the deliberate
  exception at twelve tools, because its job is inherently multi-source.
- **Alert noise has to be seeded, not discovered.** Eighteen alert series were
  firing when this was written, nearly all chronic — including
  `KubeSchedulerDown` and `KubeControllerManagerDown`, which are artifacts of
  k3s embedding both components in the server process with no separate metrics
  endpoint. A small model has no way to work that out, so the known-chronic set
  lives in `sre-sentinel`'s memory seeds and its report is shaped as
  new / still firing / resolved. Re-seed when the chronic set changes.
- **Two skills per persona.** SkillPacks mount Markdown into the run, and every
  page competes with the actual task for attention.
- **Metric names are verified, and the prompts name them.** Every metric quoted
  in a prompt was confirmed present in this Prometheus. A small local model will
  not recover from guessing `valkey_memory_used_bytes` when the exporter publishes
  `redis_memory_used_bytes`, so the prompts spell out the real names and tell the
  agent to call `grafana_list_prometheus_metric_names` rather than try a variant.
- **`runTimeout: 30m` (45m for the reviewer).** The 10-minute default is not
  enough for a multi-tool sweep at local-model speed.
- **Staggered schedules, and `firstTick: afterInterval`.** One GPU with one
  resident model means concurrent runs queue behind each other. Nothing is
  hourly-or-faster except the sentinel and the auditor, and enabling all five at
  once does not fire five cold runs at deploy time.
- **Rigid prompts.** Every prompt names the tools to call, in order, and ends
  with a required section layout and a "no report, no run" rule. This mirrors
  what the upstream chart's own examples do, and matters more the smaller the
  model is.

Swapping in a hosted model later is a `baseURL` change plus an `authRefs`
secret; the prompts and allowlists would then be worth loosening.

## Why the `permissive` policy

Both ensembles bind `policyRef: permissive`, which looks wrong until you read
the three built-in `SympoziumPolicy` objects:

| Policy | `networkPolicy.denyAll` | `toolGating.defaultAction` |
| --- | --- | --- |
| `permissive` | `false` | `allow` |
| `restrictive` | **`true`** | `deny` |
| `network-isolated` | **`true`** | `allow` (but `fetch_url` denied) |

`restrictive` and `network-isolated` both deny all egress except DNS and the
event bus, and neither declares `allowedEgress`. Binding either would cut the
agents off from Ollama *and* from every MCP server — the fleet would fail to do
anything at all. `restrictive` additionally gates tools deny-by-default against
a rule list that knows only built-in tool names, so every MCP tool would be
denied, and it requires a sandbox runtime class that is not enabled here.

So restriction is enforced where it is actually reviewable — the per-persona
`toolPolicy` allowlists and `mcpServers[].toolsDeny` in `projects/` — rather
than by a cluster policy that would break connectivity. A hardened policy is
still the better end state: it needs a custom `SympoziumPolicy` with
`denyAll: true` plus explicit `allowedEgress` entries for Ollama and the five
MCP services. Worth doing, but `allowedEgress` takes a `host`, and whether the
controller can turn a Kubernetes service DNS name into a NetworkPolicy peer
needs verifying before anything depends on it.

## Tool names are not guessable

The tool names in this repo were read off the running MCP servers with a
`tools/list` call, not inferred from documentation, because guessing them
silently disarms the thing you were trying to configure. Two live examples, both
in core's `releases/automation/templates/sympozium_mcp_servers.yaml`:

- The k8s server denies `delete_resource`, `create_resource` and
  `update_resource`. `kubernetes-mcp-server` actually exposes
  `resources_create_or_update`, `resources_delete`, `resources_scale`,
  `pods_delete`, `pods_exec` and `pods_run`. **None of the three denies match
  anything, so that server is fully write-capable today.**
- The postgres server denies `execute_write_query`. `postgres-mcp` exposes a
  single `execute_sql` tool and defaults to unrestricted access mode, so writes
  are available there too.

Both are core's to fix. Until they are, the personas here re-deny the real names
themselves, which is why `service-janitor` carries an explicit
`toolsDeny: [execute_sql]` and every k8s consumer repeats the six write tools.
When re-checking, port-forward the server and call `tools/list` — every MCP image
in the catalog is pinned to `:latest`, so the inventory can change under you.

## What the agents can see, and what they cannot

Everything the personas are told to query was checked against this cluster's
Prometheus before it went into a prompt. Two things worth knowing:

Instrumented here and genuinely valuable, which is why the warden leans on them:
**PSI** (`node_pressure_{cpu,io,memory,irq}_{waiting,stalled}_seconds_total` — how
long tasks were actually blocked, which is what "the machine feels slow" means),
**SMART** and **UPS** via the textfile collector (`smartmon_*`,
`network_ups_tools_*`, produced by core's privileged `node-exporter-textfiles`
sidecar into `/var/lib/node_exporter/{smartmon,nutmon}.prom` — currently on four
of the seven nodes; `datahublocal-orpi-0`, `datahublocal-amd-2` and
`datahublocal-nas` report neither, which the warden is seeded to flag rather than
excuse), **EDAC** memory-error counters, and `kubelet_volume_stats_*` for per-PVC
fill.

Not instrumented, so no prompt pretends to check them:

| Wanted | Missing | Where the fix goes |
| --- | --- | --- |
| systemd unit state — "services running badly in the OS" | node-exporter's `systemd` collector is off, so `node_systemd_unit_state` does not exist | core, `releases/monitoring/values/kube-prometheus-stack.yaml.gotmpl` |
| pending OS package updates | no update script in the textfile sidecar | the `node-exporter-textfiles` image, plus core's `SCRIPTS` env |
| S3 capacity | Garage exports no metrics and is not scraped | core, a ServiceMonitor — meanwhile the janitor reads its PVCs |
| repo-level CI history | the GitHub MCP server ships no Actions/workflow tools | upstream `mcp/github`, or a different server |

Standing in for systemd, `endpoint-warden` checks the node's *Kubernetes* system
workloads instead — `kube-system` and `monitoring` pods grouped by node. On a k3s
box that is most of what systemd would have told you, and there is already
something to find: the node-exporter pods themselves carry 4–16 restarts.

### Follow-ups to share with the other repos

Four changes to `datahub-local-core`'s
`releases/monitoring/values/kube-prometheus-stack.yaml.gotmpl` would close the
gaps above and remove two false alerts. They are written up as a ready-to-hand-off
prompt in [`docs/core_monitoring_followup.md`](../../docs/core_monitoring_followup.md)
rather than applied here:

1. **Disable the k3s phantom components** — `kubeScheduler.enabled: false`,
   `kubeControllerManager.enabled: false` and the matching `defaultRules.rules`
   keys. This is what finally silences `KubeSchedulerDown` and
   `KubeControllerManagerDown`; the file already does exactly this for kubeProxy.
2. **OS update counts** — the textfile mechanism here is a *versioned privileged
   sidecar* (`ghcr.io/datahub-local/node-exporter-textfiles`, `SCRIPTS=nutmon.py,smartmon.py`),
   not host cron, so this is an `updates.py` in that image plus one entry in
   `SCRIPTS`. The sidecar mounts no host filesystem, so the script has to enter
   the host mount namespace (`nsenter -t 1 -m`) — the pod already has `hostPID`
   and the sidecar is privileged.
3. **systemd unit state** — `--collector.systemd` plus a `/run/systemd`
   host mount, since the collector dials that socket *inside* the container and
   the existing `/host/root` mount does not satisfy it. Flagged as needing a test:
   a read-only bind mount can block `connect()` on a unix socket.
4. **Re-sync the drifted `extraArgs`** — the override is a stale copy of the
   chart default and is missing the `run/containerd/.+` and `erofs` exclusions
   that 88.3.0 added.

Once 2 or 3 lands, `endpoint-warden` gains the check by adding the metric to its
prompt — no structural change.

## Known gaps

- **No Slack.** `send_channel_message` is allowlisted nowhere, so reports live in
  the agent run history and the Sympozium UI
  (`https://automation-sympozium.<gateway>/auth`). Wiring it needs `slack-auth`
  projected into `automation` by
  [datahub-local-secrets](https://github.com/datahub-local/datahub-local-secrets)
  — today it exists only in `monitoring` — and then `channelConfigs` on the
  ensemble.
- **`endpoint-warden` has no host access.** "Maintaining the machines" is done
  through node-exporter metrics in Grafana, not host mounts, so the agent stays
  unprivileged. Stalls, disk health, temperature, memory errors, power, version
  drift and uptime are all reachable that way; anything genuinely needing the
  host is not in scope.
- **`NodeClockNotSynchronising` is firing on four nodes** as of writing. Nothing
  here fixes it, but `sre-sentinel` will keep reporting it, and clock skew across
  nodes is worth fixing on its own account.
- **Nothing here deletes.** `service-janitor` reports cleanup and prints the
  commands; a human runs them. Auto-cleanup would be a separate, deliberately
  authorised agent.
- **Expiry is split with n8n on purpose.**
  [`credentials_expiry_review`](../n8n/workflows/credentials_expiry_review.workflow.json)
  owns n8n credential expiry, and its dataset documents at length why that date
  lives in the credential's name. `service-janitor` stays strictly cluster-side
  — certificates, tokens, secrets — so the two never contradict each other.
