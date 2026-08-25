# Sympozium rebuild plan

Transient document. Delete it when the rebuild lands; the durable lessons belong
in `MEMORY.md`, the structure in `README.md`, the conventions in
`/CLAUDE.md`. Written 2026-08-25 against Sympozium **v0.10.47**,
k3s **v1.36.2**, agent-sandbox **v0.5.6**.

It is written to be executed **without** the conversation that produced it. Every
factual claim below was read off the running cluster or the repos on
2026-08-25 — Section 3 is the part not to re-derive.

---

## 1. Status and decisions

### Where things stand

The fleet is **gone**, deliberately removed before this rebuild starts:

- no `Agent`, no `SympoziumSchedule`, no `Ensemble` named `homelab-ops` or
  `homelab-reviewer` in `automation`
- no `<persona>-memory` Deployments, Services or PVCs — **all accumulated agent
  memory is destroyed**, which is a feature here (see Section 7)
- the ArgoCD `Application` for `agents/sympozium/` is deleted
- the eight chart example ensembles remain, all `Inactive` — leave them
- 12 orphaned `AgentRun`s remain from hand-applied probes (Section 7)

So this is greenfield. There is nothing to migrate and no live reports to protect.

### Decisions taken (do not relitigate)

| Decision | Choice |
|---|---|
| Where deterministic gathering lives | A **repo-local MCP server** we own |
| Container images in this repo | **Yes** — first image this repo ships |
| Platform-object ownership | **This repo** ships its own `MCPServer` / `SkillPack` / `SympoziumPolicy` alongside its `Ensemble`s |
| Sequencing | **From scratch**, fleet already torn down |
| Raw k8s + Prometheus access | **Kept.** The facts server reduces load; it must not reduce reach |
| Slack Q&A | **Kept and promoted** to its own persona |

---

## 2. Why rebuild

Every failure in this fleet was a **tool-loop** failure, not a writing failure.

A 4B model was made a careful API client: assemble `100*(1-avail/cap)` with a
`group_left` join, remember `increase(m[1h])` is not `m[1h]`, pass `endTime: now`
bare, diff alerts against its own memory, know orpi-0's kernel is not drift.
Every incident added a paragraph to a prompt and a regex to the validator. The
result: system prompts of 6-12KB, and `scripts/validate.py` at 1,473 lines of
which roughly 600 are nine regex functions policing English —
`_check_fill_direction`, `_check_counter_window`, `_check_endtime_literal`,
`_check_unquoted_args`, `_check_datasource_uid`, `_check_nodename_join`,
`_check_investigation_budget`, `_check_k8s_selector_rules`,
`_check_verbatim_ascii`.

That loop did not converge. The last `sre-sentinel` run before teardown
(`homelab-ops-sre-sentinel-schedule-79`, 2026-08-25T06:08Z) is the whole problem
in one trace:

```
tool_calls=19  input_tokens=262617  cached=0  tool_result_bytes=44115
13 consecutive calls hunting namespace "datahub-local-ai-sympozium", which does not exist
WARNING: terminal turn had empty text after 14 tool iterations
status.result = "(Agent completed its task via tool calls but did not produce a final text summary.)"
```

The delivery hook then posted its placeholder to Slack. The two mandatory
readings had already succeeded in calls 1 and 2; everything after was drift.

**The fix is to stop asking the model to gather.** Code gathers; the model writes.

---

## 3. Verified constraints

Read off the cluster and the repos on 2026-08-25. Do not re-derive these; do
re-check anything marked *version-sensitive* after a control-plane bump.

### 3.1 A SkillPack cannot carry tool wiring

`SkillPack.spec` is exactly: `category`, `version`, `source`,
`runtimeRequirements{image,minCPU,minMemory,sandbox}`, `sidecar{...}`, and
`skills[]{name, description, content, requires{bins,tools}}`.

There is **no** field for MCP servers, no `toolsAllow`, no `toolPolicy`, and no
parameter substitution into `content`. `requires.tools` is documentation — nothing
reads it. `skillParams` is passed to the *sidecar*, not interpolated into prose.

So "a SkillPack with the right tools and MCP calls" is not expressible. A
SkillPack can carry **prose** and **a sidecar container with RBAC**, nothing else.

Unverified and gating (Phase 0.2): whether `skills[].content` reaches the model's
context, or whether `/skills` is a directory needing `read_file`. A run logs
`skills.loaded count=1 dir=/skills`, which does not settle it.

### 3.2 Two unused mechanisms are the real levers

- **`lifecycle.preRun`** hooks are **init containers**, with access to
  `/workspace`, `/ipc`, `/tmp`. Reserved volumes are `workspace`, `ipc`, `skills`,
  `tmp`, `memory`, `mcp-config`.
- **`lifecycle.postRun[].gate: true`** holds the agent's output until the hook
  "approves, rejects, or **rewrites** it by patching the annotation
  `sympozium.ai/gate-verdict`". At most one postRun hook may set it. `gateDefault`
  is `allow` (pass through) or `block` (replace). Hooks receive `AGENT_RESULT` and
  `AGENT_EXIT_CODE` as env.

A gate hook is therefore the mechanism for: substituting a deterministic
rendering when the model returns nothing, appending authoritative figures, and
stamping a real timestamp.

### 3.3 `toolPolicy` lives on the AgentRun, and only the scheduler sets it

- `Agent.spec.agents.default` carries `agentSandbox`, `baseURL`, `env`,
  `lifecycle`, `model`, `nodeSelector`, `providerHeaders`,
  `providerHeadersSecretRef`, `runTimeout`, `sandbox`, `subagents`, `thinking`.
  **No `toolPolicy`.**
- `SympoziumSchedule.spec` carries `agentRef`, `concurrencyPolicy`, `firstTick`,
  `includeMemory`, `schedule`, `task`, `type`. **No `toolPolicy`.**
- `AgentRun.spec` **does** carry `toolPolicy`.

Verified by inspection:

| Run | `toolPolicy` | `lifecycle` |
|---|---|---|
| `...-schedule-79` (scheduled) | present, 7 allow / 2 deny | present |
| `...-ch-g44pj`, `...-ch-mq7lc` (inbound Slack) | **null** | present |
| `...-web-nxr4d` (web endpoint) | **null** | **null** |

So an inbound Slack mention gets **every built-in tool** — `write_file`,
`execute_command`, `fetch_url`, `delegate_to_persona`, `schedule_task` — and a web
run additionally loses the delivery hook, which is how a web run once wrote a full
CRITICAL report and delivered none of it.

### 3.4 What is and is not a boundary

| Mechanism | Enforcing? |
|---|---|
| `mcpServers[].toolsAllow` | **Yes.** Runs at the MCP bridge, survives inbound and web runs |
| No skill sidecar mounted | **Yes.** `execute_command` has nothing to execute |
| `toolPolicy` | **No.** Applied at schema *registration*, not dispatch. The runner logs `tool policy: denied tool "execute_command"`, omits the schema, and still executes the call if the model produces the name |
| `SympoziumPolicy.featureGates` / `toolGating` | **Unknown** — Phase 0.1 |
| Agent Sandbox | **Not yet** — no RuntimeClass, Section 6 |

`policyRef: permissive` currently means `featureGates: {browser-automation: true,
code-execution: true, file-access: true, sub-agents: true}`,
`toolGating.defaultAction: allow`, `sandboxPolicy.required: false`,
`networkPolicy.denyAll: false`.

`restrictive` and `network-isolated` are both unusable as-is: each sets
`networkPolicy.denyAll: true` with no `allowedEgress`, cutting agents off from
Ollama *and* every MCP server. `restrictive` additionally gates
`toolGating.defaultAction: deny` against a rule list holding only built-in names,
denying every MCP tool.

