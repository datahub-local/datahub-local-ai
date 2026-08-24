# Sympozium memory

Working notes for `agents/sympozium/`: why each knob is set the way it is, and
what broke when it was set otherwise.

**This file is where that reasoning goes.** Not in comments in the YAML, and not
as another section of `README.md`. The split is: config files carry values,
`README.md` carries the structure and the runbooks — what is here, how to build
and deploy it, the conventions, how to test an agent — and this file carries
every *why*, including all of the incidents. A note here should be short enough
that the next person reads all of it.

Two rules for writing here:

- **One statement, one place.** The `toolsAllow` note below was copy-pasted into
  nine persona files and the `grafana_list_datasources` note into four. Nine
  copies drift; one does not.
- **Say what was measured, with the date.** A claim with a number and a date can
  be re-checked later. "This is slow" cannot.

---

## Where things live

| What | Where | Why |
| --- | --- | --- |
| Values only, no rationale | `projects/*/ensemble.yaml`, `projects/*/agents/*.yaml`, `values/default.yaml.gotmpl` | A comment restating a decision is a second copy of it |
| Structure, conventions, runbooks, how to test | `README.md` | Reference you read before doing something |
| Every *why* — knob rationale, per-persona decisions, incidents | this file | Read when something surprises you |
| Agent behaviour | `projects/*/prompts/*.md` | The model only reads the prompts |
| Machine-checkable rules | `scripts/validate.py` | A convention nothing enforces is a suggestion |

`values/default.yaml.gotmpl` has one trap worth keeping in mind before editing
it: helmfile renders the file as a Go template **including its comments**, so a
literal `{{ ... }}` brace pair anywhere in it — even commented out — is a
template action and an undefined function. Writing a token name with its braces
in a comment there broke the ArgoCD CMP once. Name tokens without braces.

---

## Knobs that repeat across every persona

These were the same comment pasted into every file. They are properties of the
platform, not of any one agent.

- **`mcpServers[].toolsAllow` mirrors `toolPolicy.allow` with the server prefix
  stripped.** `toolPolicy` filters at the LLM request but every tool the server
  exposes is still registered and its schema still injected, so `toolsAllow` is
  what bounds context consumption — it runs at the server. `scripts/validate.py`
  fails on any drift between the two. Full measurements in
  `#the-tool-schemas-not-the-report-are-what-fills-the-context`.
- **`mcpServers[].toolsDeny` is redundant by construction** now that
  `toolsAllow` pins the surface. The lists are kept only as a record of which
  write-tool names are real, verified against a live `tools/list`. They are not
  the enforcing mechanism.
- **`grafana_list_datasources` is deliberately absent everywhere.** It was
  allowlisted so the Prometheus uid would not be a hardcoded guess, and it made
  one: the model read the list, preferred Loki's hex uid over the literal
  `prometheus`, and every query answered `404 page not found`. The datasource is
  provisioned `readOnly` by kube-prometheus-stack, so the uid is a stable literal
  and belongs in the prompt. `scripts/validate.py` enforces both halves.
- **`schedule.firstTick: afterInterval`, stated rather than left to default.**
  Two reasons at once: the CRD carries a `default:` so an omitted value is
  written in at admission and ArgoCD reports permanent drift, and `immediate`
  would queue every enabled persona's cold run behind the others on a
  single-GPU Ollama.
- **Every CRD-defaulted field is written out** for that same drift reason —
  `mcpServers[].timeout`, `schedule.firstTick`, `memory.maxSizeKB`,
  `sharedMemory.storageSize`. Re-derive the list after a control-plane bump:
  `kubectl get crd ensembles.sympozium.ai -o json | jq '.. | objects | select(has("default"))'`.
- **Schedules are UTC.** No Sympozium CRD has a timezone field, unlike the n8n
  workflows which set `Europe/Madrid` explicitly. Local times are recorded per
  persona below rather than in a comment beside each cron.
- **`MAX_TOOL_ITERATIONS: "100"`** in both ensembles' `defaults:`. The runner
  caps tool calls per run at 50 and hitting it is silent — the run ends
  `status: error`, so the `lifecycle.postRun` delivery hook never fires and
  nothing arrives at all. Five runs have hit it; `endpoint-warden` used 48 of 50
  on 2026-08-24 at 04:30 and failed on 50 at 06:15. Quoted because the CRD types
  `env` as `map[string]string` and the webhook decodes strictly, so a bare `100`
  is rejected at apply time. The real ceiling is the 65536 context every
  accumulated tool result has to fit inside, so this is headroom, not permission
  to sweep wider.

## Ensemble-level decisions

- **`homelab-ops`** — read-only, no write tool of any kind. `workflowType:
  autonomous` rather than `delegation`, because delegation needs a model that
  reliably emits `delegate_to_persona` calls and a 4B local model is not it. Each
  persona is one question with a handful of tools; breadth at this model size
  comes from more narrow agents, not fatter ones. `sharedMemory` is on so the
  personas can see each other's notes — the warden's disk trend explains the
  sentinel's evicted pods — and each keeps private memory too. `runTimeout: 30m`
  against a 10m default, because one 4B model on a single 6 GiB GPU is slow.
- **`homelab-reviewer`** — split from `homelab-ops` on a trust boundary, not on
  subject: it holds the fleet's only write tool (`github_add_issue_comment`), so
  it gets its own policy binding and its own blast radius, visible in the
  directory listing. No shared memory: nothing here needs to be visible to the
  read-only ops team, and a smaller surface is the point of the split.
  `storageSize` is still spelled out under `enabled: false` because the CRD
  defaults it. `runTimeout: 45m` — reading a changelog and a diff is the longest
  job in the fleet.

## Per-persona decisions

Local times are Madrid, which is UTC+2 in summer and UTC+1 in winter.

| Persona | Schedule | Why that cadence |
| --- | --- | --- |
| `sre-sentinel` | heartbeat, 6h | Not the detector — the digest. Alertmanager already routes every alert to Robusta (`severity =~ ".*"`, `group_wait 1s`) and Robusta posts to Slack, so this agent adds new-vs-chronic, root cause, and the volume fill check no alert rule covers. At 30m with unconditional delivery it was 48 messages a day restating Robusta. |
| `endpoint-warden` | `30 4 * * *` | 04:30 UTC = 06:30 Madrid summer, 05:30 winter. |
| `service-janitor` | `0 5 * * *` | 05:00 UTC = 07:00 Madrid summer, 06:00 winter. |
| `db-steward` | `30 5 * * *` | 05:30 UTC = 07:30 Madrid summer. Half an hour after the warden so the two do not contend for the GPU. |
| `gitops-auditor` | every 4h | Nothing else watches ArgoCD sync state — Robusta forwards Kubernetes events and Prometheus alerts, not drift — so this is the only source. 4h still gives its "drift that survives two consecutive runs" rule an 8h window to confirm against, at a sixth of the message volume. |
| `renovate-reviewer` | `0 6 * * 1-5` | 06:00 UTC weekdays = 08:00 Madrid summer, 07:00 winter. Daily, not hourly: a 4B model re-reviewing the same PR every hour is noise, and it would hold the GPU against the four ops agents. |

Other per-persona notes:

- **`sre-sentinel` is the ensemble's only `channels: [slack]` binding, and it is
  inbound only** — delivery is a `postRun` hook. It exists so an @-mention lands
  on a known persona instead of whichever of five sidecars Socket Mode happened
  to hand the event to.
- **`sre-sentinel`'s memory seeds are the known-chronic alert set**, re-verified
  against `ALERTS` on 2026-08-22. Without them the agent reports the same firing
  series forever. A seed is a list of what to *ignore when observed*, never
  evidence that something was observed, which is why each one says so.
- **`db-steward`'s postgres server denies `execute_sql`** — the one
  write-capable tool on that server, and postgres-mcp defaults to unrestricted
  access mode. The `analyze_*` tools answer everything the agent needs.
- **`db-steward` came out of `service-janitor`** when the role grew a second tool
  surface. A persona carries exactly one schedule, so "same agent, different
  focus on a different day" is not expressible — it has to be another persona.
- **`gitops-auditor` needs no `toolsDeny`**: the ArgoCD MCP server exposes no
  write tools at all, unlike the k8s and github servers.
- **`renovate-reviewer`'s `add_issue_comment` is denied at the server edge for
  every other write**, not merely left out of the allowlist. It also reaches
  outside the cluster, because upstream release notes and changelogs live there.
- **`service-janitor` stays strictly cluster-side** (certificates, tokens,
  secrets). `agents/n8n/workflows/credentials_expiry_review` owns n8n credential
  expiry; check the n8n workflows before giving a Sympozium agent a job.

---

## `values/default.yaml.gotmpl` — the per-cluster knobs

Only settings that could legitimately differ between clusters belong here.
Everything describing *what an agent is* — prompts, skills, schedules, tool
policy — lives in `projects/` and is read from there at render time.
`scripts/validate.py` rejects a values-only key that appears in `ensemble.yaml`
and vice versa.

Chart-only trees (`sympozium_delivery`, `sympozium_delivery_hook`,
`sympozium_web_endpoint`) are deliberately kept *outside* `sympozium_ensembles`,
because everything under that tree is merged into the Ensemble spec and the CRD
webhook decodes strictly — an unknown key is rejected outright
(`unknown field spec.verbosity`), not pruned.

**Delivery.** Channels are split by what a reader would do about the message, not
by which agent produced it, because a channel is really one notification setting:

| Channel | Carries | Notifications |
| --- | --- | --- |
| `#monitoring-ai-health` | the daily and weekly personas — hardware, databases, weekly cleanup | scan-later, can be off |
| `#monitoring-ai-alerts` | `sre-sentinel` | on |
| `#monitoring-ai-drift` | `gitops-auditor` | on |

Keeping the two frequent personas out of `-health` is what lets `-alerts` keep
notifications on without the daily hardware report training you to mute it.
`homelab-reviewer` is absent on purpose: it is bound to no channel and its
DO NOT MERGE comment on the pull request is the alert.

`verbosity` and `notify` are absent everywhere, and `validate.py` rejects them on
a hook-mode persona. A hook posts the run's own result unconditionally, so
neither knob can do anything — they described how the model should call the
posting tool and when to stay quiet, and there is no longer a call and no
suppression. The cost is real: every report arrives every run. Stretch
`schedule.interval` if a channel gets too busy; do not reach for `notify`.

`sympozium_delivery_hook` pins the container that does the posting —
`curlimages/curl:8.11.1`, reading `SLACK_BOT_TOKEN` from the `mcp-slack-token`
Secret by reference so no token appears in the chart.

**`channelConfigs`.** Channel type to the Secret holding its credentials. The
controller sets `ConfigRef` on every generated Agent whose agentConfig lists the
type in `channels`, so a persona bound to a type with no entry here binds to
nothing at all. A secret name is a property of the cluster, which is why it lives
here and is rejected in `ensemble.yaml`. `mcp-slack-token` is projected into
`automation` by datahub-local-secrets and carries `SLACK_BOT_TOKEN` (outbound
`chat:write`) and `SLACK_APP_TOKEN` (Socket Mode, the inbound half). Until it
appeared the only Slack secret in this cluster was `slack-auth` in `monitoring`,
which is why nothing could notify.

