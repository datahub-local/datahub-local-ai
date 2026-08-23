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
  values/default.yaml.gotmpl   per-cluster knobs: enabled, baseURL, policyRef,
                               channelConfigs, and the sympozium_delivery and
                               sympozium_web_endpoint trees
  templates/ensembles.yaml     assembles one Ensemble per projects/<name>/
  prompts/
    delivery/header.md         the line that names the agent — every bound
                               persona gets it, whatever its levels
    delivery/<level>.md        how much detail to post   (quiet|normal|verbose)
    notify/<level>.md          when to post at all       (always|onChange|never)
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
   it. The two `ignoreDifferences` entries are a backstop only: every
   CRD-defaulted field is stated in `projects/` (see *CRD defaults are stated*
   below), so there is nothing for them to hide today. Keep them anyway — a
   control-plane bump that adds a new `default:` would otherwise show up as
   permanent drift on the next sync.

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
before committing, since rendering is the only build step there is. Diff its
output against the rendered manifest, too: any field the server adds is a
CRD default this repository has not stated, which is exactly the drift ArgoCD
will report. `kubectl diff` will *not* show it — it defaults both sides.

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
allowlist. That comment is also its only notification path — a `DO NOT MERGE`
verdict on the PR *is* the alert. This is the one ensemble deliberately *not*
bound to Slack: a channel binding is bidirectional, and an inbound trigger on
the only agent holding a write tool is exactly the blast radius the split
ensemble exists to keep visible.

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
  schedules and tool policy live in `projects/`. Only `enabled`, `baseURL`,
  `policyRef`, `channelConfigs` and the `sympozium_delivery` and
  `sympozium_web_endpoint` trees — the things that could legitimately differ
  between clusters — live in
  `values/default.yaml.gotmpl`, merged over `spec` at render time. The
  validator rejects those keys in `ensemble.yaml`.
- **A channel binding is split across both, and so is delivery.** The persona
  carries the type (`channels: [slack]`), `send_channel_message` in the
  allowlist, and a `{{ DELIVERY }}` token in its system prompt. Values carry the
  credential secret (`channelConfigs`) and the knobs (`sympozium_delivery`:
  `channel`, `verbosity`, `notify`, with per-persona overrides). Any one half
  alone deploys cleanly and posts nothing, or posts to nowhere, so the validator
  cross-checks all of it — including a typo under `personas:`, `notify:
  onChange` on a prompt with no *What counts as a change* section, and
  `slackOptions` on a persona that is not on Slack. The block the templates
  substitute is three files: `prompts/delivery/header.md`, which every bound
  persona gets and which is what names the agent in the message, then the
  chosen `delivery/<verbosity>.md` and `notify/<level>.md`.
- **The report says which agent wrote it; it never says when.** No tool in this
  fleet returns the current time, so the prompts forbid writing any date or
  duration not read out of a tool result, and Slack's own message timestamp is
  the run time. `{{ SCHEDULE }}` in the header carries the cadence
  (`heartbeat, every 30m`) read off the persona's own `schedule`, so it cannot
  drift from the cron. Putting an authoritative run time *inside* the message
  needs something outside the model — a `lifecycle.postRun` gate hook that
  rewrites the output is the CRD's own mechanism for it.
- **Prompt tokens are substituted by name, never with `tpl`.** The templates
  replace exactly `{{ DELIVERY }}`, `{{ CHANNEL }}`, `{{ AGENT }}`,
  `{{ ENSEMBLE }}` and `{{ SCHEDULE }}`, then `fail` on any token left standing — the same contract as `check_template_vars_present` in
  `agents/n8n`. `tpl` would execute arbitrary template code inside a prompt and
  turn a future literal `{{` in prompt text into a render error. The cost is
  real either way: a prompt file is no longer exactly what the model sees. Run
  `helm template` to read the assembled version.
- **`toolPolicy` is prefixed, `toolsDeny` is not.** `toolPolicy.allow` lists
  agent-facing names (`k8s_pods_list`), because that is what the model sees.
  `mcpServers[].toolsDeny` lists the server's own names (`pods_delete`), because
  that filter runs at the server. Getting this backwards produces a deny that
  matches nothing — see below. The build script checks both directions.
- **CRD defaults are stated.** Every field the Ensemble CRD carries a
  `default:` for — `mcpServers[].timeout`, `schedule.firstTick`,
  `memory.maxSizeKB`, `sharedMemory.storageSize` — is written out in
  `projects/`, even where the value chosen *is* the default. The API server
  applies those defaults at admission, so an omitted value exists in the live
  object and not in git, and ArgoCD reports the Ensemble OutOfSync on every
  sync forever. Stating them also puts the value where it is reviewable instead
  of in a CRD in another repository. The validator enforces the list; re-derive
  it after a control-plane bump with
  `kubectl get crd ensembles.sympozium.ai -o json | jq -r '.. | objects | select(has("default"))'`.
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

The same class of bug as the Prometheus contract below, found the same way, and
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

## Testing an agent over HTTP