`SympoziumPolicy.spec` fields available to a custom policy: `featureGates`,
`imagePolicy.allowedRegistries`, `lifecyclePolicy.deniedResources`,
`modelPolicy.{allowedModels,allowedNamespaces}`,
`networkPolicy.{allowDNS,allowEventBus,allowedEgress[],denyAll}`,
`sandboxPolicy.{required,defaultImage,maxCPU,maxMemory,allowHostMounts,seccompProfile,agentSandboxPolicy{required,allowedRuntimeClasses,defaultRuntimeClass}}`,
`subagentPolicy`, `toolGating.{defaultAction,rules[]}`.

Note `networkPolicy.allowedEgress[]` takes `{host, port}` where host is "host or
CIDR" — whether the controller can translate a Service DNS name into a
NetworkPolicy peer is **unverified**. Assume CIDR until proven.

### 3.5 Ensemble/persona fields worth using that the old tree ignored

Persona (`agentConfigs[]`): `channels`, `channelConfigs`,
`channelAccessControl`, `channelTriggers`, `slackOptions`, `env`, `lifecycle`,
`mcpServers`, `memory`, `skills`, `skillParams`, `subagents`, `systemPrompt`,
`toolPolicy`, `webEndpoint`, `schedule`, `runTimeout`, `model`, `provider`,
`baseURL`, `displayName`, `providerHeaders`, `providerHeadersSecretRef`.

`webEndpoint` is now a **first-class persona field** (`{enabled, hostname,
rateLimit{requestsPerMinute,burstSize}}`) — the `web-endpoint` SkillPack plus
`skillParams` dance in the old chart is obsolete.

Ensemble level adds: `agentSandbox`, `channelTriggers`, `slackOptions`,
`channelAccessControl`, `channelVolumes`, `channelVolumeMounts`, `stimulus`,
`relationships`, `taskOverride`, `excludePersonas`, `modelRef`, `authRefs`,
`autoStoreMemory`, `sharedMemory`, `skillParams`, `volumes`, `volumeMounts`,
`providerHeaders`, `policyRef`, `baseURL`, `workflowType`.

Channel controls, all unused before and all needed by the responder:

- `slackOptions.{threading, threadStickiness, allowedTriggers[], emojiOnTrigger,
  emojiOnStart, emojiOnStop}` — `allowedTriggers` accepts `mention`, `dm`,
  `channel`
- `channelTriggers.{startKeywords[], stopKeywords[]}` — mute/resume per chat
- `channelAccessControl.{allowedSenders[], allowedChats[], deniedSenders[],
  denyMessage}` — **inbound only**. Empty `allowedSenders` means anyone in the
  workspace who can reach the bot can start a run.

### 3.6 An MCPServer can point at a Deployment we own