**`baseURL`.** Cluster-local Ollama, deployed by datahub-local-core
(`releases/data/values/ollama.yaml.gotmpl`). No credentials — provider `ollama`
needs none, which is why no `authRefs` secret appears anywhere in this chart. The
Sympozium NetworkPolicy already allows egress on 11434 (`extraEgressPorts` in
core's sympozium values), and Ollama serves an OpenAI-compatible API under `/v1`.

**`enabled: true` on both ensembles.** Ensembles ship disabled in the CRD
("catalog-only"), so a manifest without it deploys but never runs. All six agents
are wanted here.

**`policyRef: permissive`, deliberately.** See
`#why-the-permissive-policy`. The built-in `restrictive` and
`network-isolated` policies both set `networkPolicy.denyAll`, which would cut the
agents off from Ollama and from every MCP server. Restriction is enforced
per-agent instead, by the `toolPolicy` allowlists and MCP `toolsDeny` lists in
`projects/`.

**`sympozium_web_endpoint.enabled` is a master switch and it stays `false`.** An
endpoint does not sit beside a persona's schedule — it *replaces* it. A serving
`AgentRun` makes the schedule controller skip every tick for that agent
("Skipping trigger — instance has a serving AgentRun") silently: the
`SympoziumSchedule` stays `Active`, no run fails, nothing is emitted. Two ticks
were lost that way on 2026-08-23 before anything noticed. So it is a switch to
flip for the length of a test and flip back — which is why it is one master
switch rather than only the per-ensemble keys: turning the surface on and off
again must not mean editing, and then remembering to restore, the per-agent
decisions under it. For a test that costs no schedule, apply an `AgentRun` by
hand instead. Enabling it appends the `web-endpoint` SkillPack to the persona and
the controller deploys a web-proxy Deployment and ClusterIP Service beside the
agent; the CRD's own `spec.webEndpoint` field is deprecated in favour of the
skill and is deliberately not set anywhere. Routes are
`POST /v1/chat/completions` (OpenAI-compatible), `POST /v1/mcp` (MCP) and
`GET /healthz` (the only route needing no `Authorization` header). No `hostname`
is set, so no HTTPRoute is created and the Service stays ClusterIP. See
`README.md#testing-an-agent-over-http`.

`homelab-reviewer`'s web endpoint is off and not for symmetry:
`renovate-reviewer` is the one persona holding a write tool, and what it writes
lands on a real pull request. A web-triggered run also drops the persona's
`toolPolicy` entirely — see
`#a-web-endpoint-run-drops-the-personas-toolpolicy-entirely`.

---

---

## Incidents and lessons

Migrated out of `README.md`, which now holds the structure and the runbooks.
Order is as it was there: roughly oldest lesson first.

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
affordable on 6 GiB. The window was 32768 until 2026-08-23 and is now 65536,
set by `OLLAMA_CONTEXT_LENGTH` on core's ollama Deployment and paired with
`OLLAMA_KV_CACHE_TYPE=q8_0` to keep the cache on the GPU. Read the effective
value from `GET /api/ps` with the model resident, never from this file and never
from `/api/show`, which reports the architecture's 262144 ceiling instead. See
*The window was then raised to 65536* below for why the tool-surface budget
matters regardless of the number.

- **`workflowType: autonomous`, not `delegation`.** Delegation needs a model
  that reliably emits `delegate_to_persona` calls with a coherent payload. At
  this size it would fail quietly and often, so each persona runs on its own
  schedule instead. The relationship graph and `stimulus` are unused for now.
  Worth revisiting now that the model is a 4B rather than a 2B — but revisit it
  by testing, not by assuming.
- **Breadth comes from more personas, not fatter ones.** Seven to nine tools per
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
  new / still firing / resolved. Re-seed when the chronic set changes: by
  2026-08-22 those two had stopped firing and the set was down to four
  alertnames, which is exactly when a stale seed turns into a fabricated
  observation. Each seed now states that it is a thing to ignore when seen, not
  a thing seen.
- **Editing `memory.seeds` in git does nothing to a running ensemble.** The CRD
  describes seeds as "initial memory entries injected into MEMORY.md", and that
  is literal: the controller writes them once, at install, into
  `ConfigMap/<ensemble>-<persona>-memory` under the key `MEMORY.md`, with no
  `ownerReferences` and no reconcile afterwards. Apply a changed `seeds:` list
  and the Ensemble object updates, the `systemPrompt` and `toolPolicy` on the
  next `AgentRun` update — and the run's `## Memory Context` still carries the
  old text, because it is read from that ConfigMap. Re-seeding a live persona
  means writing the ConfigMap yourself (or deleting the memory and letting the
  agent start over). Verify after any seed change by reading the next run's
  task, not the Ensemble:

      kubectl get agentrun -n automation <run> -o jsonpath='{.spec.task}'
- **Two skills per persona.** SkillPacks mount Markdown into the run, and every
  page competes with the actual task for attention.
- **Metric names are verified, and the prompts name them.** Every metric quoted
  in a prompt was confirmed present in this Prometheus. A small local model will
  not recover from guessing `valkey_memory_used_bytes` when the exporter publishes
  `redis_memory_used_bytes`, so the prompts spell out the real names and tell the
  agent to call `grafana_list_prometheus_metric_names` rather than try a variant.
- **A tool's argument contract is part of its name.** Verifying that
  `query_prometheus` exists was not enough — it also has a required argument its
  own description disclaims, and a 4B model does not recover from a tool that
  errors every call. Call each tool by hand against the live server before
  writing a prompt against it, and put the working argument set in the prompt.
- **A blind agent has to shout.** The failure mode that cost a day here was not
  the broken tool, it was that a broken tool read as good news: "Nothing new." is
  what both a healthy cluster and a dead sensor produce, and `notify: onChange`
  turned that into silence. Every prompt that gates its own delivery needs a rule
  that makes no-data escalate and send, and a rule forbidding it from filling the
  gap with its memory seeds.
- **`runTimeout: 30m` (45m for the reviewer).** The 10-minute default is not
  enough for a multi-tool sweep at local-model speed.
- **Staggered schedules, and `firstTick: afterInterval`.** One GPU with one
  resident model means concurrent runs queue behind each other. Nothing is
  hourly-or-faster except the sentinel and the auditor. The staggering holds for
  the *cron* ticks only — an apply fires a run per persona whatever `firstTick`
  says, which is the next subsection.
- **Rigid prompts.** Every prompt names the tools to call, in order, and ends
  with a required section layout and a "no report, no run" rule. This mirrors
  what the upstream chart's own examples do, and matters more the smaller the
  model is.

Swapping in a hosted model later is a `baseURL` change plus an `authRefs`
secret; the prompts and allowlists would then be worth loosening.

### An apply fires an immediate run per touched schedule

`firstTick: afterInterval` is not the whole story, and the bullet above used to
claim it was. The Ensemble controller reconciles each persona in turn, and every
`SympoziumSchedule` it rewrites starts a run within the same second — no cron
tick involved, `status.nextRunTime` left pointing at tomorrow. Read straight off
the controller on 2026-08-24:

```
07:49:20 controllers.Ensemble           Updating SympoziumSchedule for persona   db-steward
07:49:20 controllers.SympoziumSchedule  Created scheduled AgentRun               homelab-ops-db-steward-schedule-5
07:49:23 controllers.Ensemble           Updating SympoziumSchedule for persona   endpoint-warden
07:49:23 controllers.SympoziumSchedule  Created scheduled AgentRun               homelab-ops-endpoint-warden-schedule-6
```

Two runs, three seconds apart, from one `helmfile apply`. The db-steward schedule
still reported `lastRunTime: 05:30`, `totalRuns: 4`, `nextRunTime: tomorrow
05:30` while `-schedule-5` was running, so the schedule status is no guide to
what is actually executing. The earlier `-endpoint-warden-schedule-5` at 06:15
came from an apply the same way, and it is the run that failed on
`exceeded maximum tool-call iterations (50)`. Three ran at once on 2026-08-23 at
18:53 for the same reason.

So an apply that touches N personas queues N runs against one GPU. Ollama serves
**one request at a time** here — verified from its own log, where every task in
the window landed on `id 0` and no second slot exists, because
`OLLAMA_NUM_PARALLEL` is unset and the deployment only sets
`OLLAMA_CONTEXT_LENGTH=65536`, `OLLAMA_FLASH_ATTENTION=1`,
`OLLAMA_KV_CACHE_TYPE=q8_0`. What that costs is latency and cache thrash, not
correctness: the two conversations alternate on the one slot, each request
evicting the other's prefix, and the GIN timings against the slot timings show
roughly 12 s of pure queue wait on a 3 s call. Every request still returned `200`
with `truncated = 0` and `n_ctx_slot = 65536`.

Two things follow.

- **Do not raise `OLLAMA_NUM_PARALLEL` to fix the queueing.** llama.cpp divides
  `n_ctx` across the slots, so two slots would give each run 32768 — the exact
  window that used to truncate a prompt from the front and lose the persona and
  the report format. Serialised and correct beats parallel and truncated on a
  6 GiB GPU.
- **Apply once, and expect the fleet to run.** Repeated applies while iterating
  are what put two agents on the GPU together, and a run started that way is a
  real run: it posts to Slack, it counts against `MAX_TOOL_ITERATIONS`, and it
  writes memory. For a probe, use a hand-applied `AgentRun` instead, which is the
  guidance elsewhere here for other reasons too.

Fixing this upstream means not resetting a schedule's tick on a spec update that
did not change the cron.

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

- The k8s server denied `delete_resource`, `create_resource` and
  `update_resource`, none of which exist — `kubernetes-mcp-server` exposes
  `resources_create_or_update`, `resources_delete`, `resources_scale`,
  `pods_delete`, `pods_exec` and `pods_run`. **Fixed by core on 2026-08-23**: the
  catalog now denies five of those six real names (`resources_scale` is the one
  left out, and the personas here deny it themselves).
- The postgres server denies `execute_write_query`. `postgres-mcp` exposes a
  single `execute_sql` tool and defaults to unrestricted access mode, so **this
  one is still open** and that server remains write-capable to any agent that
  wires it.

Neither was ever exploitable here, because the personas re-deny the real names
themselves — `service-janitor` carries an explicit `toolsDeny: [execute_sql]` and
every k8s consumer repeats the write tools. That is the point: a per-persona deny
is what made a broken catalog harmless, and it is why the denies stay even now
that [`toolsAllow` makes them redundant by construction](#the-tool-schemas-not-the-report-are-what-fills-the-context).

The three servers with *no* catalog denies at all — github, argocd, grafana —
are the same exposure with none of the noise: `mcp-github` publishes
`merge_pull_request` and `push_files`, `mcp-grafana` publishes
`grafana_api_request`, which reaches the whole Grafana API. Again harmless only
because of what `projects/` denies. When re-checking, port-forward the server and
call `tools/list` — every MCP image in the catalog is pinned to `:latest`, so the
inventory can change under you.

## What the agents can see, and what they cannot

Everything the personas are told to query was checked against this cluster's
Prometheus before it went into a prompt. Two things worth knowing:

Instrumented here and genuinely valuable, which is why the warden leans on them:
**PSI** (`node_pressure_{cpu,io,memory,irq}_{waiting,stalled}_seconds_total` — how
long tasks were actually blocked, which is what "the machine feels slow" means),
**SMART** and **UPS** via the textfile collector (`smartmon_*`,
`network_ups_tools_*`, produced by core's privileged `node-exporter-textfiles`
sidecar into `/var/lib/node_exporter/{smartmon,nutmon}.prom`), **EDAC**
memory-error counters, and `kubelet_volume_stats_*` for per-PVC fill.

SMART coverage is uneven, and the shape of it matters more than the headline: as
of 2026-08-22 the sidecar publishes `smartmon_*` on all seven nodes, but only
four carry actual health data — `datahublocal-amd-1` and `datahublocal-amd-2`
(two NVMe devices each), `datahublocal-orpi-0` (one) and `datahublocal-nas`
(four). On `datahublocal-orpi-1`, `-2` and `-3`, and on amd-2's nine `/dev/sd*`
iSCSI volumes, every device reports `smartmon_device_smart_available 0`: SD/eMMC
and iSCSI cannot answer a SMART query at all. That is the hardware, not a missing
exporter, and the warden is seeded to say so rather than file it as a gap every
run. `network_ups_tools_*` exists on `datahublocal-nas` alone because that is
where the UPS is plugged in — one UPS reporting normally, not six nodes missing
an exporter.

An earlier version of this section had all three of those backwards, and nothing
caught it for a day, because the agent that would have noticed could not read
Prometheus at all — see the next section.

## `send_channel_message` takes the destination in `chatId`, not `channel`

The same class of bug as the
[`query_prometheus` argument contract](README.md#the-query_prometheus-argument-contract),
found the same way, and
it cost every scheduled report for two days. The tool's signature is:

    channel: "slack"                 the *transport* — whatsapp, telegram,
                                     discord, slack. Never a #name.
    chatId:  "#monitoring-ai-alerts" the destination. Nothing else carries it.
    text:    the message
    threadId:                        optional, a Slack thread_ts

The first version of `prompts/delivery/*.md` said "post the finished report to
the Slack channel `#monitoring-ai-alerts` with `send_channel_message`", so the
model put the channel name in `channel` and left `chatId` unset. `chatId` unset
means "the device owner (self-chat)", and the tool answers
`Message sent to #monitoring-ai-alerts channel (target: owner (self))` either
way — it validates nothing and it is the last thing the agent hears about the
send.

What happens after that is asynchronous and out of the agent's sight. The
outbound event reaches the `channel-slack` Deployment, which calls
`chat.postMessage` with an empty channel and gets `channel_not_found`, logged
only there:

    kubectl logs -n automation deploy/homelab-ops-sre-sentinel-channel-slack

Two observable symptoms, both of which read as success:

- A scheduled run ends `**Report delivered successfully to
  #monitoring-ai-alerts Slack channel.**` and nothing is in the channel. The
  model is not lying; it is repeating what the tool told it.
- A run started from Slack has an owner, so the report *does* arrive — as an
  unattributed status block in the app's own direct message, with nothing to say
  which of six agents wrote it. That is what `{{ AGENT }}` in
  `prompts/delivery/header.md` is for.

Verified by three throwaway `AgentRun`s against the live sre-sentinel: with
`chatId` omitted the sidecar logs `channel_not_found` within seconds, with
`chatId` set it logs nothing and the message lands. The sidecar logs only
failures, so silence there is the success signal.

The fix is in the shared prompts, not in a persona: all three verbosity files
name both arguments and explain the failure, and `scripts/validate.py` fails if
a verbosity file stops mentioning `chatId`. There is nothing to set on the CRD —
no Sympozium field carries a destination, which is why the channel reaches the
agent as prompt text in the first place.

### Naming the argument was not enough — the example's punctuation leaked into it

The fix above stopped `chatId` being omitted and started a second version of the
same failure, which held for another two days. The verbosity files showed the
call as an indented block of `key: "value"` pairs:

    channel: "slack"
    chatId:  "{{ CHANNEL }}"

and a 4B model reproduces a block like that character for character, quotes and
alignment included. The tool was called with

    chatId = " \"#monitoring-ai-alerts\""

— a leading space and two literal double quotes inside the value. Slack has no
channel by that name, so `chat.postMessage` returns `channel_not_found` exactly
as it did when the argument was missing, and `send_channel_message` again
answers `Message sent`. Reproduced with a throwaway `AgentRun` whose system
prompt used that block shape and no other instruction; the `channel-slack`
Deployment logged

    "msg":"failed to send Slack message","chatId":" \"#monitoring-ai-alerts\"",
    "error":"...channel_not_found"

which is the one place the quotes are visible. The validator's `chatId`-is-named
rule passed the whole time, because the argument *was* named.

So a prompt for a model this size cannot show a value inside syntax the model is
also expected to strip. `prompts/delivery/*.md` now write the arguments bare —

    channel   slack
    chatId    {{ CHANNEL }}

— say outright that nothing may be added around a value, and describe the
punctuation-carrying failure alongside the omitted-argument one.
`scripts/validate.py` rejects a verbosity file that puts `{{ CHANNEL }}` back in
quotes, and the same rule now covers the `datasourceUid` / `queryType` /
`endTime` block in every persona prompt — that block was written the same way
(`queryType: "instant"`) and would have failed identically, as an unparseable
query type rather than a missing channel. The check is deliberately narrow,
naming only the five arguments the prompts spell out, because PromQL in an
indented block legitimately contains quotes (`ALERTS{alertstate="firing"}`) and a
blanket rule would be wrong. The quoted signature at the top of this section is prose for a human
reader and stays as it is; the constraint applies to the prompt files, which are
read by a 4B model with no ability to tell an example's delimiters from its
content.

## Every report arrived five times, and only one agent sent it

Delivery worked, and then it worked five times over. Each `homelab-ops` report
landed in Slack as five byte-identical copies in the same second. The obvious
reading — a model looping on `send_channel_message` — was wrong. The run that
produced them called the tool exactly once:

```console
$ # agent container log, run homelab-ops-sre-sentinel-web-b85dp
tool_call [8]: send_channel_message id=call_umgxdp7k
Wrote channel message: channel=slack chatId=#monitoring-ai-alerts threadId= len=939
token_usage: input=127195 output=1996   # 8 tool calls in total, one of them the send
```

The fan-out is under the agent, in the event bus.
`sympozium.channel.message.send` is a fleet-wide subject, and each
`<instance>-channel-slack` sidecar subscribes to it with its own ephemeral
JetStream consumer whose only filter is the subject. No queue group, no
per-instance filter, five sidecars:

```console
$ kubectl port-forward -n automation svc/nats 8222:8222
$ curl -s 'localhost:8222/jsz?consumers=true&config=true&acc=%24G' | jq -r '
    .account_details[].stream_detail[] | select(.name=="sympozium") | .consumer_detail[]
    | select(.config.filter_subject|test("channel.message.send"))
    | "\(.name) queue=\(.config.deliver_group) delivered=\(.delivered.consumer_seq)"'
EBC5z5Of queue=null delivered=7
iSxqIBaV queue=null delivered=7
49lFB7lw queue=null delivered=7
4e0UIIDh queue=null delivered=7
NYqO80a0 queue=null delivered=7
```

Every one of the five received all seven messages published that day, and every
one called `chat.postMessage`. The sidecar filters on the *transport* in
`data.channel` — that is why a telegram message never lands in Slack — and never
on the sender, which it is handed:

```console
$ # $JS.API.STREAM.MSG.GET.sympozium {"last_by_subj":"sympozium.channel.message.send"}
{"topic":"channel.message.send",
 "metadata":{"instanceName":"homelab-ops-sre-sentinel","namespace":"automation",
             "agentRunID":"homelab-ops-sre-sentinel-web-b85dp"},
 "data":{"channel":"slack","chatId":"#monitoring-ai-alerts","text":"..."}}
$ kubectl get deploy homelab-ops-sre-sentinel-channel-slack -n automation \
    -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="INSTANCE_NAME")].value}'
homelab-ops-sre-sentinel
```

Both halves of the discriminator are present and neither is consulted. Successful
sends are not logged, so the proof that all five *post* rather than merely
receive came from a failure: one malformed `chatId` produced the identical
`channel_not_found` in all five sidecars at the same second, while only
`sre-sentinel` had run.

### The fix is to stop using the channel: `deliveryMode: hook`

The tempting reading of that missing filter is that it can be turned into the
fix: a sidecar ignores the sender, so a *single* slack sidecar should deliver the
whole ensemble, each message to the `chatId` it names. Unbind four personas, keep
one, done.

It does not work, and the way it fails is worth writing down. `send_channel_message`
is registered on an unbound persona and answers normally — a probe against
`renovate-reviewer`, the one persona already bound to nothing, called it once and
the run reported `Succeeded` with result `DONE`:

```console
$ kubectl get agentrun unbound-delivery-probe-1 -n automation -o jsonpath='{.status.result}'
DONE
$ # ...and in the pod's own log, one line lower:
agent       tool call: send_channel_message args={"channel":"slack","chatId":"#monitoring-ai-alerts",...}
agent       Wrote channel message: channel=slack chatId=#monitoring-ai-alerts threadId= len=31
ipc-bridge  Dropping outbound message to channel not configured on this agent
              path=/ipc/messages/send-1787503073633807136.json channel=slack
```

The ipc-bridge gates outbound on the agent's own `channels`, so the binding is
what lets a message reach the bus at all. Delivery and the duplicate-producing
sidecar are the same switch: **every persona that reports to a channel costs one
copy of every report in the ensemble.** Unbinding four would have silenced them
completely, with every run still green.

Nothing else reaches it either:

- `channelAccessControl` (`allowedChats`, `allowedSenders`, `deniedSenders`) is
  inbound only — "only messages from listed chats are accepted", "only listed
  senders can trigger agent runs". No outbound field exists on any CRD.
- The controller exposes only `SYMPOZIUM_IMAGE_REGISTRY` and
  `SYMPOZIUM_IMAGE_TAG`, both fleet-wide. Running a patched `channel-slack` means
  mirroring the whole image set under one tag.
- The sidecar Deployment declares `replicas: 1` under an `Agent` ownerReference,
  so scaling one to zero is reconciled straight back.

So the multiplier cannot be removed from the channel side. It can be sidestepped
entirely by not using the channel: `lifecycle.postRun` runs a container after the
agent finishes, with the report in `AGENT_RESULT` and the bot token pulled from a
Secret by reference. One `chat.postMessage`, no event bus, one copy.

Measured end to end before it was adopted:

```console
$ kubectl logs <run>-postrun-<hash> -c post-deliver -n automation
slack response: {"ok":true,"channel":"C0BSUUF6GHE","ts":"1787507365.945959",...}
delivered ok
$ kubectl get agentrun <run> -n automation -o jsonpath='{.status.result}'
SRE Sentinel | homelab-ops | postRun delivery probe
...
```

Egress works because the hook pod carries no `sympozium.ai/role=agent` label, so
`sympozium-agent-deny-all` does not select it; `agent-allow-tools` would
otherwise permit only in-cluster port 8080. Note the hook runs as an *init*
container named `post-<name>` in a `<run>-postrun-*` pod whose main container is
`done` — `kubectl logs` without `-c` gives you the wrong one.

It also fixes the empty results, which turned out to have nothing to do with
invalid UTF-8. Over 24 hours: `terminal turn had empty text` 60, `invalid UTF-8`
2. The model's last act was calling the posting tool, so there was no final text
to return. Take the tool away and the report *is* the final text.

`deliveryMode` therefore defaults to **hook**, so a persona added later gets
one-copy delivery without anyone remembering to ask for it. All five
`homelab-ops` personas are on it; `tool` stays expressible for a persona that
genuinely needs the sidecar path, and `scripts/validate.py` warns with the live
duplicate count the moment one does.

Three knobs went away with the sidecars, and their absence is enforced rather
than assumed:

- **`send_channel_message` is off every allowlist.** Keeping it would mean the
  model posts *and* is posted for, and worse, the run would end on a tool call —
  which is what leaves `status.result`, and so `AGENT_RESULT`, empty.
- **`notify` is gone.** A hook posts unconditionally, so a notify level would
  claim a suppression that does not happen. The cost is real: `-alerts` now gets
  a report every 30 minutes where `onChange` kept it near-silent. The lever is
  `schedule.interval`.
- **`verbosity` is gone.** The verbosity files describe how to call the posting
  tool; hook mode substitutes `prompts/delivery/hook.md` instead and never reads
  them.

Two things that must stay true. A persona with no `sympozium_delivery` entry gets
**no** hook — `homelab-reviewer` delivers nothing on purpose, its alert being the
DO NOT MERGE comment on the pull request — so the template gates the hook on a
resolved destination, not merely on the mode. And `hook.md` names no tool at all:
an earlier draft mentioned the posting tool while explaining what it replaced,
which is exactly the trap in *Naming the argument was not enough* above — a 4B
model reads a tool name as an instruction to call it.

`sre-sentinel` keeps the ensemble's one `channels: [slack]`, purely for inbound.
That makes an @-mention land on a known persona instead of whichever of five
sidecars Socket Mode happened to hand the event to.

### Hook mode did not retire the empty result — it left the residue

Taking the posting tool away removed the *dominant* cause, not the mechanism. On
2026-08-24 `homelab-ops-sre-sentinel-schedule-75` finished `Succeeded`, 7 tool
calls, 2645 output tokens, `status.result` null, and the channel got
`deliver-slack.sh`'s placeholder. No posting tool was involved; the run simply
stopped writing:

```
tool_call [3]: k8s_events_list  args={"fieldSelector":"involvedObject.name=longhorn-backend"}
tool_call [4]: k8s_pods_list    args={"labelSelector":"app=longhorn"}
tool_call [5]: k8s_resources_list args={"apiVersion":"v1","kind":"Pod","labelSelector":"app=longhorn,namespace=kube-system"}
tool_call [6]: k8s_resources_list args={"apiVersion":"v1","kind":"Pod","labelSelector":"app=longhorn,namespace=kube-system"}
tool_call [7]: k8s_pods_list    args={"labelSelector":"app=longhorn","namespace":"kube-system"}
WARNING: terminal turn had empty text and no prior reasoning to fall back on
```

Calls 1 and 2 were correct and answered. `ALERTS` carried something genuinely
new — `TargetDown{job="longhorn-backend", namespace="kube-system"}`, all five
`longhorn-manager` pods refusing connections on :9500 after the v1.12.1 bump —
and the agent set out to root-cause it, as instructed. Then: a scrape-job name
passed as a pod name, `namespace` written as a term inside `labelSelector` (no
object carries such a label), that same call again byte-for-byte, and finally the
selector with `namespace` promoted to an argument but `app=longhorn` still wrong
— the real selector is `app=longhorn-manager`. Five empty results in a row, and
then a turn with neither text nor a tool call. The alert went unreported.

Three lessons, and only the third is new:

- **"Find the cause" with no budget and no exit is the bug.** A model this size
  does not conclude on its own that it has learned enough to start writing. Step
  3 of the prompt now grants *at most 3 lookups* per alert and names the outcome
  when they yield nothing — `cause not determined`, stated to be a legitimate
  finding. Both halves are load-bearing: a cap with no escape hatch relocates the
  silence, exactly as `endpoint-warden`'s mandatory table produced invented
  numbers until absence became expressible as `unavailable`.
- **Give the model the literal shape of the call.** `namespace` is its own
  argument on every `k8s_*` tool and never a `labelSelector` term; the alert's
  own labels are the address, so nothing has to be assembled by hand. Same
  reasoning as pinning the datasource uid.
- **`max_tool_iterations` is 50 and hitting it is silent.** Not what happened
  here — this run used 7 — but the search for it turned up five runs that did
  hit it, and the failure mode is worse: the run ends `status: error`, so the
  postRun hook never fires and *nothing* arrives, not even a placeholder.
  `endpoint-warden` used 48 of 50 at 04:30 that morning and failed on 50 at
  06:15. Both ensembles now set `MAX_TOOL_ITERATIONS: "100"` in `defaults:`. The
  real ceiling is the 65536 context every accumulated tool result has to fit
  inside, so this buys headroom rather than removing a limit.

`scripts/validate.py` fails a prompt that names `k8s_events_list` without stating
a lookup budget and the unresolved-cause wording, and fails an `env` value that
is not a quoted string — the CRD types `env` as `map[string]string` and the
webhook decodes strictly, so a bare `100` is rejected at apply time.

### It happened again the same day, on a different tool

`homelab-ops-db-steward-schedule-5`, 2026-08-24 07:49: `Succeeded`, 14 tool
calls, 102,289 tokens, `status.result` null, and the same placeholder in Slack.
The reading half of the run went perfectly — health, both archiver expressions
with the `increase(...)` wrapper intact, the top queries, `redis_*` memory, the
`group_left` fill expression, all in the first six calls. Then it went looking
for the CloudNativePG `Cluster` object:

```
tool_call [7]  k8s_resources_list {"apiVersion":"postgresql.cnpg.io/v1","kind":"Cluster","labelSelector":"name=...-cluster-18-1"}
tool_call [8]  k8s_resources_list {"apiVersion":"v1","kind":"Pod","labelSelector":"app=cloudnative-pg,namespace=data"}
tool_call [10] k8s_resources_list {"apiVersion":"v1","kind":"PersistentVolumeClaim","labelSelector":"name=...-cluster-18-1, name=...-cluster-18-1-wal"}
tool_call [13] k8s_resources_list {"apiVersion":"v1","kind":"Pod","labelSelector":"app=cloudnative-pg,namespace=data"}
WARNING: terminal turn had empty text and no prior reasoning to fall back on
```

Every one of those matches nothing. `name` is not a label; the pod name is the
cluster name with `-1` appended, so neither string is a label value anyway;
`namespace` is inside `labelSelector` again; call 10 puts two equalities on one
key, which can never both hold; call 13 repeats call 8 byte-for-byte. Seven of
the fourteen calls went on one object that a bare `apiVersion` + `kind` +
`namespace` returns — the model finally made that call at [11] and still could
not stop. A day's Postgres and Valkey readings were in hand and none of them
were written down.

This is the sre-sentinel failure with the nouns changed, which says the fix was
scoped too narrowly the first time: the prompt said "root-cause" there and merely
"`k8s_resources_list` for Clusters" here, and only the first had a budget. So the
rules are now per-tool rather than per-persona. `db_steward_system.md` step 5
gives the literal three-argument call, states that `status.currentPrimary` names
the primary so Pods never need listing, forbids a `labelSelector` outright, and
carries the same *at most 3 lookups* cap with `cause not determined` as the exit;
`service_janitor_system.md` gained the same guards, sized per backup system,
since it is the other `k8s_resources_list` caller and its one successful run
spent 46 tool calls. `scripts/validate.py` now keys both checks off
`K8S_LOOKUP_TOOLS` — `k8s_events_list`, `k8s_pods_log`, `k8s_resources_list` —
and additionally requires every prompt naming one of them to say that
`namespace` is its own argument and to forbid repeating a call.

Worth stating plainly, because the concurrency above was the first suspicion:
this was not GPU contention. `endpoint-warden` was running against the same
single Ollama slot throughout, and every one of db-steward's requests came back
`200` with `truncated = 0` at `n_ctx_slot = 65536`. Contention doubled the wall
clock and changed nothing else.

### Verified, and it turned up a second prompt bug

Re-run as a hand-applied `AgentRun` with the new prompt, nothing else on the GPU:
9 tool calls against 14, 42.9 s against 127.8 s, 40,661 tokens against 102,289,
and a full four-section report in `status.result`. The cluster lookup was the
first call and the only one — `apiVersion` + `kind` + `namespace`, no selector —
and the primary came straight off `status.currentPrimary`.

The report it finally produced then showed what the empty result had been hiding.
The **Valkey** section read "Memory max: reported as 0 bytes — unable to
determine actual limit", which is a permanent finding of exactly the kind the
kernel-drift bullet warns about: this Valkey has no `maxmemory` set, so the
exporter publishes `redis_memory_max_bytes` = 0, and the container carries no
memory limit either (`container_spec_memory_limit_bytes` returns nothing for the
pod). Both verified against Prometheus on 2026-08-24. "Compare used against max"
could never be satisfied, so the section was going to say "unable to determine"
every run forever.

The prompt now reads `redis_memory_used_bytes` with its trend and
`increase(redis_evicted_keys_total[1h])` — evictions being the direct measurement
of what a ceiling would have warned about — and says outright that there is no
percentage to compute here. `redis_evicted_keys_total` is a counter by
Prometheus's metadata, so it joins `CUMULATIVE_COUNTERS` and the window is
enforced. That an unbounded cache grows until the node runs out is worth
suggesting once, not raising daily.

Worth generalising: an empty result hides every other bug in the prompt behind
it. The Valkey line had been wrong since the persona was written and nobody could
see it, because the runs that would have shown it delivered a placeholder.

### A completed run's log is in Loki, not gone

The agent pod is deleted on completion whatever `cleanup` says, which is why the
guidance elsewhere here is to stream `kubectl logs -c agent -f` during a probe.
That is still the right way to watch a run, but a run that has already finished is
*not* unrecoverable: Loki has every container of it, which is the only reason the
trace above could be read hours later.

```bash
kubectl port-forward -n monitoring svc/datahub-local-core-loki-gateway 3199:80 &
curl -sG http://localhost:3199/loki/api/v1/query_range \
  --data-urlencode 'query={pod="homelab-ops-sre-sentinel-schedule-75-rqmbq"}' \
  --data-urlencode 'start=2026-08-24T06:07:00Z' \
  --data-urlencode 'end=2026-08-24T06:11:00Z' \
  --data-urlencode 'direction=forward' --data-urlencode 'limit=5000'
```

`status.podName` on the AgentRun gives the pod name, and `startedAt`/`completedAt`
give the window. The `agent` container carries the tool calls and the terminal
warning; `mcp-bridge` carries which server each call went to; `mcp-discover`
prints the per-server tool counts. Tool *results* are not logged anywhere — replay
the query against Prometheus to see what the model saw.

This is also how to measure a failure mode across the fleet rather than guess at
it, which is where the counts above came from:

```
{namespace="automation",container="agent"} |= "terminal turn had empty text"
{namespace="automation",container="agent"} |= "exceeded maximum tool-call iterations"
```

## The endpoint *replaces* the schedule — it does not sit beside it

**This is the reason `sympozium_web_endpoint.enabled` is `false`.** Enabling the
endpoint silently stops every scheduled run for that persona.

Enabling it creates one long-lived `AgentRun` per persona in phase `Serving`
(`mode: server`, `agentId: web-endpoint`, a fixed `sessionKey: web-endpoint`),
which puts the `Agent` itself into phase `Serving` with one active pod. The
schedule controller then refuses to fire:

    INFO controllers.SympoziumSchedule Skipping trigger — instance has a
    serving AgentRun {"sympoziumschedule": "homelab-ops-sre-sentinel-schedule",
    "servingRun": "homelab-ops-sre-sentinel-web-endpoint"}

Observed, not inferred. The endpoints came up at 05:24:30Z on 2026-08-23; the
next two due ticks — `db-steward` at 05:30 (daily) and `sre-sentinel` at 05:38
(30m heartbeat) — never produced an `AgentRun`, and the `SympoziumSchedule`
objects stayed `Active` while quietly skipping. Nothing surfaces this: no
failed run, no event on the schedule, no change in phase. The fleet just stops.

So the two are mutually exclusive per persona, and the choice is: a scheduled
agent, or an on-demand one. For this fleet the schedule *is* the product, which
is why the master switch stays off and gets flipped on only for the length of a
test:

    # values/default.yaml.gotmpl
    sympozium_web_endpoint:
      enabled: true     # <- and back to false afterwards

Two smaller things, if you do turn it on. The serving run has
`useContext: true` on a *fixed* session key, so successive HTTP requests
accumulate conversation history while every scheduled run starts clean — the
second request reproduces a cron run with the first still in context, not a
clean one. And the endpoint is a trigger: every persona behind one is read-only
today, which is the only reason a ClusterIP with a bearer key is a reasonable
place to leave it.

## A right metric read the wrong way round

The volume check in `sre_sentinel_system.md` said:

    Query kubelet_volume_stats_available_bytes / kubelet_volume_stats_capacity_bytes
    and flag any PersistentVolumeClaim above 80%

That ratio is the fraction **free**. Flagging "above 80%" flags the *emptiest*
volumes in the cluster and can never flag a full one. It shipped that way and ran
for days. The report that finally exposed it named
`logs-datahub-local-core-data-airflow-triggerer-0` at "97-98% capacity — write
operations failing":

    free fraction: 0.9789697334135097     <- reported as "97.9% full"
    used fraction: 0.0210302665864903     <- actual

Measured the same day, with the storage-class filter below: **nothing in the
cluster was above 31% used**, and the NFS share was under 1%. Every *Filling up*
section and every volume-driven CRITICAL had been false since the persona was
written.

It did more damage than a wrong line in a report. "**Filling up** is not
'Nothing filling.'" is one of the conditions in *What counts as a change*, so an
always-populated Filling up section made every run count as a change and post to
Slack — the inversion defeated the anti-noise rule that exists two sections
further down the same prompt.

Two things had to change in the expression:

    100 * (1 - kubelet_volume_stats_available_bytes / kubelet_volume_stats_capacity_bytes)
      * on(namespace, persistentvolumeclaim) group_left(storageclass)
        (kube_persistentvolumeclaim_info{storageclass=~"longhorn|longhorn-no-replica"} > 0)

The `1 -` is the fix. The join is the second half of the same lesson: Garage's
data volumes are on the `nfs` class, and all five `nfs` PVCs report the *same*
`capacity_bytes` — 1,926,808,731,648, the share itself. A per-volume percentage
there is the share's fill repeated once per claim, which is how "garage-2 at 99%,
immediate action required" reached Slack about a share that was empty. Only
`longhorn` and `longhorn-no-replica` have a real per-volume capacity.
`kube_persistentvolumeclaim_info` carries the `storageclass` label; the metric
does not.

The rule this adds, which *Verify the telemetry exists before writing a prompt
against it* did not cover: *a correct metric name is not a correct reading.* Both
metrics here existed, were spelled right, and were confirmed present — and the
prompt was still wrong, because nothing had checked the direction of the
division or what the denominator meant per storage class. A 4B model will not
notice; it computes what it is told and reports it with total confidence.

Encoded so it cannot return: `scripts/validate.py` fails any persona prompt that
divides an availability metric by a capacity metric without a `1 -` on the same
line, and the expressions are now given literally in the prompts rather than
described, because a `group_left` join is beyond what this model will assemble
from prose.

One consequence to remember about memory: `sre-sentinel` spent days storing runs
that asserted volumes at 96-99%. Fixing the prompt does not remove those, so its
seeds now carry an explicit correction telling it to distrust its own fill
history before 2026-08-23. See [Wiping a persona's memory](README.md#wiping-a-personas-memory) for the
alternative.

### The same mistake with a counter instead of a ratio

The fill inversion was a ratio read the wrong way round. `db_steward_system.md`
had the counter version of it, and it survived longer because the metric name and
the conclusion both looked right:

    `cnpg_pg_stat_archiver_failed_count` — **the most important number you
    look at.** WAL archiving that is failing means point-in-time recovery is
    silently broken, even though every backup still reports success.

Nothing there says the metric is a **counter**. It counts archive attempts that
have failed since the statistics were last reset, so it never falls, and a
cluster that had two failures once and archived perfectly ever afterwards reports
`2` forever. Paired with a hard rule that a failing archiver is CRITICAL, that is
a permanent CRITICAL. Measured on 2026-08-24, while the agent was calling
recovery "silently broken":

    cnpg_pg_stat_archiver_failed_count               2
    increase(cnpg_pg_stat_archiver_failed_count[24h])   0        <- no failure in a day
    time() - cnpg_pg_stat_archiver_last_failed_time  470508      <- 5.4 days ago
    time() - cnpg_pg_stat_archiver_last_archived_time     95     <- 95 seconds ago
    increase(cnpg_pg_stat_archiver_archived_count[1h])   12.1

Archiving was working. Two runs had already posted the CRITICAL to
`#monitoring-ai-health`, and the persona's own memory seed said "a *rising*
`..._failed_count`" — the prompt overrode the seed, because the prompt is what
names the tool call.

The prompt now gives both expressions literally, and a hard rule that a non-zero
lifetime total with a zero increase is a **healthy** archiver that the report
should say so about. A probe flipped the verdict from CRITICAL to HEALTHY on the
same cluster in the same minute.

`endpoint-warden` had the identical latent bug and is the reason prose is not
enough. It named `node_pressure_*`, `node_edac_*` and
`node_disk_io_time_seconds_total` — all genuine counters — and told the model
"Take the rate, not the raw counter" in the checklist and "Rates, not counters"
again in the hard rules, while handing it nothing but bare metric names to put in
an `expr`. Both prompts now carry the literal `rate(...)`/`increase(...)` window.

Two things this cost that are worth keeping in mind:

- **A `_total` suffix does not mean counter.** `cnpg_backends_total` and
  `cnpg_backends_waiting_total` are gauges. The first draft of the validator
  check keyed on the suffix and immediately failed a correct prompt, which is the
  *a rule the fleet cannot satisfy* trap. `scripts/validate.py` therefore holds an
  explicit `CUMULATIVE_COUNTERS` set read off Prometheus's metadata API, with the
  command to re-derive it after an exporter bump.
- **The model drops the wrapper.** Given `increase(cnpg_pg_stat_archiver_failed_count[1h])`
  the first probe sent `cnpg_pg_stat_archiver_failed_count[1h]` — a bare range
  selector — and then labelled the raw counter it got back as the increase. It is
  the `chatId` lesson once more: a 4B model told to strip the punctuation around
  argument *values* strips the function call around an expression too. Both
  prompts now say an `expr` is the whole line, wrapper included, and the second
  probe sent it intact and reported `= 0`.

## Reading the uid was worse than pinning it

`grafana_list_datasources` returns all three datasources this Grafana serves:

| name | uid | type |
| --- | --- | --- |
| Prometheus | `prometheus` | prometheus |
| Alertmanager | `alertmanager` | alertmanager |
| Loki | `P8E80F9AEF21F6940` | loki |

Only one of those *looks* like a uid. A 4B model reads the list, takes the hex
string for the real identifier and the bare word `prometheus` for a placeholder
it was supposed to resolve, and sends every PromQL query to Loki — which answers
`404 page not found` for every metric. So the tool added to stop the uid being a
guess is what produced the wrong guess, and it did so against a prompt that
already stated the correct value two paragraphs earlier.

The tool is now absent from all four Prometheus-reading personas, and the uid is
a pinned literal. That is safe because the datasource is provisioned `readOnly`
by kube-prometheus-stack, so `prometheus` is stable; and if it ever does change,
the agent reports every metric unavailable, which is loud. `scripts/validate.py`
enforces both halves — no persona may allowlist the tool, and any prompt calling
`grafana_query_prometheus` must spell out `datasourceUid   prometheus`.

The general lesson is worth more than the fix: **a discovery tool that returns
several plausible answers is a liability at this model size.** The agent has to
choose, a wrong choice fails silently, and the failure looks like the thing being
discovered is broken. Prefer a pinned literal plus a loud failure.

### It then invented the numbers rather than report none

The 2026-08-24 04:30 run of `endpoint-warden` is the part that cost trust. With
every Prometheus query 404ing, the mandated **Fleet** table still required seven
columns per node — and the model filled the disk column from the one tool that
had answered, `k8s_nodes_top`, whose memory percentages it relabelled as disk:

| node | reported "disk fill" | `kubectl top` memory | actual `df` |
| --- | --- | --- | --- |
| datahublocal-orpi-0 | 79% (CRITICAL) | 81% | **5%** |
| datahublocal-amd-2 | 35% | 34% | — |
| datahublocal-nas | 16% | 16% | — |

It then emitted the whole report twice with different numbers, the second copy
annotating its own substitution (`~45% disk fill (calculated from k8s_nodes_top
memory)`) while the first presented it bare. The existing hard rule — "never
report a number you did not retrieve" — lost to the format rule demanding a
value in every column.

Three prompt changes, because the format was as much at fault as the model: a
column with no metric is the literal word `unavailable` and a row of seven of
those is a legitimate row; every figure must come from the metric named for it,
with `k8s_nodes_top` called out as CPU and memory only; and the three sections
are emitted exactly once each. A correcting memory seed tells the persona to
treat its pre-2026-08-24 Fleet rows as absent rather than as a baseline, per
[When not to wipe](README.md#wiping-a-personas-memory).

### The kernel "drift" was never drift

The same reports flagged `datahublocal-orpi-0` on `7.1.2-edge-rockchip64` against
orpi-1/2/3 on `6.1.115-vendor-rk35xx` as version drift, every run, for days. It
is not drift — it is four hardware classes on four kernel trees:

| node(s) | hardware | OS | kernel |
| --- | --- | --- | --- |
| orpi-0 | Orange Pi 4 LTS (RK3399) | DietPi / trixie | `7.1.2-edge-rockchip64` |
| orpi-1, orpi-2, orpi-3 | Orange Pi 5B (RK3588) | DietPi / trixie | `6.1.115-vendor-rk35xx` |
| amd-1, amd-2 | amd64 | Debian 13 trixie | `6.12.96` / `6.12.101+deb13-amd64` |
| nas | Intel N305 | TrueNAS / bookworm | `6.12.15-production+truenas` |

The seed said "kernel and OS versions should match across nodes; the odd one out
is the finding", which is true only within a class. Different SoC families cannot
converge on a kernel, so that finding could never be actioned and could never go
away. Kernels are now compared within a hardware class only: the sole comparable
pair is amd-1 against amd-2, where 6.12.96 genuinely trails 6.12.101, and orpi-0
and the NAS are each a class of one and so can never be the odd one out.

**A permanent finding is a bug in the prompt, not a problem in the fleet.** It
also costs more than noise here, since a non-empty findings section is a change
condition that forces a post.

Not instrumented, so no prompt pretends to check them:

| Wanted | Missing | Where the fix goes |
| --- | --- | --- |
| S3 capacity | Garage exports no metrics and is not scraped — no `garage_*` series exist | core, a ServiceMonitor — meanwhile the janitor reads its PVCs |
| repo-level CI history | the GitHub MCP server ships no Actions/workflow tools | upstream `mcp/github`, or a different server |

Two rows left this table on 2026-08-23. **systemd unit state** and **pending OS
package updates** are now instrumented — see *Follow-ups to share with the other
repos* below for the metric names — and the personas have not yet been updated to
use them. S3 capacity is the only core-side gap remaining.

Standing in for systemd, `endpoint-warden` checks the node's *Kubernetes* system
workloads instead — `kube-system` and `monitoring` pods grouped by node. On a k3s
box that is most of what systemd would have told you, and there is already
something to find: the node-exporter pods themselves carry 4–16 restarts.

## Follow-ups to share with the other repos

Four changes were asked of `datahub-local-core`'s
`releases/monitoring/values/kube-prometheus-stack.yaml.gotmpl`. **All four have
landed**, verified against the live cluster on 2026-08-23 — the list below is
kept as a record of what to re-check after a chart bump, not as work outstanding:

1. **Disable the k3s phantom components** — done. Prometheus now carries no
   `KubeSchedulerDown` or `KubeControllerManagerDown` rule and no
   scheduler/controller-manager scrape target at all, which is why neither
   alert fires. Re-check with `/api/v1/rules` and `/api/v1/targets` rather than
   by looking for the alert, since "not firing" and "not defined" look identical
   from a dashboard.
2. **OS update counts** — done. The textfile sidecar
   (`ghcr.io/datahub-local/node-exporter-textfiles`) now runs
   `SCRIPTS=nutmon.py,smartmon.py,updates.py` and publishes
   `node_apt_upgrades_pending`, `node_apt_security_upgrades_pending`,
   `node_apt_package_cache_timestamp_seconds` and `node_reboot_required`.
3. **systemd unit state** — done, and scoped rather than wholesale:
   `--collector.systemd` is paired with a `--collector.systemd.unit-include`
   allowlist covering `k3s`, `k3s-agent`, `containerd`, `ssh`,
   `systemd-timesyncd`, `chrony`, `smartmontools` and the three `nut-*` units.
   `node_systemd_unit_state` is present on all seven nodes (115 series, none
   `failed` as of 2026-08-23), plus `node_systemd_units` and
   `node_systemd_system_running`.
4. **Re-sync the drifted `extraArgs`** — done. The live node-exporter args carry
   both the `run/containerd/.+` mount-point exclusion and the `erofs` fs-type
   exclusion.

What that unblocks is in *this* repository, not core: `endpoint-warden` was
written around these metrics not existing, and it can now check systemd unit
state and pending OS updates by naming the metrics above in its prompt — no
structural change, and the gap table above needs its first two rows struck.
Verify each metric against Prometheus before it goes in a prompt; that rule has
not changed just because the metrics arrived.

Everything still outstanding for the other repos — including the one monitoring
item that has not landed, the Garage ServiceMonitor — splits in two, because only
part of it is core's. Four config changes belong
here — the `mcp-k8s` Deployment is currently unmanaged (`spec.deployment` is null
while the Deployment it needs is still owned by the CR), `mcp-postgres` denies
`execute_write_query`, which is not a tool that server has, three servers carry
no catalog-level `toolsDeny` at all, and `web-proxy` floats on `:latest` against
a v0.10.47 control plane. The other three are upstream
`sympozium-ai/sympozium` bugs that nothing in either of our repositories can fix,
written as ready-to-file issues: the UTF-8 marshal that drops `status.result`,
the web proxy dropping `toolPolicy` and truncating the task, and
`MCPServer.status.ready` reporting `true` for a server that answers no
`tools/list`. All three share one failure mode — the run reports `Succeeded` and
quietly does less than it claims — which is the same mode as every agent-side bug
in this document.

A fifth, unrelated change to `releases/automation/` is what currently stops the
fleet running at all — see below.

A sixth landed on 2026-08-24 and is the largest of them, because it is the one
that made `toolPolicy` decorative: the built-in `k8s-ops` and `sre-observability`
SkillPacks tell the model to shell out, and their sidecar RBAC is bound to the
shared `sympozium-agent` ServiceAccount. Two fixes, one in core's catalog and one
upstream — the prompt to hand to core is in
`#a-skillpack-overrode-every-tool-decision-in-this-repository`.

## The `mcp-k8s` MCPServer is `transportType: http` and answers 404

**Resolved by core on 2026-08-23, with a caveat.** The MCPServer is now declared
external with the path spelled out —
`url: http://...-mcp-k8s.automation.svc:8080/mcp` — and discovery reports
`Discovered 14 tools from "...-mcp-k8s"`. `sre-sentinel` has used
`k8s_events_list` and `k8s_pods_log` on a real run since. The caveat is that
`spec.deployment` is now null while the Deployment serving that URL is still
owned by the MCPServer CR, so nothing declares it any more. Delete and recreate
the MCPServer and the Deployment is cascade-deleted and never rebuilt, taking
every `k8s_*` tool with it.

Every `k8s_*` tool has been absent from every persona since the server was
created. `datahub-local-core-automation-sympozium-mcp-k8s` is the one MCPServer
in the catalog declared `transportType: http`; the other four are `stdio` and
work. The tool-discovery init container hits the service root and gets a 404 on
all six attempts:

    kubectl logs -n automation <run-pod> -c mcp-discover
    WARNING: all 6 discover attempts failed for "...-mcp-k8s":
      HTTP 404 from http://...-mcp-k8s.automation.svc:8080: 404 page not found
    Discovered 51 tools from "...-mcp-grafana"
    Wrote tool manifest with 51 tools

`ghcr.io/containers/kubernetes-mcp-server` serves streamable HTTP under `/mcp`,
not `/`, and nothing in the CR can add a path — `spec.url` exists only for
external servers with no `deployment`. Confirmed against the running pod: `POST
/` is 404, `POST /mcp` is 200 and answers with a JSON-RPC session error, which is
the correct response to an uninitialised `tools/list`.

`MCPServer.status.ready` is `true` regardless, because it tracks the Deployment
and not a `tools/list`, so nothing surfaces this. The only visible symptom is a
run that quietly cannot investigate: `sre-sentinel` loses
`k8s_pods_list`, `k8s_events_list`, `k8s_pods_log` and `k8s_resources_list`, so
every cause it reports comes from Prometheus alert labels alone, and the reports
read plausibly while resting on nothing but metrics.

The fix belongs in core, and the cluster already demonstrates it: give the k8s
server `transportType: stdio` like grafana, argocd, github and postgres, and the
controller's shim serves it at the root the bridge already asks for. This is also
the second instance of the rule in *Tool names are not guessable* — a tool that
does not arrive fails silently, whether the name is wrong or the whole server is
unreachable, so re-run the discovery check after any MCP image or transport
change.

## An empty `status.result` is a gRPC marshal failure on invalid UTF-8

Roughly 58% of runs finish `Succeeded`, with tool calls, output tokens and a
report that reaches Slack, and `status.result` empty. It is not a length cap (a
1599-character result stores fine), not `cleanup`, and nothing sets
`status.error`. The runner says what happened, one line above the result marker:

    tool call: send_channel_message args={... "text":"SRE Sentinel \ufffd\ufffd ..."}
    Wrote channel message: channel=slack chatId=#monitoring-ai-alerts len=1449
    rpc error: code = Internal desc = grpc: error while marshaling:
      string field contains invalid UTF-8
    __SYMPOZIUM_RESULT__{"status":"success","metrics":{...}}__SYMPOZIUM_END__

No `response` key at all — compare a healthy run, which carries
`"response":"..."`. The runner ships its final reply to the controller over gRPC,
protobuf refuses to marshal a `string` field that is not valid UTF-8, and the
reply is dropped. The run is still `Succeeded` because the *work* succeeded; only
the transport of the text failed.

What produced the invalid bytes was our own header. `prompts/delivery/header.md`
ordered the model to reproduce, character for character:

    {{ AGENT }} · {{ ENSEMBLE }} · {{ SCHEDULE }}

`·` is U+00B7 — two bytes in UTF-8. A 4B model at a `q8_0` KV cache reproducing
that byte pair sometimes emits a lone or wrong continuation byte, which is the
`\ufffd\ufffd` above. The one string the prompts demanded be echoed verbatim was
also the one most likely to be corrupted, and it was in every report every
persona wrote.

Consistent with every measurement taken: three throwaway runs with ASCII-only
output stored results of 2, 72 and 1599 characters without trouble, while persona
runs — all of which mandated the `·` — came back empty at 26 of 45. The header is
now `|`-separated, the two argument blocks that carried an em dash are plain
hyphens, and `scripts/validate.py` fails on any non-ASCII character inside an
indented block in `prompts/delivery/`, because an indented block there *is* the
text the model is told to emit. Prose outside those blocks keeps its typography;
the model is not asked to reproduce it.

Two things this does not fix, and one of them belongs to core:

- The model can still emit a mangled multi-byte character of its own accord, from
  prose it was never told to copy. The durable fix is control-plane side —
  sanitise or lossy-decode the reply before the marshal, so a corrupt byte costs
  a replacement character rather than the whole report. Worth raising against
  core alongside the two items below.
- A dropped `result` is invisible: `phase: Succeeded`, no `error`, no condition.
  Until it is sanitised, do not read an empty `result` as a quiet run — stream
  `kubectl logs <pod> -c agent -f` instead, which is where the report actually
  is.

## The tool schemas, not the report, are what fills the context

`toolPolicy` filters at the LLM request. It does not stop a tool being
*registered*, and every registered tool's JSON schema is injected into the
prompt on every call. The runner says so plainly — this is a run with nine
allowed tools:

    tools enabled: 60 tool(s) registered

Sixty, because the grafana MCP server alone exposes 66 tools and the persona only
denied 14 of them. Measured with two throwaway `AgentRun`s that differ in nothing
but `toolPolicy`, each with a one-line system prompt and no task worth the name:

| Run | `toolPolicy` | First-call input |
| --- | --- | --- |
| mirrors the web proxy | absent | **40,500 tokens** |
| mirrors the schedule | the persona's nine | 4,095 tokens |

Ollama reported the live window as `context_length: 32768` at the time, so
40,500 did not fit. Nothing errors: the request is truncated and the run proceeds
against a prompt with the front of it gone — which is where the persona, the
report format, the four required sections and the delivery instructions all live.
That is the whole explanation for

    (Agent completed its task via tool calls but did not produce a final text
     summary.)

on a web-triggered run. The agent is not ignoring its instructions; it never
received them. It also explains the mangled `chatId` above, and why a web run
costs three times the tokens of a scheduled one for a worse answer.

The fix is `toolsAllow` on each persona's `mcpServers` entry, which filters at
the server and therefore bounds what is registered at all. Every persona now
pins it to exactly the tools its `toolPolicy.allow` names, unprefixed, and
`scripts/validate.py` fails if the two lists drift in either direction — a tool
in `toolsAllow` but not `toolPolicy.allow` is prompt weight the model can never
use, and the reverse never reaches the agent. sre-sentinel's grafana wiring goes
from 52 registered tools to two.

This also repairs the web endpoint as a side effect: a run with no `toolPolicy`
now has only ~15 tools to describe, so it fits the window with or without the
policy. The `toolsDeny` lists stay, and are now redundant by construction —
`toolsAllow` already excludes every write tool. They are kept as documentation of
which write names are real, because core's own catalog denies names that do not
exist (see *Tool names are not guessable*); do not mistake them for the
enforcing mechanism.

### The window was then raised to 65536, which does not retire the rule

Core's ollama Deployment now sets `OLLAMA_CONTEXT_LENGTH=65536`, alongside
`OLLAMA_FLASH_ATTENTION=1` and `OLLAMA_KV_CACHE_TYPE=q8_0`. Verified live after
forcing a load — `GET /api/ps` reports `context_length: 65536` with
`size_vram == size` at 4.45 GB, so the model and its KV cache are wholly on the
6 GiB GPU with nothing spilled to CPU. The two Ollama tuning flags are
load-bearing for that, not incidental: a q8_0 KV cache is half the size of f16,
and doubling the window doubles what the cache costs. Re-check `size_vram`
against `size` after any change to either flag, the window, or the model — a
spill to CPU does not fail, it just makes every run several times slower.

Do not read the number out of this file. It lives in core's Deployment, and the
authoritative check is `GET /api/ps` with the model resident, which is the only
place the *effective* window appears — `/api/show` reports the architecture's
262144 ceiling, which has never been what a request gets.

40,500 now fits, so the raised window fixes the overflow on its own and
`toolsAllow` is no longer what stands between a web run and a truncated prompt.
The rule survives it anyway, for reasons that have nothing to do with the
window's size:

- At roughly 670 tokens per tool schema, sixty tools is ~40k of prompt on *every*
  call in the loop. That was the difference between 433,866 input tokens for a
  16-call web run and ~160,000 for a comparable scheduled one — same GPU, one
  model resident, and every token of it serialised through it.
- A 4B model chooses badly among sixty tools. The allowlist was always partly a
  precision device, which is why personas are held to five-to-seven tools; a
  registered-but-unallowlisted tool is described to the model and then refused,
  which is the worst of both.
- Headroom is what absorbs a large Prometheus result mid-run. Spending most of
  the window on schemas before the first query removes exactly that.

So the general rule holds in its stronger form: on a local model, the tool
surface is a prompt budget before it is a permissions question, and the budget is
spent on every call rather than once.

## A web-endpoint run also truncates the task to its first line

With `toolsAllow` deployed and the header ASCII, a web run finally produced a
clean full report — `SRE Sentinel | homelab-ops | heartbeat, every 30m`, four
sections, Status CRITICAL, 7 tool calls, 53,490 input tokens (down from 27k per
call to 7.6k), and `status.result` populated for the first time on that path.

And it sent nothing. The `channel-slack` Deployment logged neither a success nor
a failure, because `send_channel_message` was never called — even though the run
met every condition in *What counts as a change*.

The reason is a second thing the proxy drops. The persona's `schedule.taskFile`
is four paragraphs:

    Do an on-call sweep now.

    Query the firing alerts, diff them against what you saw last run, and
    root-cause anything new or changed. Then check whether any
    PersistentVolumeClaim is filling up, whether or not an alert has fired for it.

    Then emit the Status / New / Still firing / Filling up report.

    Then deliver it as your Delivery section instructs.

The `AgentRun` the proxy created carried one line: `Do an on-call sweep now.`
Compare `kubectl get sympoziumschedule ... -o jsonpath='{.spec.task}'` against
the web run's `{.spec.task}` — the last paragraph, the only place that told the
agent to deliver, is gone.

The system prompt still had its whole Delivery section, describing *how* to post
and *when*. What it never said was that posting is required. A 4B model reads
"here is how to post" plus a task that stops at "do a sweep" and reasonably
stops after writing the report.

So the imperative was in the wrong file. `prompts/notify/always.md` and
`onchange.md` now close with delivery as a completion condition of the run,
explicitly independent of the task text — *whatever your task says or leaves out
… this run is unfinished until you have called `send_channel_message`* — and
`scripts/validate.py` fails a notify level other than `never` that stops naming
the tool. `never.md` is untouched: for it, sending nothing is correct.

The general lesson, and the third time this repository has paid for it: anything
a run needs in order to be correct has to live in the prompt the persona always
carries, never in a field a caller can replace. `toolPolicy` was dropped, the
task was truncated, and both failed by producing a plausible run that did less
than it claimed.

### A web-endpoint run drops the persona's `toolPolicy` entirely

The `web-endpoint` SkillPack's proxy builds the child `AgentRun` from the
**`Agent`** object, and the Agent CRD has no `spec.toolPolicy` and no
`spec.systemPrompt` — the Ensemble controller can only park the prompt in
`spec.memory.systemPrompt`, and the tool policy has nowhere to go at all. The
schedule controller builds its runs from the Ensemble's `agentConfigs` entry
instead, so a scheduled `AgentRun` carries `toolPolicy` and a web-triggered one
does not:

    kubectl get agentrun <schedule-run> -o jsonpath='{.spec.toolPolicy}'   # the 9 allowed tools
    kubectl get agentrun <web-run>      -o jsonpath='{.spec.toolPolicy}'   # empty

An absent `toolPolicy` is not an empty allowlist — it is no allowlist. Measured
with a hand-applied `AgentRun` mirroring the proxy's spec: `sre-sentinel`, whose
persona allows nine tools and denies `write_file` and `execute_command`, started
with

    tools enabled: 60 tool(s) registered

so the read-only guarantee in *`homelab-ops` — read-only, no write tool of any
kind* does not hold for a run started over HTTP. That is a second, stronger
reason `sympozium_web_endpoint.enabled` stays `false` outside a test, alongside
the schedule suppression below: the endpoint does not merely bypass the cron, it
bypasses the per-persona restriction that the `permissive` `policyRef` deliberately
leaves to `projects/`. Closing it needs a `toolPolicy` field on the Agent CRD (or
on `webEndpoint`) in core; until then, testing goes through a hand-applied
`AgentRun`, which does carry the policy inline.

## The agent NetworkPolicy blocks shared memory and every MCP server

**Resolved by core on 2026-08-21/22.** A
`datahub-local-core-automation-sympozium-agent-allow-tools` policy now allows
egress on 8080 to `sympozium.ai/component=shared-memory` and
`app.kubernetes.io/name=mcpserver`, which are exactly the two destinations the
chart's own policy omits. Confirmed working: agents load their shared-memory
tools and discover MCP tools normally. The chart's
`sympozium-agent-allow-eventbus` still allows only its original three
destinations, so the diagnosis below still describes the upstream default and is
kept for the next person who deploys this chart somewhere else.

Every first run failed on 2026-08-21, and neither cause is in this repository.
The Sympozium chart's own `sympozium-agent-deny-all` selects
`sympozium.ai/role=agent` (Ingress + Egress) and `sympozium-agent-allow-eventbus`
punches the holes back. On port 8080 it allows exactly three destinations —
`sympozium.ai/component=memory`, `app.kubernetes.io/name=model`,
`app.kubernetes.io/component=apiserver` — and the two things our agents need most
are labelled neither:

| Destination | Its labels | Reachable from an agent pod |
| --- | --- | --- |
| per-persona memory server | `sympozium.ai/component=memory` | yes |
| **shared memory server** | `sympozium.ai/component=shared-memory` | **no** |
| **MCP servers** | `app.kubernetes.io/name=mcpserver` | **no** |
| Ollama | — (bare `11434` rule, core's `extraEgressPorts`) | yes |

Measured, not inferred — a throwaway pod labelled `sympozium.ai/role=agent`
reproduces it exactly. Note that the first request or two *succeed*: k3s programs
the policy a second or so after the pod starts, so a probe that runs immediately
sees a working network.

The two failure modes follow directly:

- **`homelab-ops` (all five personas).** `sharedMemory.enabled: true` gives every
  agent pod a `wait-for-shared-memory` init container that polls
  `homelab-ops-shared-memory:8080/health` for 120s and then `exit 1`. The Job
  exhausts its backoff limit and the AgentRun reports `Job failed` with
  `reason: infra` — the pod never got past `PodInitializing`, so there are no
  agent logs to read, which is what makes this one look mysterious.
- **`homelab-reviewer`.** No shared memory, so the pod starts and reaches Ollama
  — but every MCP tool call is blocked, and the run died with
  `exceeded maximum tool-call iterations (50)`.

`policyRef: permissive` does not help: these policies come from the chart's
`networkPolicies.enabled` and select *all* agent pods regardless of the
`SympoziumPolicy` bound to the ensemble.

The fix belongs in core, next to `sympozium_mcp_servers.yaml`, and is deliberately
narrower than adding `8080` to `extraEgressPorts` (which renders as a rule with no
`to:` — port 8080 open to the whole cluster):

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: sympozium-agent-allow-shared-memory-and-mcp
  namespace: automation
spec:
  podSelector:
    matchLabels:
      sympozium.ai/role: agent
  policyTypes: [Egress]
  egress:
    - ports:
        - { port: 8080, protocol: TCP }
      to:
        - podSelector:
            matchLabels:
              sympozium.ai/component: shared-memory
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: mcpserver
```

Worth reporting upstream too: a chart that ships both a shared-memory server and
an MCP catalog, and a policy that reaches neither, is broken for anything but the
single-agent case. Re-check the label names after an image bump before assuming
this entry still applies.

### `sympozium-allow-otel` strangles the web-proxy pods

**Resolved by core.** `...-sympozium-web-proxy-allow-egress`,
`...-agent-allow-otel` and `...-channel-allow-otel` now exist alongside the
chart's policies, and authenticated web requests produce complete runs. What a
web-triggered run still gets wrong is not network-related — it
[drops the persona's `toolPolicy`](#a-web-endpoint-run-drops-the-personas-toolpolicy-entirely)
and [truncates the task](#a-web-endpoint-run-also-truncates-the-task-to-its-first-line).
The diagnosis below is kept because it is the upstream chart's default behaviour.

The HTTP endpoints deploy and serve `/healthz`, but an authenticated request
fails before it reaches the model:

    {"error":{"message":"failed to get instance: failed to get server groups:
     Get \"https://10.43.0.1:443/api\": dial tcp 10.43.0.1:443: connect:
     connection refused"}}

The web-proxy needs the Kubernetes API to create the `AgentRun` it serves, and
it cannot reach it. Two label mistakes stack up, neither of them in this
repository:

- The Sympozium chart's own `sympozium-web-proxy-allow-ingress` — which *does*
  allow egress on 443/6443, DNS, NATS and Ollama — selects
  `sympozium.ai/component: web-proxy`. The controller labels these pods
  `sympozium.ai/component: agent-server`. The policy matches nothing.
- With that policy inert, the only Egress policy left selecting them is
  `sympozium-allow-otel` (`app.kubernetes.io/part-of: sympozium`), which allows
  ports 4317 and 4318 and nothing else. One matching Egress policy is enough to
  restrict a pod to the union of matching rules, so the effect of that OTLP
  allowance is to deny everything else.

Confirm the mismatch with:

    kubectl get pods -n automation -o json | jq -r '.items[]
      | select(.metadata.name|test("web-endpoint-server"))
      | .metadata.labels["sympozium.ai/component"]'
    kubectl get netpol sympozium-web-proxy-allow-ingress -n automation \
      -o jsonpath='{.spec.podSelector}'

Note this also corrects the comment in core's
`releases/automation/templates/sympozium_upstream_fixes.yaml`, which says
`sympozium-allow-otel` selects "a label no controller-created pod carries". The
agent-server pods do carry it, and that is exactly what breaks them.

Two ways to close it:

1. **Upstream** — `sympozium-web-proxy-allow-ingress` should select the label
   the controller actually sets. This is the one worth filing; it makes the
   chart's web endpoint feature non-functional under its own NetworkPolicies.
2. **Core, alongside the other fixes** — one more NetworkPolicy in
   `sympozium_upstream_fixes.yaml` selecting
   `sympozium.ai/component: agent-server`, allowing DNS, 443/6443 to the API
   server, 4222 to NATS and 11434/11435 to Ollama. That is the same shape as the
   three entries already in that file, and it is what will actually unblock these
   endpoints today. Written, as fix (4) in that file.

It lands once and then stays out of the way, because it selects a label rather
than a name. With `sympozium_web_endpoint.enabled` false the controller tears the
web-proxy Deployments down, nothing carries
`sympozium.ai/component: agent-server`, and a `podSelector` matching no pod
permits nothing — the policy is inert, not a standing hole. Turn the flag on and
the pods appear already covered. So the flag in this repository is the only thing
that moves; core does not have to be touched again in either direction.

    kubectl get pods -A -l sympozium.ai/component=agent-server   # empty when off

The per-request `AgentRun` Jobs the proxy creates are ordinary agent pods
carrying `sympozium.ai/role=agent`, so they are already covered by the same
policies a scheduled run uses.

### The `channel-slack` Deployments have no resource requests or limits

Every other workload the controller creates for a persona is bounded. The
`channel` container is the exception:

    kubectl get deploy -n automation \
      -o custom-columns='NAME:.metadata.name,RES:.spec.template.spec.containers[*].resources' \
      | grep -E 'channel|memory'

The memory sidecar carries `50m/64Mi` requests and `200m/128Mi` limits, taken
from its SkillPack's `spec.sidecar.resources`. The channel Deployment is built
from `spec.channels[]`, which has no equivalent field anywhere in the `Ensemble`
or `Agent` CRD — confirmed by searching both schemas for one:

    kubectl get crd ensembles.sympozium.ai agents.sympozium.ai -o json \
      | jq -r '[paths(objects) | select(.[-1]=="resources") | join(".")] | .[]'

So this is not settable from this repository, and not from core's values either.
Nor is it patchable the way core's other chart fixes are: `_kustomize.yaml.gotmpl`
patches chart-rendered resources, and these Deployments are created by the
controller at admission time, long after the chart is rendered. Five unbounded
pods sit in `automation` today — small ones, a websocket client each, but with no
request they are also the first thing the scheduler will misplace and the last
thing a node under pressure will evict fairly.

Two ways to close it, in preference order:

1. **Upstream** — a `resources` field on `ChannelSpec`, defaulted the way the
   SkillPack sidecar already is. This is the one worth filing.
2. **Core, as a stopgap** — a `LimitRange` in `automation` would give every
   container in the namespace a default request, which fixes this and changes
   the behaviour of everything else in a shared namespace. Only worth it if the
   unbounded pods actually cause a scheduling problem.

## A SkillPack overrode every tool decision in this repository

`endpoint-warden` delivered a placeholder, `sre-sentinel` reported no firing
alerts while four were firing, and `db-steward` wrote a whole daily report out of
its own memory. Three symptoms, one cause, and it was not context size: the
largest prompt Ollama saw across those runs was **15,294 tokens against
`n_ctx_slot = 65536`**, with no truncation. The per-run token figures on the run
list (199,130 for sre-sentinel) are *cumulative across LLM rounds*, not per call —
about 9k a round over 21 rounds. Read `n_ctx_slot` and `task.n_tokens` from
Ollama's slot log before blaming the window.

The cause was the mounted skill Markdown. `sre-observability`:

> You are running in-cluster with `kubectl`, `curl`, and `jq`. Use
> `execute_command` for all shell commands.

and `k8s-ops`:

> You are running inside a Kubernetes pod with full cluster admin access via an
> in-cluster ServiceAccount token. kubectl works out of the box ... You have RBAC
> permissions to read all resources cluster-wide and manage workloads in any
> namespace.

Every persona in `homelab-ops` carried one of the two. A 4B model follows that
over a nine-tool allowlist, and **the runner executes the call anyway**:

```
tool policy: denied tool "execute_command"     <- logged at startup
tools enabled: 9 tool(s) registered            <- schema not injected
tool call: execute_command args={"command":"kubectl get pvc -A ..."}
[tool-executor] exec [1787569...]: kubectl get pvc -A --no-headers (timeout=30s)
```

`toolPolicy` filters schema *registration*, not dispatch. The model learned the
name from the skill, emitted the call, and the skill sidecar ran it. **744 shell
commands executed across the fleet in the 7 days to 2026-08-24.** So
`toolPolicy.allow` is not the enforcing boundary it is described as anywhere else
in this file — a skill that names a tool is enough to get it back.

What each symptom actually was:

- **endpoint-warden, empty result.** 16 calls, 11 of them shell: `curl` against
  four guessed Prometheus URLs, then `ls /workspace`, `getenforce`, `ps aux`,
  `env | grep PROM`. Ended `WARNING: terminal turn had empty text`, so the
  delivery hook posted its placeholder. Not the iteration cap — 16 of 50.
- **sre-sentinel, wrong report.** 21 calls, 18 shell. Its two
  `grafana_query_prometheus` calls were correct and came *first*; 18 kubectl
  results then buried them and it wrote `Still firing: None` while Prometheus
  held `CPUThrottlingHigh`, `InfoInhibitor`, `NodeClockNotSynchronising` and
  `Watchdog`. `NodeClockNotSynchronising` is the real fault its own seeds say to
  report while it persists. Run 74, which stayed on the Grafana path, listed all
  four. The tool was never broken; the detour lost the answer.
- **db-steward, fabricated report.** A separate trigger, same skill:
  `endTime: "1725489600"` — 2024-09-04 — on all six queries, every one empty,
  "The tools are unavailable", then a full report from `memory_search` with a
  lifetime archiver count, "27 total backends" and "up from ~6.8%". The skill
  demonstrated `NOW=$(date +%s)` / `end=$NOW`; the model reproduced the shape
  without a shell to evaluate it. Rare but live: 528 calls sent `now`, 6 a stale
  epoch, 1 `2024-01-01T00:00:00Z`.

### The read-only guarantee was never real

The worse half. `k8s-ops` declares sidecar RBAC, and the controller realises it
per run as a Role plus RoleBinding in `automation` — 109 pairs had accumulated by
2026-08-24, owned by retained AgentRuns and so never collected. Every binding
targets the **shared `sympozium-agent` ServiceAccount**, which is the same
identity every agent pod in the namespace runs as. Verified:

```console
$ kubectl auth can-i --as=system:serviceaccount:automation:sympozium-agent -n automation create pods/exec
yes
$ ... delete deployments   -> yes
$ ... get secrets          -> yes
$ ... create rolebindings  -> yes
```

`create/patch` on `rolebindings` is a self-escalation path out of the namespace.
Because the SA is shared, it applied to `endpoint-warden` and
`renovate-reviewer` too, neither of which lists `k8s-ops`. It had been true since
2026-08-21. Nothing exploited it, and nothing in `projects/` would have stopped
it: a per-persona `toolsDeny` filters an MCP server, and this path used no MCP
server at all.

### The fix, and the rule that comes out of it

Both skills are gone from all five `homelab-ops` personas, which leaves `memory`
alone. They contributed nothing the pinned MCP tools do not already cover, and
`k8s-ops` additionally mandated its own `✅/⚠️/❌` output table, competing with the
persona's required section layout. Removing them deletes the sidecar, so the RBAC
is never created again. `scripts/validate.py` keeps them out by name
(`SHELL_TEACHING_SKILLS`) rather than by a general rule, because the objection is
to what these two say, and the 109 stale pairs need deleting once by hand:

```bash
kubectl get rolebinding,role -n automation -o name \
  | grep sympozium-skill- | xargs kubectl delete -n automation
```

`endTime` is now pinned to the literal `now` in all four Prometheus prompts, with
the reason stated — the model has no clock, so any timestamp it writes is
invented — and `_check_endtime_literal` enforces both halves. That is the `chatId`
lesson again: naming the argument is not enough, the prompt has to say what the
value may not be.

**The rule: a SkillPack is prose competing with the persona's own prompt, and
prose wins.** Read the Markdown of every pack before mounting it
(`kubectl get skillpack <name> -n automation -o json | jq -r '.spec.skills[].content'`)
and read `.spec.sidecar.rbac` with it, because mounting a pack grants its RBAC to
the whole namespace. Two skills per persona was a budget decision about
attention; it is now also a trust decision. `memory` and `code-review` were
checked and carry no sidecar, no RBAC and no shell instruction.

### The prompt to hand to `datahub-local-core`

Core owns the SkillPack objects, so two of the three fixes are its. The third is
upstream. Paste this as-is:

> The `k8s-ops` and `sre-observability` SkillPacks in `automation` are unsafe for
> a small local model and their RBAC leaks across the namespace. Two changes:
>
> 1. **Drop the write verbs from `k8s-ops`'s sidecar RBAC.** It currently grants
>    `create/update/patch/delete` on `pods`, `pods/exec`, `pods/portforward`,
>    `secrets`, `serviceaccounts`, `configmaps`, `deployments`, `statefulsets`,
>    `daemonsets`, `jobs`, `cronjobs`, `networkpolicies`, `ingresses`,
>    `horizontalpodautoscalers`, `poddisruptionbudgets` and — the one that makes
>    it an escalation path — `roles` and `rolebindings`. The controller realises
>    this per run as a Role + RoleBinding in `automation` bound to the **shared**
>    `sympozium-agent` ServiceAccount, so it applies to every agent pod in the
>    namespace, not only the ones that mount the pack. Verified on 2026-08-24:
>    `kubectl auth can-i --as=system:serviceaccount:automation:sympozium-agent
>    -n automation create rolebindings` answers `yes`. Nothing in this cluster
>    needs a skill to write to Kubernetes — the personas that do have MCP servers
>    for it. Cut the verb lists to `get,list,watch`, matching what
>    `sre-observability` already does.
> 2. **Stop the skill Markdown prescribing a shell.** `sre-observability`'s
>    prompt-query skill says "Use `execute_command` for all shell commands" and
>    demonstrates `NOW=$(date +%s)` / `end=$NOW`; `k8s-ops`'s cluster-overview
>    skill opens "You are running inside a Kubernetes pod with full cluster admin
>    access ... kubectl works out of the box" and then lists kubectl invocations.
>    Personas that deny `execute_command` in `toolPolicy` called it anyway — 744
>    shell commands across the fleet in the 7 days to 2026-08-24 — because the
>    deny filters schema registration, not dispatch, so naming the tool in prose
>    is enough to get it back. A pack should describe *what to look at*, not
>    which tool to reach for; the persona's `toolPolicy` decides that. While the
>    packs say otherwise, this repository cannot mount either of them.
>
> Also worth garbage-collecting: those per-run Roles and RoleBindings are owned
> by AgentRuns, which are retained, so 109 pairs had accumulated. Either set a
> retention on AgentRuns or give the RBAC objects a shorter-lived owner.
>
> The third fix is upstream (`sympozium-ai/sympozium`), and worth filing:
> `toolPolicy` must be enforced at tool *dispatch*, not only at schema
> registration. Today the runner logs `tool policy: denied tool
> "execute_command"`, omits the schema, and then executes the call if the model
> produces the name from anywhere else. Same failure mode as the other three open
> upstream bugs — the run reports `Succeeded` and quietly does something other
> than what it claims. Related: per-run skill RBAC should be bound to a
> per-instance ServiceAccount rather than the shared `sympozium-agent`.

## Known gaps

- **Slack is wired for `homelab-ops` only, and it now works.** Both halves that
  could not be checked before applying have been: the controller does turn
  `channelConfigs` into a per-agent `channel-slack` Deployment which reaches
  Slack with `SLACK_BOT_TOKEN`, and `send_channel_message` does take a
  destination — in `chatId`, not `channel`, which is
  [the trap that cost two days of reports](#send_channel_message-takes-the-destination-in-chatid-not-channel).
  What remains unverified is the inbound half: no @-mention has been tried
  against the bot.
- **A failed outbound send is only visible in the sidecar.** The tool answers
  `Message sent` before anything has been sent, so neither the agent, the
  `AgentRun` phase nor `status.result` can show a delivery failure — only
  `kubectl logs deploy/<persona>-channel-slack` can, and it logs failures only.
  Anything watching for "the reports stopped arriving" has to watch Slack or
  that log, not the run history. Related to `#monitoring-ai-runs` having no
  producer, below.
- **The HTTP endpoints are off again — resolved 2026-08-23.**
  `sympozium_web_endpoint.enabled` is `false`, and the schedules have been
  ticking since: `sre-sentinel` reached `schedule-75` by 06:08 on 2026-08-24.
  While it was `true` all five `homelab-ops` personas had a serving `AgentRun` in
  front of them and none ticked from 05:08 on 2026-08-23, with the
  `SympoziumSchedule`s still reading `Active` and nothing failing
  ([why](#the-endpoint-replaces-the-schedule--it-does-not-sit-beside-it)). Kept
  here because the failure is silent and the switch is meant to be flipped for
  tests: turning it on costs the fleet its heartbeat, and gaps appear in exactly
  the run-to-run memory the reports are diffed against.

  The endpoint itself now works — the earlier NetworkPolicy failure written up
  [above](#sympozium-allow-otel-strangles-the-web-proxy-pods) no longer bites,
  and web requests produce complete runs. What it still does is
  [drop the persona's `toolPolicy`](#a-web-endpoint-run-drops-the-personas-toolpolicy-entirely)
  and [truncate the task to its first line](#a-web-endpoint-run-also-truncates-the-task-to-its-first-line),
  so a run started this way is neither as restricted nor as fully instructed as
  the same persona on its cron. For anything where that matters, a hand-applied
  `AgentRun` remains the honest test.
- **`NodeClockNotSynchronising` is a true positive — do not seed it.** It fires
  on `datahublocal-orpi-0` through `-3` and is absent from `sre-sentinel`'s seeds,
  which was initially read as seed drift. It is not. The four Orange Pis run no
  time daemon at all: `node_systemd_unit_state{name="systemd-timesyncd.service",
  state="active"}` is `0` on each, against `1` on both amd nodes, and the NAS
  runs `chrony` instead. With nothing telling the kernel it is synchronised,
  `node_timex_sync_status` is `0` and the alert is correct.

  No clock has actually drifted yet — `max(abs(node_timex_offset_seconds))`
  across the fleet is 575 microseconds — so this is a latent fault rather than a
  live one, and it will only widen while no daemon is running. The fix is at the
  node (enable and start `systemd-timesyncd` on the four SBCs), not in this
  repository and not in the seeds: seeding it would teach the agent to ignore the
  one alert here that is telling the truth.

  Worth noting *how* this was diagnosed, because it is the argument for the point
  above. Before core enabled `--collector.systemd` the alert was
  indistinguishable from the chronic noise — there was no way to ask why the
  kernel thought it was unsynchronised. One metric turned a guess into a
  one-query answer.
- **Channels are named, not `C0…` ids.** Slack accepts a name for
  `chat.postMessage`, but it is the legacy form and it breaks silently on a
  rename. Swapping is a one-line values change per channel.
- **`#monitoring-ai-runs` has no producer yet.** A failed `AgentRun` notifies
  nobody: an agent that cannot run cannot report that it cannot run, which is
  exactly how the Ollama restart on 2026-08-22 cost three runs in silence. That
  signal has to come from outside the fleet — an alert on `AgentRun` phase, or an
  n8n workflow polling it, alongside `Catch Errors` which already does this job
  for n8n.
- **A Slack binding is also an inbound path.** `slackOptions.allowedTriggers:
  [mention]` keeps it to an explicit @-mention rather than every message in the
  channel, which matters when one GPU serves the whole fleet. Narrow it further
  with ensemble-level `channelAccessControl` (`allowedChats`, `allowedSenders`)
  once the channel and user ids are known; today anyone in the workspace who
  @-mentions the bot can start a read-only run.
- **`endpoint-warden` has no host access.** "Maintaining the machines" is done
  through node-exporter metrics in Grafana, not host mounts, so the agent stays
  unprivileged. Stalls, disk health, temperature, memory errors, power, version
  drift and uptime are all reachable that way; anything genuinely needing the
  host is not in scope.
- **Nothing here deletes.** `service-janitor` reports cleanup and prints the
  commands; a human runs them. Auto-cleanup would be a separate, deliberately
  authorised agent.
- **Expiry is split with n8n on purpose.**
  [`credentials_expiry_review`](../n8n/workflows/credentials_expiry_review.workflow.json)
  owns n8n credential expiry, and its dataset documents at length why that date
  lives in the credential's name. `service-janitor` stays strictly cluster-side
  — certificates, tokens, secrets — so the two never contradict each other.

## Open, and not ours

- `TargetDown{job="longhorn-backend"}` has been firing since the Longhorn
  v1.12.1 bump on 2026-08-24: all five `longhorn-manager` pods answer
  `connection refused` on :9500 while the manager itself reconciles replicas
  normally. A scrape target left stale by the upgrade. The config lives in
  datahub-local-core.
- The channel sidecar fan-out — every slack sidecar delivers every instance's
  outbound message — is one line upstream: filter on `metadata.instanceName`,
  which the envelope already carries. `deliveryMode: hook` avoids it meanwhile.
  See `#every-report-arrived-five-times-and-only-one-agent-sent-it`.