`sympozium_web_endpoint` in `values/default.yaml.gotmpl` puts an HTTP endpoint
in front of a persona, so a run can be started without waiting for its cron.
Enabling it appends the `web-endpoint` SkillPack, and the controller deploys a
web-proxy beside the agent that turns one request into one `AgentRun` — against
the same prompt, skills, MCP servers and tool policy the schedule uses. It is on
for all five `homelab-ops` personas and off for `renovate-reviewer`, which holds
a write tool.

No `hostname` is set, so no `HTTPRoute` is created and the Service stays
ClusterIP: nothing outside the cluster can reach it.

    kubectl get svc -n automation | grep web
    kubectl get secret -n automation -o name | grep web-endpoint

    KEY=$(kubectl get secret homelab-ops-sre-sentinel-web-endpoint-key \
      -n automation -o jsonpath='{.data.api-key}' | base64 -d)
    kubectl port-forward -n automation svc/homelab-ops-sre-sentinel-web 8080:8080 &

    curl -s localhost:8080/healthz
    curl -s localhost:8080/v1/chat/completions \
      -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
      -d '{"model":"default","messages":[{"role":"user","content":"Do an on-call sweep now."}]}'

Confirm the object names against the cluster rather than trusting the ones above
— they are the controller's, not this chart's.

Two things to know before leaning on it. A request costs a slot on the one GPU,
the same as a scheduled run, so a test queued behind a heartbeat tick waits for
it. And the endpoint is a trigger: every persona behind one is read-only today,
which is the only reason a ClusterIP with a bearer key is a reasonable place to
leave it.

Where a test needs to differ from the real thing — a different prompt, a
narrower tool policy, no delivery — an `AgentRun` applied by hand is the better
tool, since it takes `systemPrompt`, `task` and `toolPolicy` inline:

    kubectl apply -f - <<'EOF'
    apiVersion: sympozium.ai/v1alpha1
    kind: AgentRun
    metadata:
      name: probe-1
      namespace: automation
    spec:
      agentRef: homelab-ops-sre-sentinel
      agentId: probe
      sessionKey: ""
      mode: task
      useContext: false
      model:
        provider: ollama
        model: qwen3.5:4b
        baseURL: http://datahub-local-core-data-ollama.data.svc:11434/v1
        authSecretRef: ""
      systemPrompt: |
        <the prompt under test>
      task: |
        <the task under test>
      toolPolicy:
        allow: [send_channel_message]
        deny: [write_file, execute_command]
    EOF
    kubectl get agentrun probe-1 -n automation -o jsonpath='{.status.result}'

That is how the `chatId` contract above was pinned down. Note that the pod is
deleted as soon as the run ends whatever `cleanup` says, so `status.result` and
the sidecar logs are the only record — plan the probe around reading those.

## The `query_prometheus` argument contract

`grafana_query_prometheus` fails outright unless `endTime` is passed, even for an
instant query, and the tool's own description says the opposite (`startTime` is
"ignored if queryType is 'instant'", while `endTime` sits unremarked in the
schema's `required` list). Omit `queryType` instead and it defaults to `range`,
which then fails on the missing `stepSeconds`. The call that works is:

    datasourceUid: "prometheus"
    expr:          <PromQL>
    queryType:     "instant"
    endTime:       "now"

For the first day these agents ran, no prompt said this, so every
`grafana_query_prometheus` call from all four Prometheus-reading personas
errored. What that looked like from outside is the part worth remembering: not an
outage, but `Status HEALTHY / Nothing new.` every thirty minutes, with the
known-chronic memory seeds recited under **Still firing** as though they had been
observed — including two alerts that were not firing at all. `notify: onChange`
then suppressed the Slack post, so a dead sensor and a quiet cluster produced
byte-identical output: nothing. `NodeClockNotSynchronising` fired on four nodes
for seven hours without a word.

The fix is in three parts, all of them in `projects/`: the prompts state the
argument contract, the hard rules make an errored query escalate (DEGRADED, and
send regardless of the change test) instead of degrading to silence, and
`grafana_list_datasources` is allowlisted so the datasource uid is read rather
than guessed. Every persona's prompt now also says its seeds are a list of what
to ignore *when observed*, never evidence that it was.

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

A fifth, unrelated change to `releases/automation/` is what currently stops the
fleet running at all — see below.

### The agent NetworkPolicy blocks shared memory and every MCP server

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
- **`NodeClockNotSynchronising` is firing on four nodes** as of writing — the
  four arm64 orpi boxes, with `node_timex_sync_status 0` and
  `node_timex_maxerror_seconds` pinned at the kernel's unsynchronised ceiling of
  16s, so their time source is not merely drifting but absent. Nothing here fixes
  it. `sre-sentinel` was supposed to keep reporting it and did not, for the
  argument-contract reason above; it is deliberately left out of the seeds so the
  first run after that fix reports it as new, and suggests its own remedy.
- **Nothing here deletes.** `service-janitor` reports cleanup and prints the
  commands; a human runs them. Auto-cleanup would be a separate, deliberately
  authorised agent.
- **Expiry is split with n8n on purpose.**
  [`credentials_expiry_review`](../n8n/workflows/credentials_expiry_review.workflow.json)
  owns n8n credential expiry, and its dataset documents at length why that date
  lives in the credential's name. `service-janitor` stays strictly cluster-side
  — certificates, tokens, secrets — so the two never contradict each other.
