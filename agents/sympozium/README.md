# Sympozium agents

Agent definitions for the [Sympozium](https://github.com/sympozium-ai/sympozium)
control plane that [datahub-local-core](https://github.com/datahub-local/datahub-local-core)
deploys into the `automation` namespace, plus a Helm release that ships them.

Core owns the *platform* — the controller, API server, NATS, the MCP server
catalog, the SkillPacks and the policies. This sub-project owns the *agents*:
what they are told to do, when they run, and what they are allowed to touch.

> **This file is the structure and the runbooks**: what is here, how to build,
> validate and deploy it, the conventions, and how to test an agent.
>
> **Why any of it is set the way it is lives in [MEMORY.md](MEMORY.md)** —
> per-knob and per-persona rationale, and every incident this fleet has had.
> New notes go there, not here.

The unit of deployment is an **Ensemble** — a team of personas. Installing one
stamps out an `Agent` and a `SympoziumSchedule` per persona and seeds their
memory. Ensembles default to disabled in the CRD ("catalog-only"), so a manifest
that does not say `enabled: true` deploys but never runs.

## Prompt and context budget

The effective model context has a hard **90K-token maximum**. The prompt,
registered tool schemas, every tool result, memory and final answer all share it.
Treat it as a ceiling, not usable working space: leave room for results and the
final answer. `toolsAllow` is therefore a context control as well as a
permission control; never attach a server or tool a persona does not need.

Write every persona prompt in a compact, literal "caveman" style:

- one job; literal tools in the required order; stop when the answer exists;
- a small, explicit lookup cap and a valid no-result answer;
- exact output sections, once and in order, when the persona is a reporter;
- short hard rules for evidence (`unavailable`, `ERROR:`) and final delivery;
- no repeated background, prose tutorials, copied schemas, or speculative
  alternatives — deterministic gathering belongs in MCP code.

Prefer a short imperative over explanation: `Call facts_node_fleet. Trust the
notes. Three lookups max. No result: cause not determined.` Prompt files are the
only source, so make this edit there rather than generating or inlining text.
Measure real runs after a change: the runner's cumulative `input=` token log is
the evidence that the budget still has headroom.

## Layout

The chart root **is** this directory. Helm's `.Files` cannot read above the chart
directory, and the templates read `projects/` directly, so there is no `release/`
subdirectory here — unlike `workflows/superset/`, which needs a build step
because its bundles are binary zips. Nothing is generated into the repository.

```
agents/sympozium/
  Chart.yaml
  helmfile.yaml.gotmpl
  values/default.yaml.gotmpl   per-cluster knobs: enabled, baseURL, authRefs,
                               policyRef, channelConfigs, and the
                               sympozium_delivery and sympozium_web_endpoint trees
  templates/
    ensembles.yaml             assembles one Ensemble per projects/<name>/
    _helpers.tpl               resolves the per-persona knobs (cadence, the
                               sympozium_delivery values, deliveryMode)
    _delivery.tpl              assembles the delivery prompt block and the
                               postRun hook container
  files/deliver-slack.py       the hook's script: converts the report to Slack
                               mrkdwn, prepends the header, posts it once. A real
                               file rather than an inline string so it can be
                               read, linted and run on its own
  prompts/
    delivery/hook.md           the whole delivery block for deliveryMode: hook -
                               the model's reply *is* the report, and the header
                               is added by the script, not written by the model
    delivery/header.md         the line that names the agent, for tool mode
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
```

## Workflow

1. Edit anything under `projects/<ensemble>/`.
2. Preview the rendered manifests:

   ```bash
   cd agents/sympozium && helmfile template
   ```

   **Render with `helmfile`, not bare `helm template`.** ArgoCD's CMP runs
   `argo-cd-helmfile.sh`, and helmfile renders `values/default.yaml.gotmpl` as a
   Go template *before* Helm parses it as YAML — comments included. So a literal
   `{{ … }}` anywhere in that file, even inside a `#` comment, is an
   undefined-function error that `helm template -f` never sees, because it reads
   the same file as plain YAML. A comment naming a prompt token in braces broke
   the sync that way on 2026-08-23, after CI had passed.
   CI now renders through helmfile for exactly this reason. Prompt tokens are
   written without braces in that file; everywhere else — prompts, templates,
   this README — braces are fine.

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

| Persona           | Schedule (UTC) | What it answers                               | MCP surface            |
| ----------------- | -------------- | --------------------------------------------- | ---------------------- |
| `sre-sentinel`    | heartbeat, 30m | What is firing, and why?                      | `grafana`, `k8s`       |
| `gitops-auditor`  | sweep, 1h      | Does the cluster match what git says?         | `argocd`               |
| `endpoint-warden` | daily 04:30    | Are the machines themselves degrading?        | `grafana`, `k8s`       |
| `db-steward`      | daily 05:30    | Are Postgres and Valkey healthy and roomy?    | `pg`, `grafana`, `k8s` |
| `service-janitor` | Mon 05:00      | Is the homelab recoverable? What is expiring? | `k8s`, `grafana`       |

Each persona is **one question with five to seven tools**. That is the whole
reason there are five of them rather than three fatter ones — see
[the model constrains the design](MEMORY.md#the-model-constrains-the-design). A persona
carries exactly one schedule in the CRD, so "same agent, different focus on a
different day" is not expressible; it has to be another persona.

### `homelab-reviewer` — the only write surface

| Persona             | Schedule (UTC) | What it answers                                  | MCP surface        |
| ------------------- | -------------- | ------------------------------------------------ | ------------------ |
| `renovate-reviewer` | Mon–Fri 06:00  | Is this bump safe, and what does migrating cost? | `github`, `argocd` |

Its one write tool is `github_add_issue_comment`. Merging, pushing, approving
and branch creation are denied at the server edge, not merely left out of the
allowlist. That comment is also its only notification path — a `DO NOT MERGE`
verdict on the PR *is* the alert. This is the one ensemble deliberately *not*
bound to Slack: a channel binding is bidirectional, and an inbound trigger on
the only agent holding a write tool is exactly the blast radius the split
ensemble exists to keep visible.

## Conventions

- **Prompts are never inlined.** A persona references `prompts/*.md` and never
  writes `systemPrompt` or `schedule.task` literally. Same reasoning as
  `agents/n8n/prompts/` — a 40-line instruction buried in a YAML block scalar is
  not reviewable. Nothing checks this since the validator was removed; a literal
  prompt renders fine, so it is on review to catch.
- **Names are DNS-1123.** Ensemble and persona names become Kubernetes object
  names, so they are kebab-case (`sre-sentinel`), not the `snake_case` used for
  project directories elsewhere in this repo. Prompt *files* stay `snake_case.md`
  to match `agents/n8n/`. The templates check that a persona's `name` matches its
  file name, since a mismatch there would produce the wrong object.
- **Nothing is generated into the repository.** `templates/ensembles.yaml` is
  the build step: it reads `projects/` at render time, so the sources are the
  only copy of anything. There is no committed manifest to fall out of date with
  its source, and no rebuild to forget. The cost is that a pull request shows the
  prompt as Markdown rather than the assembled CR — run `helm template` to see
  what the cluster will actually get.
- **Source describes the agent; values describe the cluster.** Prompts, skills,
  schedules and tool policy live in `projects/`. Only `enabled`, `baseURL`,
  `authRefs`, `policyRef`, `channelConfigs` and the `sympozium_delivery` and
  `sympozium_web_endpoint` trees — the things that could legitimately differ
  between clusters — live in
  `values/default.yaml.gotmpl`, merged over `spec` at render time. Setting one of
  them in `ensemble.yaml` is not an error and not a warning — values win the
  merge, so the value in the source is silently ignored.
- **A channel binding is split across both, and so is delivery.** The persona
  carries the type (`channels: [slack]`) and, in hook mode, a `{{ DELIVERY }}`
  token in its system prompt. No persona carries a posting tool: both delivery
  modes deliver the run's own final text. Values carry the
  credential secret (`channelConfigs`) and the knobs (`sympozium_delivery`:
  `channel`, `verbosity`, `notify`, with per-persona overrides). Any one half
  alone deploys cleanly and posts nothing, or posts to nowhere — a typo under
  `personas:` included — and nothing cross-checks the halves any more, so read
  all three files together when changing any one of them. The block the templates
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
  matches nothing — see
  [tool names are not guessable](MEMORY.md#tool-names-are-not-guessable). The
  build script checks both directions.
- **CRD defaults are stated.** Every field the Ensemble CRD carries a
  `default:` for — `mcpServers[].timeout`, `schedule.firstTick`,
  `memory.maxSizeKB`, `sharedMemory.storageSize` — is written out in
  `projects/`, even where the value chosen *is* the default. The API server
  applies those defaults at admission, so an omitted value exists in the live
  object and not in git, and ArgoCD reports the Ensemble OutOfSync on every
  sync forever. Stating them also puts the value where it is reviewable instead
  of in a CRD in another repository. Nothing enforces the list, so re-derive it
  after a control-plane bump with
  `kubectl get crd ensembles.sympozium.ai -o json | jq -r '.. | objects | select(has("default"))'`.
- **Schedules are UTC.** No Sympozium CRD has a timezone field, unlike the n8n
  workflows which set `Europe/Madrid` explicitly. Every cron here is written in
  UTC with the local time in a comment, and shifts by an hour twice a year.
- **Read-only by default, and `toolPolicy` is not what enforces it.** Every
  persona denies `write_file` and `execute_command` — a shell, and redundant with
  the MCP servers wired. But the deny filters schema registration, not dispatch:
  a SkillPack that names `execute_command` in its Markdown gets it back, and the
  fleet ran 744 shell commands that way. Read a pack's `.spec.skills[].content`
  and `.spec.sidecar.rbac` before mounting it, and see
  [MEMORY.md](MEMORY.md#a-skillpack-overrode-every-tool-decision-in-this-repository).

## Testing an agent over HTTP

`sympozium_web_endpoint` in `values/default.yaml.gotmpl` puts an HTTP endpoint
in front of a persona, so a run can be started without waiting for its cron.
Enabling it appends the `web-endpoint` SkillPack, and the controller deploys a
web-proxy beside the agent that turns one request into one `AgentRun` — against
the same prompt, skills, MCP servers and tool policy the schedule uses.

The switch is in two parts, and they AND:

```yaml
sympozium_web_endpoint:
  enabled: false           # master — OFF: an endpoint replaces the schedule
  ensembles:
    homelab-ops:
      enabled: true        # all five personas
      requestsPerMinute: 60
      burstSize: 10
    homelab-reviewer:
      enabled: false       # the one persona with a write tool
```

The master switch exists separately from the per-ensemble ones because this is
something you flip on for a test and off again — see
[the endpoint replaces the schedule](MEMORY.md#the-endpoint-replaces-the-schedule--it-does-not-sit-beside-it)
for why — and that must not mean editing, and then having to remember to restore, the
per-agent decisions underneath. Per-persona overrides go under
`ensembles.<name>.personas.<persona>`, exactly as `sympozium_delivery` does. A
stray key at the root, or a persona name that does not exist, is silently
ignored at render time.

No `hostname` is set, so no `HTTPRoute` is created and the Service stays
ClusterIP: nothing outside the cluster can reach it. The object names are the
controller's, not this chart's:

    kubectl get deploy,svc,secret,agentrun -n automation | grep web-endpoint

    KEY=$(kubectl get secret homelab-ops-sre-sentinel-web-proxy-key \
      -n automation -o jsonpath='{.data.api-key}' | base64 -d)
    kubectl port-forward -n automation \
      svc/homelab-ops-sre-sentinel-web-endpoint-server 8080:8080 &

    curl -s localhost:8080/healthz
    curl -s localhost:8080/v1/chat/completions \
      -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
      -d '{"model":"default","messages":[{"role":"user","content":"Do an on-call sweep now."}]}'

### Prefer a hand-applied `AgentRun` for most testing

It costs no schedule, no Deployment and no serving state, and it takes
`systemPrompt`, `task` and `toolPolicy` inline, so a probe can differ from the
real thing — a different prompt, a narrower tool policy, no delivery:
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
        allow: [facts_alerts_snapshot]
        deny: [write_file, execute_command]
    EOF
    kubectl get agentrun probe-1 -n automation -o jsonpath='{.status.result}'

`spec.agentId`, `spec.sessionKey` and `spec.model` are all required by the CRD;
omitting any of them is rejected at apply time. Add `lifecycle` only if you want
the probe to post to Slack — leave it out and the run is silent.

That is how the `chatId` contract was pinned down. The pod is deleted as soon as
the run ends whatever `cleanup` says, so stream `kubectl logs <pod> -c agent -f`
while it runs; a run that has already finished is still readable from Loki, which
is how the two 2026-08-24 incidents were diagnosed hours later. See
[MEMORY.md](MEMORY.md#a-completed-runs-log-is-in-loki-not-gone).

## Wiping a persona's memory

Needed after a prompt bug that made the agent store false observations — the
[inverted fill check](MEMORY.md#a-right-metric-read-the-wrong-way-round) left 67 records
asserting volumes at 96-99%. Two facts make this safer than it looks:

**The seeds are not in the store.** They are injected into the task at run time
from the Ensemble's `agentConfigs[].memory.seeds`, as the `## Memory Context`
preamble. Row 1 of `sre-sentinel`'s store is a failed-`AgentRun` record, not a
seed, and the stored records carry whichever seed *wording* was current when the
run happened. So a wipe loses accumulated history and nothing else; the seeds
reappear on the next run because they were never persisted.

**There is no supported delete path.** The memory server does expose one, and it
is switched off:

```console
$ kubectl port-forward -n automation deploy/<persona>-memory 8080:8080 &
$ curl -s -X DELETE http://127.0.0.1:8080/delete
{"success":false,"error":"delete is disabled: MEMORY_ADMIN_TOKEN is not configured"}
```

Neither the Agent nor the Ensemble CRD has a field for `MEMORY_ADMIN_TOKEN`
(`memory` accepts only `enabled`, `maxSizeKB`, `autoStore` and — on the Ensemble
— `seeds`), so it cannot be enabled from this repository, and patching the
Deployment's env directly is reverted by the controller, which owns it. The image
is distroless, so `kubectl exec … rm /data/memory.db` is out too — there is no
shell in it.

That leaves the volume. `MEMORY_DB_PATH=/data/memory.db` on a 1 Gi `longhorn`
PVC owned by the Agent CR:

```console
# 1. Read the counts first, so you can prove the wipe happened.
kubectl port-forward -n automation deploy/homelab-ops-sre-sentinel-memory 8080:8080 &
curl -s http://127.0.0.1:8080/stats     # {"max_seq":67, ...}

# 2. Delete the PVC. It will sit in Terminating — the pvc-protection
#    finalizer holds it while a pod has it mounted. That is expected.
kubectl delete pvc homelab-ops-sre-sentinel-memory-db -n automation --wait=false

# 3. Delete the memory pod. Releasing the mount lets the finalizer clear and
#    the PVC actually go.
kubectl delete pod -n automation \
  -l sympozium.ai/component=memory,sympozium.ai/instance=homelab-ops-sre-sentinel

# 4. The Agent controller recreates PVC and pod. Confirm an empty store.
curl -s http://127.0.0.1:8080/stats     # max_seq back to 0
```

The label is `sympozium.ai/instance`, not `sympozium.ai/agent` — verified against
the running pod on 2026-08-23, and the obvious guess is wrong. Re-check it before
relying on this (`kubectl get pod <name> -o jsonpath='{.metadata.labels}'`); it is
the one part of the procedure a control-plane bump can silently change, and a
selector that matches nothing makes step 3 a no-op that leaves the PVC stuck in
Terminating.

Do not do this while the persona's schedule is live: a run mid-wipe stores into
the volume being deleted. With the HTTP endpoint serving, schedules are already
suppressed, which is the one time that suppression is convenient.

**When not to wipe.** The store is what the new/chronic/resolved diff is built
from, so wiping costs the agent its baseline and the next few runs will report
long-standing conditions as new. Where the bad records are a bounded, describable
set, a correcting seed is cheaper and keeps the history: `sre-sentinel` now
carries one telling it to distrust its own fill figures before 2026-08-23. Prefer
that unless the store is so polluted that the baseline is worthless anyway.

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
`grafana_list_datasources` was allowlisted so the datasource uid could be read
rather than guessed. Every persona's prompt now also says its seeds are a list of
what to ignore *when observed*, never evidence that it was.

That third part was wrong, and it is now reverted — see
[reading the uid was worse than pinning it](MEMORY.md#reading-the-uid-was-worse-than-pinning-it).