`MCPServer.spec`: `deployment` (managed), `url` (external/pre-existing — *"no
deployment created"*), `replicas`, `suspended`, `timeout`, `toolsAllow`,
`toolsDeny`, `toolsPrefix`, `transportType` (`stdio`|`http`).

Core already uses the `url:` form for `mcp-k8s` and comments why: setting `url`
stops the controller reconciling a deployment of its own. Copy that pattern.

**Critical detail:** core's `agent-allow-tools` NetworkPolicy opens egress on port
8080 only toward `podSelector` `sympozium.ai/component: shared-memory` and
`app.kubernetes.io/name: mcpserver`. Our facts-server pods **must carry
`app.kubernetes.io/name: mcpserver`** or every call times out with no useful error.

Note the shared-memory key is `sympozium.ai/component`, not
`app.kubernetes.io/component` — the same label confusion §5.3 warns about, where
`allow-eventbus` grants 8080 to `sympozium.ai/component: memory` instead.

### 3.7 The model constrains the design

Inference is cluster-local Ollama, one 6 GiB GPU, one resident model. Only
`qwen3.5:4b` is pulled (4.7B params, 3 GB). Hence `workflowType: autonomous`,
short allowlists, and staggered schedules.

*Version-sensitive:* core commit `f58529a` ("increase context length and add KV
cache configuration") landed after the 65,536 figure in `/CLAUDE.md` was measured.
**Re-read the effective value from `GET /api/ps` with the model resident** — not
`/api/show`, which reports the architecture ceiling. The whole token budget rests
on it. See Phase 0.3.

The Ensemble controller starts a run within the same second as every
`SympoziumSchedule` it rewrites, whatever `firstTick` says. One `helmfile apply`
touching N personas queues N real runs against one Ollama slot. Apply once; probe
with a hand-applied `AgentRun`. Do not answer the queueing with
`OLLAMA_NUM_PARALLEL` — llama.cpp divides `n_ctx` across slots.

### 3.8 `MAX_TOOL_ITERATIONS`

The runner caps tool calls per run at 50 by default; hitting it ends the run
`status: error`, so `lifecycle.postRun` never fires and **nothing arrives at
all**. Both old ensembles set `"100"` in `defaults:` — quoted, because the CRD
types `env` as `map[string]string` and the webhook decodes strictly.

---

## 4. Target architecture

### 4.1 New sub-project: `agents/mcp/`

Follows the `workflows/dbt` / `workflows/dlt` shape exactly, per `/CLAUDE.md`
naming conventions.

```
agents/mcp/
  src/mcp_runner/
    __main__.py            python -m mcp_runner --project homelab_facts [--port 8080]
    server.py              MCP plumbing, tool registration, /healthz
    prometheus.py          the ONLY place that knows the uid, endTime, instant vs range
    kube.py                Kubernetes client
    postgres.py, argocd.py
    state.py               previous-snapshot persistence
  projects/homelab_facts/
    tools/alerts.py        alerts_snapshot()
    tools/volumes.py       volume_fill()
    tools/nodes.py         node_fleet()
    tools/databases.py     postgres_health(), cache_health()
    tools/lifecycle.py     cert_expiry(), backup_freshness()
    tools/gitops.py        argocd_drift()
    tools/raw.py           promql()
    config/chronic_alerts.yaml
    config/hardware_classes.yaml
    config/thresholds.yaml
  tests/homelab_facts/
  Dockerfile               multi-arch: arm64 AND amd64 (agents land on Orange Pis)
  pyproject.toml           name: datahub-local-ai-mcp
  README.md
```

Package `datahub-local-ai-mcp`, module `mcp_runner`, entry point
`python -m mcp_runner`, project dirs `lowercase_underscores`. A second MCP server
later is another `projects/<name>/`.

### 4.2 The two tool tiers

The facts server does **not** replace reach. Every persona gets both tiers.

**Tier 1 — facts tools.** The mandatory sweep, one call per report section,
correct by construction:

| Tool | Subsumes |
|---|---|
| `alerts_snapshot()` | the `ALERTS{alertstate="firing"}` query **plus** the new / still-firing / resolved diff, computed in code against a stored snapshot |
| `volume_fill()` | the full `group_left` expression, already the *used* fraction, already filtered to `longhorn\|longhorn-no-replica` |
| `node_fleet()` | the entire node table — disk, temp, PSI, EDAC, SMART, UPS, pending updates, kernel grouped by hardware class |
| `postgres_health()` | archiver **increase**, backends, database and volume sizes, top queries |
| `cache_health()` | Valkey via `redis_*` |
| `cert_expiry()`, `backup_freshness()` | dates read off resources |
| `argocd_drift()` | sync/health state **plus** consecutive-run persistence |
| `promql(expr)` | arbitrary Prometheus, with uid / `endTime` / `queryType` supplied server-side |

**Tier 2 — raw tools, unchanged.** `k8s_resources_list`, `k8s_events_list`,
`k8s_pods_log`, `k8s_pods_list`, `k8s_nodes_top`,
`grafana_query_prometheus`, and the github/argocd/postgres tools as before. These
are for following up on whatever tier 1 surfaces.

The win is **budget reallocation**, not fewer tools. The mandatory readings drop
from 8+ calls to 1-2, leaving the iteration budget for real investigation — which
is exactly where the last run ran out and drifted.

Three properties that remove failure classes structurally rather than by
instruction:

1. **The diff is computed, not remembered.** "New vs chronic" stops depending on
   a model reading memory seeds. The chronic set becomes
   `config/chronic_alerts.yaml` — reviewable in git.
2. **Absence is a value.** A missing metric returns the literal `unavailable`, so
   a mandatory report format can never force an invented number.
3. **The server holds state**, so a trend claim is real rather than asserted.

Each of the nine prose validators becomes a pytest over the join, the increase
window, the inversion, or the absence path.

#### Two hard requirements, both learned the expensive way

**Every tool output needs a bounded size, enforced in code.** "Fat tool" means
*few calls*, never *big answers*. A single ~16 KB tool result is enough on its own
to end a run with no report: `gitops-auditor` on 2026-08-24 made four calls for
`tool_result_bytes=24126` and produced `terminal turn had empty text`, where its
run four hours earlier made five calls for 8,483 bytes and wrote a normal report.
The difference was one tool, `argocd_get_application_resource_tree`, worth ~16 KB
by itself. **This was not a context overflow** — cumulative input was 25,423
tokens against the 65,536 window. A 4B model simply stops producing a final turn
when one answer is that large. It is the same empty-terminal-turn mechanism as the
failed-lookup spiral, reached by volume instead of iteration count.

So each facts tool declares a byte budget, truncates server-side, and *says* it
truncated. A tool whose answer has no natural bound is a liability at this model
size in exactly the way a tool returning several plausible identifiers is. Put the
budget in the tests.

**`node_*` series in this Prometheus carry no machine name.** They are keyed by
`instance`, so any per-node table has to join them to node identity server-side.
The old fleet's model did the join itself and the 2026-08-24 13:25 table was wrong
in five ways at once: four rows said `unavailable` when every figure was
available, the NAS was given amd-1's disk percentage, orpi-1 got roughly orpi-3's,
every uptime was wrong by two orders of magnitude, three ARM nodes with 5 pending
security updates were reported as having none, and the single Finding named
amd-1's CPU pressure at 52.7% against a real 0.47% — the loaded machines were
orpi-1/2/3. `node_fleet()` owns that join, and a per-row identity test is the
first thing to write.

**Query Prometheus directly, not through Grafana.** Verified reachable from
`automation`: `http://datahub-local-core-kube-pr-prometheus.monitoring.svc:9090`
answers `/api/v1/query?query=up` with HTTP 200, and `monitoring` has no
NetworkPolicies. Going direct deletes the entire datasource-uid failure class —
no uid to resolve, no `endTime` literal, no Loki to be mistaken for Prometheus.

`promql()` is what lets `prompts/shared/promql.md` be deleted — 2.3KB of prose
explaining that `endTime` is the literal word `now`, three characters.

Keep `k8s_resources_get` banned. Core's ClusterRole is `apiGroups: ["*"],
resources: ["*"], verbs: [get,list,watch]` — deliberately widened in commit
`91b4d58` so agents can read velero, cnpg, longhorn and cert-manager objects — so
`k8s_resources_get` on a Secret returns the base64 values in full.
`k8s_resources_list` returns a table and is the right shape for a reporter.

### 4.3 `agents/sympozium/` changes

The sub-project root stays the chart root (Helm's `.Files` cannot read above it).
New templates:

```
templates/
  ensembles.yaml     much thinner: no {{ TOKEN }} substitution, no render guards
  mcpservers.yaml    Deployment + Service + MCPServer for homelab_facts
  policy.yaml        SympoziumPolicy (only if Phase 0.1 says it bites)
  skillpacks.yaml    only if Phase 0.2 says skill content reaches the model
```

`values/default.yaml.gotmpl` keeps per-cluster knobs only: `enabled`, `baseURL`,
`policyRef`, `channelConfigs`, the delivery destinations, and the facts-server
image tag. Per-persona `model`/`provider`/`runTimeout` stay in the project's
`defaults:` block — they describe the agent, not the cluster.

### 4.4 Reporters and one responder

Two shapes, split because they conflict structurally.

**Reporters** — scheduled, both tool tiers, `postRun` hook delivery plus a
`gate: true` hook, **no** channel binding and therefore no inbound path. The
system prompt shrinks to a report contract, because the method left the prompt.

**One responder** — the Slack Q&A persona:

- `channels: [slack]`, and it is the **only** bound persona. Every channel sidecar
  delivers every instance's outbound message on an unfiltered fleet-wide
  JetStream consumer, so N bound personas means N byte-identical copies. One
  binding is the fix available to us.
- **No `postRun` hook.** The hook hardcodes a destination: both inbound questions
  before teardown were asked in *different* channels and both answers landed in
  `#monitoring-ai-alerts`. Without the hook, replies flow through the channel
  sidecar back to the asking thread.
- `slackOptions: {threading: true, threadStickiness: true, allowedTriggers:
  [mention, dm]}` so follow-ups in a thread do not need re-mentioning.
- `channelAccessControl: {allowedSenders: [<your Slack user id>], denyMessage:
  "..."}` so a reject is visible rather than silently dropped.
- `channelTriggers: {stopKeywords, startKeywords}` for muting a busy thread.
- **A conversational prompt, not a report format.** The observed failure was a
  report prompt fighting a legitimate question: asked "how to fix
  NodeClockNotSynchronising in dietpi and truenas?", the persona answered *"this
  request doesn't fit the SRE Sentinel monitoring workflow"*. Advisory contract,
  both tool tiers, no mandatory sections.
- Its `toolPolicy` is **not** a boundary on this path (3.3). Its real bounds are
  `mcpServers[].toolsAllow` and mounting no skill sidecar. Size the `toolsAllow`
  list accordingly.

Note the binding is bidirectional, which is why only a read-only persona may
carry one. Anything holding a write tool — the old `renovate-reviewer`, which may
only comment — stays unbound, in its own ensemble, split on the trust boundary.

### 4.5 Delivery

Keep `deliveryMode: hook` as the default: a `lifecycle.postRun` container posts
`AGENT_RESULT` to the Slack API directly, touching no shared subject, so a report
arrives exactly once regardless of how many personas exist. Egress works because
the hook pod carries no `sympozium.ai/role=agent` label and so escapes
`sympozium-agent-deny-all`.

Two consequences are the point rather than side effects: a hook-mode persona must
**not** allowlist `send_channel_message` (or it posts *and* is posted for, and the
run ends on a tool call), and the report becomes the model's final text.

**Add the `gate: true` hook.** With facts pre-computed the model's output shape is
tight, so a gate can render the facts table deterministically and append the
model's prose. A run then cannot post a placeholder, and no figure in the table
was ever the model's to invent.

`files/deliver-slack.sh`'s eight `sed` expressions are a markdown-to-mrkdwn
transpiler in shell. With output shape constrained by the gate, most of it can go;
consider Slack `blocks` assembled in the gate container instead.

---

## 5. Changes needed in `datahub-local-core`

> **Status 2026-08-25: 5.1, 5.2, 5.4 and 5.6 are DONE. 5.3 is written but
> UNCOMMITTED. 5.5 is WAIVED.** Landed on core `main` as `8ba20df`, `fa0242b`,
> `e745620`. Both admission objects are live, the run-pruner CronJob is armed at
> `0 3 * * *` and unsuspended, no probe leftovers remain, and the admission floor
> was verified in both directions (deny list injected on runs with no
> `toolPolicy`; existing policies untouched). 5.2 deleted, 5.4 no action, 5.6
> technique exercised with no drift. Note `fa0242b`: the mutation ships as a
> JSONPatch, not an ApplyConfiguration.
>
> **5.3 is the open item.** The edit exists in core's working tree and is not
> committed, so ArgoCD reports `Synced` against a revision without it and the live
> policies still carry the sandbox exclusion — the same trap that left fix (6)
> sitting for a day. Commit it; see §5.3.
>
> **5.5 was waived by decision, not completed.** No ArgoCD `Application` will be
> re-registered for `agents/sympozium/`. Consequences, accepted: deploys are
> `helmfile apply` by hand, drift against git is invisible rather than reported,
> and a teardown is not reproducible from git. Nothing about the rebuild is
> blocked — personas arrive via helmfile and the admission floor starts guarding
> them the moment they exist.


### 5.1 Commit the uncommitted `toolPolicy` admission floor — highest value

`releases/automation/templates/sympozium_upstream_fixes.yaml` contains a written,
commented "fix (6)": a `MutatingAdmissionPolicy` +
`MutatingAdmissionPolicyBinding` that defaults `spec.toolPolicy.deny` on any
`AgentRun` created without one, matched on `!has(object.spec.toolPolicy)`, with
`failurePolicy: Fail`.

It is **not deployed**:

```
$ git status --short          # in datahub-local-core
M  releases/automation/templates/sympozium_upstream_fixes.yaml
M  releases/automation/values/_kustomize.yaml.gotmpl
M  values/_version.yaml
$ git log -S 'agentrun-default-toolpolicy' -- releases/automation/templates/sympozium_upstream_fixes.yaml
(nothing)
$ kubectl get mutatingadmissionpolicy
No resources found
```

It is staged but never committed, so ArgoCD reports `Synced` against a revision
that does not contain it. k3s is v1.36.2 and **does** serve
`admissionregistration.k8s.io/v1` for `MutatingAdmissionPolicy` /
`MutatingAdmissionPolicyBinding`, so the manifest is correct as written.

Commit and push it, then verify the object exists and probe with a hand-applied
`AgentRun` carrying no `toolPolicy` — `failurePolicy: Fail` means a CEL error
stops every run.

Scope honestly: this removes denied tools from the schema the model is *offered*,
which is the observed attack path. It is not dispatch-time enforcement.

Also decide what to do with the other two modified files in that working tree
before committing — they are unrelated to this plan and unreviewed here.

### 5.2 Remove the leftover egress NetworkPolicy

`zz-temp-claude-agent-server-egress-test` in `automation`, created
2026-08-23T08:56Z as a diagnostic and never removed. It selects
`sympozium.ai/component: agent-server` and grants egress to **ports 443 and 6443
with no `to:` selector** — any destination — plus 11434/11435 likewise. Its
intended function is now served properly by
`datahub-local-core-automation-sympozium-web-proxy-allow-egress`. Delete it.

### 5.3 Let sandboxed agents reach MCP and OTel — after the rebuild, not before

**Do not deploy a throwaway persona to investigate this.** The fleet is being
recreated from zero; the observation this needs arrives for free on the first real
sandboxed run in Phase 4. Nothing here blocks the rebuild.

#### Corrected picture (re-measured 2026-08-25)

An earlier draft of this section claimed that enabling `agentSandbox` "cuts every
agent off from Ollama *and* every MCP server". That is wrong about Ollama; it was
written after reading only core's two policies. (`/CLAUDE.md` says nothing about
sandbox networking and needs no correction — its "cut off from Ollama and every
MCP server" line is about `SympoziumPolicy.networkPolicy.denyAll` on the
`restrictive`/`network-isolated` policies, which is a different mechanism and
still accurate.) Five policies select agent pods; only two exclude sandboxes:

| Policy | Selector | Excludes sandbox? |
|---|---|---|
| `sympozium-agent-deny-all` | `sympozium.ai/role=agent` | no (it grants nothing) |
| `sympozium-agent-allow-eventbus` | `sympozium.ai/role=agent` | **no** |
| `...-core-...-agent-allow-tools` | `role=agent` + `sandbox DoesNotExist` | **yes** |
| `...-core-...-agent-allow-otel` | `role=agent` + `sandbox DoesNotExist` | **yes** |
| `sympozium-sandbox-restricted` | `role=agent` + `sandbox=true` | n/a |

`sympozium-agent-allow-eventbus` carries **no sandbox exclusion** and already
grants, to any destination unless noted: 53 DNS, 443, 6443, 9473, **11434**,
**11435**, 4222 to nats, and 8080 to `sympozium.ai/component=memory`,
`app.kubernetes.io/name=model` and `app.kubernetes.io/component=apiserver`.

So for a sandboxed agent pod carrying `sympozium.ai/role=agent`:

- **Ollama already works** — 11434/11435, no exclusion, any destination.
- **MCP on 8080 does not.** That policy's 8080 rules do not include
  `app.kubernetes.io/name: mcpserver`; only core's `agent-allow-tools` grants it,
  and that one excludes sandboxes.
- **OTel 4317/4318 does not**, for the same reason.

NetworkPolicy egress is an allow-list **union** across every policy selecting a
pod, so `sympozium-sandbox-restricted` cannot subtract anything another policy
grants. It is not the obstacle; the two exclusions are.

#### The change — written by the core agent 2026-08-25, NOT YET DEPLOYED

Both exclusions are dropped from core's `...-sympozium-agent-allow-tools` and
`...-sympozium-agent-allow-otel` in
`releases/automation/templates/sympozium_upstream_fixes.yaml`, with
`matchExpressions` collapsed to `matchLabels: {sympozium.ai/role: agent}` — the
`In [agent]` expression was doing what one label does.

**Status: uncommitted.** `git status` shows the file modified but unstaged; the tip
is still `e745620`, which does not contain it; and the live policies still carry
`sympozium.ai/sandbox: DoesNotExist` on both. ArgoCD reports `Synced` against a
revision without the edit — the same trap that left fix (6) sitting for a day.

```bash
cd datahub-local-core
git add releases/automation/templates/sympozium_upstream_fixes.yaml
git commit -m "fix(sympozium): let sandboxed agents reach MCP, shared memory and OTel"
git push
# then confirm the exclusion is gone:
kubectl -n automation get netpol \
  datahub-local-core-automation-sympozium-agent-allow-tools \
  -o jsonpath='{.spec.podSelector}'
```

Three destinations were genuinely unreachable for a sandboxed pod and are the
whole point of the change:

| Destination | Port |
|---|---|
| `app.kubernetes.io/name: mcpserver` | 8080 |
| `sympozium.ai/component: shared-memory` | 8080 |
| `app.kubernetes.io/name: sympozium-otel-collector` | 4317/4318 |

**The shared-memory one is easy to misread.** `allow-eventbus` grants 8080 to
`sympozium.ai/component: memory` — a *different label value* from the
`shared-memory` core's policy targets, which is fix (1)'s subject in that file's
header. So shared memory sat in the same hole as MCP and was not covered by the
eventbus policy.

The plan's other option — "accept sandboxing only for personas that need no MCP"
— was never actually available: without the collector rule even an MCP-free
sandboxed persona loops on OTLP export failures, which is fix (3)'s subject.

Scope, stated honestly by the author: this relaxes the sandbox's *egress* intent.
Upstream's "reach nothing but its siblings" no longer holds and that comment was
removed rather than left contradicting the code. What survives is the isolation
that matters for a sandbox — **no ingress, and the gVisor kernel boundary**. Egress
is now the same allowlist a normal agent gets.

Nothing changes on the sync that lands it: `agentSandbox` is off and no pod carries
the sandbox label.

#### Two checks on the first sandboxed run, and they are not the same check

**Connectivity** — the path that was silently broken: a sandboxed agent pod
resolves and connects to its MCP server on 8080. That is what the change above
fixes.

**Governance** — which the change deliberately does not address, and should not.
Does the `agentSandbox` run pod carry `sympozium.ai/role=agent` at all? If it does
not, *no* policy selects it — `sympozium-agent-deny-all` included — so it has
**unrestricted egress**, and the sandbox is less contained than an ordinary agent
while connectivity looks perfect. So on the **first real sandboxed run in Phase
4**:

```bash
kubectl -n automation get pod <run-pod> --show-labels
```

- carries `sympozium.ai/role=agent` → governed, and the edit above is sufficient
- does not → the run pod escapes `sympozium-agent-deny-all` entirely and needs its
  own policy written against whatever labels it does carry

Note `sympozium.ai/sandbox=true` most likely belongs to the legacy per-agent
`spec.sandbox` sidecar rather than the `agentSandbox` CRD backend, which is
exactly why this is an observation and not an assumption. Do not write netpol
changes speculatively — `mcp-k8s` 404'd for three days behind a
`status.ready: true` for that reason.

#### Sequencing

Sandboxing is **post-rebuild hardening**. Phase 4 builds personas with
`agentSandbox.enabled: false`; this section and the flip to `true` come after the
fleet is working, on one persona first. Record the label answer in `MEMORY.md`
when it arrives.

### 5.4 Consider adding the facts server to core's catalog instead — decided against

Noted so it is not reopened. `defaultMcpServers.enabled: false` and core owns the
catalog in `sympozium_mcp_servers.yaml`, so core is the conventional home for an
`MCPServer`. The decision in Section 1 puts ours in this repo because its logic is
specific to these agents and belongs beside the personas that depend on it. Risk
accepted: two repos declaring objects in `automation`. Keep names prefixed
(`datahub-local-ai-*`) so ownership is legible.

### 5.5 Re-register the ArgoCD Application

**This cannot delete data. Verified 2026-08-25 — read this section before
hesitating over it.**

#### Why it has to happen

The Application for `agents/sympozium/` was hand-applied — no `ownerReferences`,
only a `kubectl.kubernetes.io/last-applied-configuration` annotation — and is now
deleted. Core's only `ApplicationSet` (`automation/datahub-local-core`) generates
core's own seven releases and does **not** reference `agents/sympozium`; grep for
`agents/sympozium` across core finds nothing.

Three consequences, in order of how much they hurt:

1. **No GitOps for this sub-project.** Every change means `helmfile apply` by
   hand, and drift against git is invisible rather than reported.
2. **The admission floor shipped in 5.1 currently guards an empty namespace.**
   There are zero `Agent` objects in `automation`. The guard only becomes
   load-bearing once personas exist, and personas arrive through the Application.
3. **A teardown is not reproducible from git** — demonstrated today. The
   Application was deleted and nothing in any repository can recreate it.

#### Why your data is not at risk

The sympozium Application manages **`Ensemble` custom resources** — and, after the
rebuild, our `MCPServer` + Deployment + Service and possibly a `SympoziumPolicy`
and `SkillPack`. **None of those owns a PersistentVolumeClaim.**

Agent memory PVCs are created by the *Sympozium controller* from
`Ensemble.spec.agentConfigs[].memory`, with an `ownerReference` on the generated
`Agent`. ArgoCD never renders them, never tracks them, and therefore can never
prune them. They are outside its object graph by construction.

State on 2026-08-25:

```
$ kubectl get pvc -n automation
nats-data   longhorn   1Gi        # core's chart, not ours
```

That is the **only** PVC in `automation`. There are no `<persona>-memory` PVCs —
they went with the fleet teardown, before this plan was written (Section 7.1). So
at the moment the Application is re-created there is literally nothing under its
management to delete.

The general hazard worth knowing anyway: **every storageclass on this cluster is
`reclaimPolicy: Delete`** — `local-path`, `longhorn`, `longhorn-no-replica`,
`longhorn-static`, `nfs`. So a pruned PVC destroys its volume, with no
Released-PV fallback. That is the reason never to put `prune: true` on an
Application that could ever manage a PVC. It does not apply here, but it is why
the procedure below is worth following rather than skipping.

#### The safe procedure

1. **Adopt, do not recreate.** Apply an Application whose `name`, `namespace`,
   `spec.source.repoURL` and `spec.source.path` match what was there. ArgoCD
   adopts pre-existing resources by tracking-id; it does not delete and re-add.
2. **Omit `syncPolicy` entirely at first.** Sync manually, read the diff, and only
   proceed once it is empty.
3. **Then add `syncPolicy.automated: {}` with no `prune` key.** An empty
   `automated` block is `prune: false, selfHeal: false` — sync can create and
   update but never delete. Add `prune` later, deliberately, and never while the
   app could manage a PVC.
4. **Carry `ignoreDifferences`** on `memory.maxSizeKB` and `schedule.firstTick`,
   as core's ApplicationSet does, so CRD defaulting does not read as permanent
   drift (Section 5.6).
5. **Verify before syncing** with `helm template ... | kubectl apply
   --dry-run=server -f -` (Section 10).

#### The superset half is separable — defer it

`datahub-local-workflows-superset` has the same *reversibility* gap (hand-applied,
`path: workflows/superset/release/`,
`repoURL: https://github.com/datahub-local/datahub-local-ai.git`,
`targetRevision: HEAD`) but **no live hazard**, so do not touch it while doing the
sympozium one:

- it targets namespace **`data`**, not `automation`
- its `syncPolicy` is `automated: {}` with **no `prune`** — automated sync already
  cannot delete anything
- Superset dashboards live in Superset's own database; the ConfigMaps are only the
  import source, and object `uuid`s are the stable identity across re-imports
  (`/CLAUDE.md`). Nothing about registering a *different* app touches them.

Track it in git eventually — ideally one `ApplicationSet` covering both `agents/`
and `workflows/` sub-projects — but as its own change, after the rebuild, and
never by deleting the working Application first.

### 5.6 Re-derive CRD defaults after any control-plane bump

Every CRD-defaulted field must be stated explicitly or ArgoCD reports permanent
drift, and `kubectl diff` cannot see this class of drift because it defaults both
sides. Diff a `--dry-run=server` apply against the rendered manifest instead.

```bash
kubectl get crd ensembles.sympozium.ai -o json \
  | jq '.. | objects | select(has("default"))'
```

Known defaulted: `mcpServers[].timeout`, `schedule.firstTick`,
`memory.maxSizeKB`, `sharedMemory.storageSize`, `agentSandbox.warmPool.size` (2),
`lifecycle.gateDefault` ("block"), `webEndpoint.rateLimit.requestsPerMinute` (60)
and `.burstSize` (10), `subagents.{maxDepth: 2, maxConcurrent: 5,
maxChildrenPerAgent: 3}`, `stimulus.trigger` ("onReady").

---

## 6. Changes needed in `datahub-local-bootstrap`

> **Status 2026-08-25: DONE.** Landed on bootstrap `main` as `780ec88`, tree clean,
> pushed. `gvisor` RuntimeClass live with `handler: runsc` and
> `scheduling.nodeSelector: {datahub.local/gvisor: "true"}`. Five of seven nodes
> labelled — `amd-1`, `amd-2`, `orpi-1`, `orpi-2`, `orpi-3`. `orpi-0` is excluded as
> control-plane; `nas` is excluded deliberately in `inventory.yml`
> (`k3s_gvisor_enabled: false`, TrueNAS appliance OS) and is `NoSchedule`-tainted
> anyway. **Verified end to end**: a pod with `runtimeClassName: gvisor` reports
> `uname -r` = `4.19.0-gvisor` and `Starting gVisor...` in `dmesg` on both
> `datahublocal-amd-2` (x86_64) and `datahublocal-orpi-1` (aarch64). The RK3588
> vendor-kernel risk this section warned about did not materialise. **6.1 no longer
> blocks anything, and neither does 5.3** — see the correction there: sandboxed
> agents already reach Ollama, and the MCP/OTel fix needs no probe. Sandboxing is
> post-rebuild hardening. With 5.5 waived and 6.1 done, **nothing blocks Phase 2**;
> the only outstanding core action is committing the 5.3 edit.


### 6.1 Install a sandbox runtime, or Agent Sandbox stays decorative

Bootstrap already installs Agent Sandbox — `roles/bootstrap/defaults/main/values_security.yaml`:

```yaml
agent_sandbox_enabled: true
agent_sandbox_extensions_enabled: true       # SandboxTemplate, SandboxClaim, SandboxWarmPool
agent_sandbox_manifest: sandbox-with-extensions.yaml
agent_sandbox_namespace: agent-sandbox-system
```

Controller v0.5.6 is Running. But the upstream manifest installs the **API and
controller only**. On this cluster:

```
$ kubectl get runtimeclass
crun  lunatic  nvidia  nvidia-experimental  slight  spin  wasmedge  wasmer  wasmtime  wws
```

No `gvisor`, no `kata`. `Ensemble.spec.agentSandbox.runtimeClass: gvisor` would
fail to schedule, and `agentSandbox.enabled: true` without a runtimeClass gives
Sandbox-CRD lifecycle management (warm pools, claims) with **zero kernel
isolation** — Sympozium's own field description promises "gVisor/Kata
kernel-level isolation", which is not what would happen.

So bootstrap needs a new task: install `runsc` on every node and create a
`gvisor` RuntimeClass. Notes for whoever does it:

- gVisor supports **both** arm64 and amd64, so the whole fleet is a candidate:
  `datahublocal-amd-1`/`amd-2` (amd64, Debian 13 trixie, 6.12.x),
  `datahublocal-nas` (amd64, TrueNAS on bookworm, 6.12.15),
  `datahublocal-orpi-0` (arm64, RK3399, 7.1.2-edge-rockchip64),
  `datahublocal-orpi-1/2/3` (arm64, RK3588, 6.1.115-vendor-rk35xx).
- All seven nodes run `containerd://2.3.2-k3s2`, so this is a k3s containerd
  config drop-in plus the `runsc` binary, following the existing NVIDIA-driver
  task as the pattern for per-node installs.
- Kata is the wrong choice here — it wants nested virtualisation the SBCs do not
  have.
- Verify per-node before trusting it: gVisor on vendor rockchip kernels is not a
  configuration anyone guarantees. A node where `runsc` fails should be excluded
  by `nodeSelector` rather than block the rest.

### 6.2 Sequence

Sandboxing only becomes real when **both** 6.1 and 5.3 have landed. Until then
`agentSandbox.enabled: false` in `values/default.yaml.gotmpl`, with the two
prerequisites recorded in `MEMORY.md` as the enabling change.

Worth pursuing after the rebuild, precisely because the responder means untrusted
Slack text drives runs — which is the threat kernel isolation actually answers,
and the one `toolPolicy` demonstrably does not.

---

## 7. Cleanup and state that affects decisions

### 7.1 Agent memory is gone — treat that as an asset

All `<persona>-memory` Deployments, Services and PVCs were destroyed with the
fleet. Nothing carries over.

This matters more than it looks. The old memory seeds had accumulated
**corrections of the agents' own wrong history** — the seeds themselves said so:

- *"Correction, 2026-08-24: any earlier memory of yours reporting WAL archiving
  as failing ... is wrong. Those runs read a lifetime counter as a live state."*
- *"Correction, 2026-08-23: any earlier memory of yours reporting a volume at
  96-99% and 'write operations failing' is wrong. Those runs divided available by
  capacity and read the free fraction as the used one."*
- *"Distrust every Fleet figure you recorded before 2026-08-24. Prometheus was
  being queried against Loki's datasource uid, so all of it 404'd, and the disk
  percentages stored for those runs are `k8s_nodes_top` **memory** readings
  relabelled as disk."*

**Do not port those corrections into the new seeds.** They exist only to
neutralise stored garbage that no longer exists, and a seed that argues with
absent history is pure prompt cost. Under the new architecture the facts they
correct are computed in code and tested — the fill inversion and the counter
window become pytest cases, not memory.

What *does* deserve to carry over is the ground truth those runs established, and
it belongs in `agents/mcp/projects/homelab_facts/config/` rather than in memory:

- `hardware_classes.yaml` — orpi-0 (RK3399, rockchip64) | orpi-1/2/3 (RK3588,
  rk35xx vendor) | amd-1/amd-2 (Debian 13 amd64) | nas (TrueNAS, Intel N305).
  Versions are comparable only *within* a class; a class of one is never the odd
  one out. The old fleet reported orpi-0's kernel as drift every run for days
  because that rule lived in prose.
- `chronic_alerts.yaml` — `KubeSchedulerDown` and `KubeControllerManagerDown` are
  k3s artifacts (both components embedded, no separate metrics endpoint);
  `Watchdog` fires by design; `CPUThrottlingHigh` is chronic across ~10
  workloads; `NodeClockNotSynchronising` is **real** on orpi-0..3
  (systemd-timesyncd inactive) and must not be suppressed.
- Telemetry facts: Valkey is scraped by a redis exporter so its metrics are
  `redis_*` and never `valkey_*`; node-exporter's SMART series is
  `smartmon_temperature_celcius` (upstream typo); SMART health is meaningful only
  on amd-1, amd-2, orpi-0 and nas — every device on orpi-1/2/3 reports
  `smartmon_device_smart_available 0`; the UPS is on `nas` alone, so
  `network_ups_tools_*` exists there only; `chrony.service` on nas and
  `systemd-timesyncd.service` everywhere else; all five `nfs` PVCs report the
  same shared 1.9 TB capacity, so a per-volume percentage there is meaningless.
- `cnpg_backends_total` and `cnpg_backends_waiting_total` are **gauges** despite
  the `_total` suffix; `cnpg_pg_stat_archiver_failed_count` is a **cumulative
  counter** and must be read as `increase(...[1h])`. A suffix-based rule gets
  both wrong — keep an explicit set, sourced from Prometheus's metadata API.

`MEMORY.md` (128 KB) should be rewritten around the new invariants. Keep the
incident log as history — it is why the constraints in Section 3 are trusted —
but stop growing prompt-shaped lessons into it, because most of them are about to
become code.

### 7.2 Orphaned AgentRuns pinning RBAC

12 `AgentRun`s survive the teardown — the hand-applied ones, which had no
ensemble owner:

```
db-steward-manual-0650            db-steward-probe-0820
homelab-ops-sre-sentinel-ch-g44pj homelab-ops-sre-sentinel-ch-mq7lc
homelab-ops-sre-sentinel-diag2    homelab-ops-sre-sentinel-web-{28782,b85dp,cj7qq,dfv2j,kcr5p,npd8r,nxr4d}
```

`automation` also holds 14 Roles and 14 RoleBindings — 13 run-owned pairs plus
the one core's run-pruner ships. Nothing retires an `AgentRun` — no TTL on the
CRD, no history limit on `SympoziumSchedule`, no chart knob — and the controller
gives each run's skill Role and RoleBinding an `ownerReference` on the run, so
retained runs pin their RBAC.

**The pruner will not collect these, and that is correct.** All 12 carry a
`status.completedAt`, but the oldest is `2026-08-22T21:28:53Z` and the newest
`2026-08-24T16:23:13Z` — 1 to 3 days. At `RETAIN_DAYS=7` the earliest becomes
eligible 2026-08-29. The CronJob has also never run: `status.lastScheduleTime` is
empty, first tick 03:00 on 2026-08-26. So seeing all 12 survive that tick is
expected behaviour, **not** evidence of a broken pruner — do not read it as one.
To clear them sooner, delete by hand or lower `RETAIN_DAYS`.

This makes the next point free rather than something to arrange: keep two or three
of them until Phase 0 is done — they are the only surviving evidence of the
inbound/web `toolPolicy: null` behaviour, and Loki still holds their container logs
keyed by `status.podName` over the `startedAt`/`completedAt` window. Retention to
2026-08-29 covers Phase 0 without any action.

### 7.3 Uncommitted work in this repo

```
$ git status --short          # datahub-local-ai
M  CLAUDE.md
M  agents/sympozium/MEMORY.md
M  agents/sympozium/projects/homelab-ops/{README.md,ensemble.yaml}
M  agents/sympozium/projects/homelab-ops/agents/{gitops-auditor,service-janitor}.yaml
M  agents/sympozium/projects/homelab-ops/prompts/*_system.md   (5 files)
A  agents/sympozium/prompts/shared/promql.md
M  agents/sympozium/scripts/validate.py
M  agents/sympozium/templates/ensembles.yaml
AM agents/sympozium/REBUILD.md          # this document
M  agents/sympozium/.helmignore         # excludes it from the chart
```

Note the last two: **this plan is itself part of the undecided set.** Whatever is
decided below governs the document describing the decision.

**The set is not homogeneous — do not discard it wholesale.** Two of these files
carry durable findings that directly constrain Phase 2, and losing them costs real
work:

| Keep | Why |
|---|---|
| `REBUILD.md`, `.helmignore` | this plan |
| `MEMORY.md` (+358) | incident write-ups, **not** prompt iteration. Includes the 16 KB tool-result limit and the `node_*`-has-no-node-name join — both now requirements in Section 4.2, and neither derivable from the code |
| `CLAUDE.md` (+18) | the `mcp-k8s` wildcard ClusterRole vs SkillPack RBAC distinction. `/CLAUDE.md` is the file a future session reads automatically |

| Discard | Why |
|---|---|
| 5 × `prompts/*_system.md` | prompt-and-regex iteration this rebuild deletes |
| `prompts/shared/promql.md` | replaced by `promql()` |
| `scripts/validate.py` (+104) | more prose regex — the thing being removed |
| `templates/ensembles.yaml` (+14) | the `{{ PROMQL }}` substitution that reads it |
| `projects/homelab-ops/**` | the personas being replaced |

**Discard those nine together or not at all.** They are coupled: the staged
prompts contain `{{ PROMQL }}`, and the substitution that resolves it is in the
staged `ensembles.yaml`. Reverting one without the other fails the render. `HEAD`
(`3591a5e`) is self-consistent, so reverting all nine to it is safe by
construction — confirm with a `helm template` and `validate.py` run afterwards.

### 7.4 The eight chart example ensembles

`code-analysis-team`, `developer-team`, `devops-pipeline-example`,
`local-inference-example`, `observability-mcp-example`, `platform-team`,
`research-delegation-example`, `subagent-analysis-example` — all `Inactive`,
catalog-only, and not ours. Leave them. They are useful as live CRD examples;
just never confuse them with ours, and keep our names prefixed.

### 7.5 Do not mount `sre-observability` or `k8s-ops`

Both remain in the cluster's SkillPack catalog and both are traps, verified
before teardown:

- `sre-observability` says *"Use `execute_command` for all shell commands"*;
  `k8s-ops` claims *"full cluster admin access ... kubectl works out of the box"*.
  744 shell commands ran across the fleet in a week on personas that *denied*
  `execute_command` — prose competing with a persona's prompt, and prose wins.
- Both declare `sidecar.rbac` that the controller binds to the **shared**
  `sympozium-agent` ServiceAccount, so mounting one granted every agent in
  `automation` create/delete on pods, `pods/exec`, secrets, deployments and
  rolebindings.

Read a pack's `.spec.skills[].content` **and** `.spec.sidecar.rbac` before
mounting anything. `scripts/validate.py` should keep rejecting both by name.
Mounting no skill sidecar at all is also what keeps `execute_command` inert
(3.4).

### 7.6 Retire the web-endpoint machinery

No `web-endpoint` Deployments, Services or HTTPRoutes survive the teardown.
`sympozium_web_endpoint` in values, the render-time skill append, and the
validator's `VALUES_ONLY_SKILLS` guard can all go:

- a serving `AgentRun` makes the schedule controller **skip every tick** for that
  agent, silently, with the `SympoziumSchedule` still `Active`
- a web run gets **neither `toolPolicy` nor `lifecycle`** (3.3), so it is both
  unbounded and undeliverable
- it **truncates the task to its first line**
- `webEndpoint` is now a first-class persona field anyway (3.5), so the SkillPack
  dance is obsolete

The responder persona covers the "ask it something" use case properly. If an HTTP
trigger is ever wanted again, use `agentConfigs[].webEndpoint` and re-verify all
three behaviours above.

---

## 8. Phases

### Phase 0 — four verifications (0.3 answered)

Each changes a design choice; none is expensive. Two write to the cluster.

1. **Does `SympoziumPolicy` gate dispatch or only registration?** Create a
   throwaway policy with `featureGates: {code-execution: false, file-access:
   false}` and `toolGating: {defaultAction: deny, rules: [...]}`, bind a probe
   persona, and hand-apply an `AgentRun` whose task explicitly asks for
   `execute_command`. Stream `kubectl logs <pod> -c agent -f` — the pod is
   deleted on completion whatever `cleanup` says.
   - *Bites* → build `templates/policy.yaml`; it becomes the boundary the
     responder needs.
   - *Registration only* → skip it, and rely on `mcpServers[].toolsAllow` plus
     mounting no skill sidecar, which are the boundaries that do hold.
2. **Does `SkillPack.skills[].content` reach the model's context?** Create a
   throwaway pack whose content holds a unique canary string, mount it on a probe
   persona, and ask the model to repeat the canary.
   - *Yes* → shared prose (report contract, delivery contract) moves to one
     repo-owned SkillPack, and the `{{ TOKEN }}` substitution machinery dies.
   - *No / needs `read_file`* → keep prose in `systemPrompt`, which demonstrably
     works, and drop `templates/skillpacks.yaml` from the plan.
3. ~~**Read the effective Ollama context.**~~ **ANSWERED 2026-08-25: 65,536.**
   Read from `GET /api/ps` with `qwen3.5:4b` resident (warmed with a one-token
   `/api/generate` first — nothing is loaded when the fleet is down). Core's
   `f58529a` did **not** change it; the figure in `/CLAUDE.md` still holds.
   `size_vram` 4.45 GB of the 6 GiB card. Re-check after an Ollama or model bump.
4. **How does an inbound-triggered run actually reply?** Gates Section 9's
   responder-guard question and possibly the responder's tool list. Bind a probe
   persona to Slack, send it one @-mention, and observe two things:
   - Does a reply reach the asking thread **without** `send_channel_message` in the
     allowlist? The evidence is ambiguous: both surviving `...-ch-*` runs carried
     the postRun hook and their answers appeared in `#monitoring-ai-alerts` (the
     hook's hardcoded destination), while the run log shows
     `tool policy: tool "send_channel_message" not in allow list`. So there is no
     evidence a thread reply ever happened — only that the hook posted. If the
     reply path *requires* the tool, the responder must allowlist it, which
     reintroduces the `chatId` footgun and makes the single-binding rule
     load-bearing rather than merely tidy.
   - With a `gate: true` hook attached, does the delivered text come from
     **before or after** the verdict? That decides whether a non-delivering gate
     can guard the responder at all.

Record all four answers in `MEMORY.md` with the date and the command used.

### Phase 1 — land core's admission floor

Section 5.1. Independent of everything else, closes a live gap, already written.
Then Section 5.2 (delete the leftover netpol). Section 5.5 is **waived** — see the
status block in Section 5; do not start it here.

### Phase 2 — `agents/mcp/`

Build the sub-project. Order that keeps it provable:

1. `pyproject.toml`, `src/mcp_runner/` skeleton, `/healthz`, `python -m mcp_runner`
2. `prometheus.py` with the uid / `endTime` / `queryType` knowledge in one place,
   and `promql()` as the first tool
3. one facts tool end to end — `volume_fill()` is the best first, since its
   inversion-plus-join is the failure the old fleet repeated for days — with
   pytest over the inversion, the `group_left` join, and the `nfs` exclusion
4. the rest of the tools, each with its tests
5. `config/*.yaml` populated from Section 7.1
6. Dockerfile, multi-arch buildx, CI push to GHCR, pinned tag

Run it locally against the cluster and diff its output against hand-run PromQL
before wiring any agent to it.

### Phase 3 — chart platform objects

Deployment + Service + `MCPServer` (`url:` form, **`app.kubernetes.io/name:
mcpserver` labels** — 3.6), and `policy.yaml` if Phase 0.1 said yes. Verify:

```bash
cd agents/sympozium
helm template datahub-local-ai-sympozium . -n automation -f values/default.yaml.gotmpl \
  | kubectl apply --dry-run=server -f -
```

Confirm a probe `AgentRun` can actually reach the new server —
`kubectl logs <run-pod> -c mcp-discover` prints per-server tool counts, and a
whole server failing is silent otherwise. Core's `mcp-k8s` 404'd for three days
with `MCPServer.status.ready: true` throughout.

### Phase 4 — personas

Reporters first, then the responder. For each: hand-apply an `AgentRun` and watch
it before any schedule ticks. Apply the chart **once** — the Ensemble controller
queues a run per rewritten schedule against one Ollama slot (3.7).

### Phase 5 — delete

- the nine prose validators in `scripts/validate.py` (~600 of 1,473 lines)
- `{{ TOKEN }}` substitution, the `contains "{{"` render guards, `_delivery.tpl`'s
  verbosity branch
- `prompts/shared/promql.md`, `prompts/delivery/{normal,quiet,verbose}.md`,
  `prompts/notify/*` — verbosity and notify were already meaningless under hook mode
- `sympozium_web_endpoint` and `VALUES_ONLY_SKILLS`
- the bulk of every system prompt
- most of `files/deliver-slack.sh`'s `sed` pipeline, once the gate hook shapes output
- this file

Then rewrite `MEMORY.md` around the new invariants and update `/CLAUDE.md`'s
Sympozium section — it currently documents the old architecture in detail and
will be actively misleading.

---

## 9. Open questions

- **Does `endpoint-warden` survive?** Its report is a node table — pure tabular
  data. Once `node_fleet()` exists, an LLM adds nothing but risk between the data
  and the channel. Candidates: a plain CronJob that posts the table, a Grafana
  panel, or keep the persona for the *interpretation* only (trend, "which node is
  the odd one out") with the table rendered by the gate hook.
- **Does `homelab-reviewer` come back as-is?** `renovate-reviewer` is the only
  persona with a write tool (`github_add_issue_comment`), which is why it has its
  own ensemble and no channel binding. Nothing in this plan changes that, but it
  gains least from the facts server — its work is reading diffs, not metrics.
  Consider rebuilding it last, unchanged.
- **Where does the Application manifest live?** Section 5.5. Affects this repo,
  `workflows/superset`, and whether a teardown is reversible from git.
- **The responder has no output guard, and it is the persona that most needs one.**
  A `gate` is a flag on a `postRun` hook (Section 3.2), and the responder has no
  `postRun` hook *by design* — that is what stops its answers going to the hook's
  hardcoded channel instead of the asking thread (Section 4.4). So the reporters,
  fed by a deterministic facts server, get the deterministic output guard; the
  responder, fed by free-form Slack text, gets none.

  It may be fixable rather than a genuine trade-off: **a gate hook does not have
  to deliver.** A `postRun` hook with `gate: true` that only validates or rewrites
  and posts nothing would leave the channel sidecar to deliver the *gated* text.
  Whether that works depends entirely on Phase 0.4 — if the sidecar reads
  `status.result` after the verdict, this is the answer; if it delivers off the
  event bus before the gate runs, or if replies need `send_channel_message` at
  all, the responder needs a different guard.

  Severity, honestly: with `channelAccessControl.allowedSenders` pinned to one
  person the input is not adversarial, it is your own text, and
  `threadStickiness` marks a thread `interrupted` the moment a non-owner speaks,
  after which `allowedTriggers` must be satisfied again. So this is a missing
  guard on malformed or confusing input, not an open door. Do not let it block the
  rebuild; do not ship the responder without deciding it either.
- **Does the responder need its own ensemble?** It is read-only, so it can share
  `homelab-ops`. But it is the only inbound surface, and Section 3.4 says its real
  bounds are per-persona. A separate ensemble would make that boundary visible in
  the directory listing, at the cost of a second `Ensemble` object.

---

## 10. Verification commands

```bash
# Repo
uv sync --extra sympozium
uv run python agents/sympozium/scripts/validate.py
cd agents/sympozium && helm template datahub-local-ai-sympozium . -n automation \
  -f values/default.yaml.gotmpl

# Against a live cluster — persists nothing, catches what the webhook rejects
helm template datahub-local-ai-sympozium . -n automation -f values/default.yaml.gotmpl \
  | kubectl apply --dry-run=server -f -

# CRD defaults, to re-derive after a control-plane bump
kubectl get crd ensembles.sympozium.ai -o json | jq '.. | objects | select(has("default"))'

# What a persona actually got
kubectl -n automation get agent <name> -o json | jq '{mcpServers: .spec.mcpServers, skills: .spec.skills}'
kubectl -n automation get agentrun <run> -o json | jq '{toolPolicy: .spec.toolPolicy, lifecycle: .spec.lifecycle}'

# Live run — the pod is deleted on completion, so stream it
kubectl -n automation logs <run-pod> -c agent -f
kubectl -n automation logs <run-pod> -c mcp-discover   # per-server tool counts

# A finished run, via Loki (the only way to diagnose a scheduled run after the fact)
kubectl -n monitoring port-forward svc/datahub-local-core-loki-gateway 3100:80
curl -sG http://127.0.0.1:3100/loki/api/v1/query_range \
  --data-urlencode 'query={namespace="automation",pod="<pod>",container="agent"}' \
  --data-urlencode 'start=<startedAt>' --data-urlencode 'end=<completedAt>' \
  --data-urlencode 'limit=2000' --data-urlencode 'direction=forward' \
  | jq -r '.data.result[].values[][1]'

# Effective Ollama context (model must be resident)
kubectl -n data port-forward svc/datahub-local-core-data-ollama 11434:11434
curl -s http://127.0.0.1:11434/api/ps | jq '.models[] | {name, context_length}'
```

Never read an empty `status.result` as a quiet run. `status.result` is also
dropped whenever the reply contains invalid UTF-8 — the runner ships it to the
controller over gRPC and protobuf refuses to marshal a bad string, while the run
still reports `Succeeded` with no `error`. Stream the log instead.
