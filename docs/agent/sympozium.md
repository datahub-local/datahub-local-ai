# Sympozium agents

`agents/sympozium/` holds the **agents**; datahub-local-core holds the
**platform**. Core deploys the Sympozium control plane into `automation` along
with the `MCPServer` catalog, the `SkillPack`s and the built-in
`SympoziumPolicy`s. This sub-project only declares `Ensemble`s — teams of
personas — and never re-declares platform objects.

An `Ensemble` is the unit of deployment: installing one stamps out an `Agent` and
a `SympoziumSchedule` per persona and seeds their memory. **Ensembles default to
disabled** in the CRD ("catalog-only"), so a manifest without `enabled: true`
deploys but never runs. The chart's own eight example ensembles are all sitting
in the cluster disabled; ours are separate objects and must not be confused with
them.

```
agents/sympozium/
  Chart.yaml, helmfile.yaml.gotmpl   the sub-project root IS the chart root
  MEMORY.md                          why every knob is set the way it is
  values/default.yaml.gotmpl         per-cluster knobs only
  templates/ensembles.yaml           assembles the Ensembles at render time
  templates/mcpservers.yaml          Deployment + Service + MCPServer per MCP server
  templates/mcp-configmaps.yaml      renders config/<server>/ into a ConfigMap
  config/<server>/                   the data a server mounts at /etc/mcp/<server>/
  templates/_delivery.tpl            the postRun hook and the prompt block
  prompts/delivery/hook.md           the delivery contract, substituted per persona
  projects/<ensemble>/
    ensemble.yaml       team-level spec + `defaults:` stamped onto each persona
    agents/<persona>.yaml   skills, schedule, MCP servers, tool policy, memory seeds
    prompts/<persona>_{system,task}.md
```

Three ensembles, split on trust boundaries and not on subject:

| Ensemble            | What                                                    | Inbound?                |
| ------------------- | ------------------------------------------------------- | ----------------------- |
| `homelab-ops`       | six scheduled read-only reporters, one question each    | no — no channel binding |
| `homelab-responder` | one persona you can ask a question in Slack             | **yes**, the only one   |
| `homelab-reviewer`  | `renovate-reviewer`, the only persona with a write tool | no                      |

The reporters take their readings from the facts server in `datahub-local-ai-mcp`, so their
prompts are a report contract rather than a method — see
[MCP servers](mcp-servers.md).

## Conventions

- **Write the reasoning in `MEMORY.md`, not in the config files.** The YAML under
  `projects/` and `values/` carries values and one pointer line, nothing else;
  `agents/sympozium/MEMORY.md` carries why each knob is set that way, the
  per-persona decisions, and each new incident. That is also where a new lesson
  goes — `README.md` holds the structure and the long write-ups that already
  exist and is not growing further. A comment restating a decision beside the
  value is a second copy of it: the `toolsAllow` note had been pasted into nine
  persona files and the `grafana_list_datasources` note into four before this
  split. Stripping all of it changed neither the parsed YAML nor a byte of
  `helm template` output.
- **A prompt or seed names the lookup; the server holds the data.** Write what a
  persona should *do* — which tool answers which question, how to read a result,
  what to say when nothing comes back — and never what the data currently
  contains. No dimension lists, no column names a tool returns, no shop or
  product or namespace names, no counts, no "every invoice is X". Those are rows,
  and a copy of a row in a prompt or a `memory.seeds` entry is stale the next
  time the pipeline runs, with nothing to revalidate it: the agent cannot tell a
  remembered value from a retrieved one, so it states the stale copy with the
  same confidence. Prefer the shape over the instance — `semantic_list_dimensions
  (metric) says which dimensions exist` outlives `it carries supermarket,
  store_name and store_vat_id`, which was wrong the moment a dimension was added.
  Keep an example generic (`a shop with no rows`, not a brand) so it illustrates
  the rule instead of asserting a fact. What legitimately stays is wiring that is
  true by construction — that S3 here is Garage, that bodega-as-dataset is
  answered by `semantic_*` — because that describes the plumbing rather than what
  flowed through it. This is the same objection as the `toolsAllow` comments and
  the committed manifest above, and it has now cost four incidents; the concrete
  numbers belong in `MEMORY.md`, which is documentation and is read by people.
- **Prompts are files, never inlined.** A persona sets `systemPromptFile` and
  `schedule.taskFile`; the build script *rejects* a literal `systemPrompt` or
  `schedule.task`. Same reasoning as `agents/n8n/prompts/`.
- **Nothing is generated into the repository.** `templates/ensembles.yaml` reads
  `projects/` at render time, so the sources are the only copy. Do not reintroduce
  a committed manifest — it is a second copy that silently drifts from its source.
- **A `memory.seeds` edit is not done when it is merged.** The controller writes
  seeds once, at install, into `ConfigMap/<ensemble>-<persona>-memory` and never
  reconciles them, so a sync updates the Ensemble, `systemPrompt` and
  `toolPolicy` while the run's `## Memory Context` still carries the install-time
  text. Nothing fails and `kubectl diff` cannot see it. Run
  `uv run --with pyyaml python agents/sympozium/scripts/reseed_memory.py`
  (`--apply` to repair) after any seed edit, and when a persona behaves as though
  it never got a correction. It diffs seed *text* rather than counts — a matching
  count with different text is what hid `homelab-oracle`'s drift for eleven days,
  and both drifts found so far were found by accident.
- **Source describes the agent; values describe the cluster.** Only `enabled`,
  `baseURL` and `policyRef` live in `release/values/default.yaml.gotmpl`, merged
  over `spec` at render time. The build script rejects those keys in
  `ensemble.yaml`. Per-persona `model`/`provider`/`runTimeout` come from the
  project's `defaults:` block, because they describe the agent, not the cluster.
- **`toolPolicy` is prefixed, `toolsDeny` is not.** `toolPolicy.allow` uses
  agent-facing names (`k8s_pods_list`) because that is what the model sees;
  `mcpServers[].toolsDeny` uses the server's own names (`pods_delete`) because
  that filter runs at the server. Backwards means a deny that matches nothing.
- **A channel binding is split across source and values, and both halves are
  load-bearing.** The persona carries the type (`channels: [slack]`) and, in hook
  mode, a `{{ DELIVERY }}` token in its
  system prompt; values carry the credential secret (`channelConfigs`) and the
  `sympozium_delivery` knobs — `channel` and `deliveryMode`, with per-persona
  overrides. No CRD field
  carries a destination, so the channel only ever reaches the agent as prompt
  text: the templates substitute exactly `{{ DELIVERY }}`, `{{ CHANNEL }}`,
  `{{ AGENT }}`, `{{ ENSEMBLE }}` and `{{ SCHEDULE }}` and `fail` on any token
  left standing. `{{ DELIVERY }}` expands to one file,
  `prompts/delivery/hook.md`. Chart-only knobs must stay out of
  `sympozium_ensembles` — the webhook decodes `spec` strictly and rejects an
  unknown key outright. Nothing cross-checks the two halves, so read both files
  together whenever either changes. Note the binding is *bidirectional* — an inbound Slack message can start an `AgentRun`
  — which is why `homelab-reviewer`, the only ensemble with a write tool, is not
  bound.
- **The binding is what lets a message leave the pod, so delivery cannot be
  unbundled from it.** `send_channel_message` is registered on an *unbound*
  persona too, and it answers normally — a probe run of `renovate-reviewer`
  called it and reported `Succeeded` with `DONE` — but the ipc-bridge then drops
  the message: `Dropping outbound message to channel not configured on this
  agent`. Nothing fails, nothing arrives. Verified 2026-08-23.
- **Every channel sidecar delivers every instance's message, so N delivering
  personas means N copies of every report.** A binding deploys a
  `<persona>-channel-slack` sidecar, and each one subscribes to the fleet-wide
  `sympozium.channel.message.send` with an unfiltered, non-queue-group JetStream
  consumer: it filters on the transport in `data.channel` and never on the
  `metadata.instanceName` the envelope hands it. Five bound personas in
  `homelab-ops` means five sidecars and five byte-identical Slack messages in the
  same second, from one `send_channel_message` call. Nothing scopes that from the
  channel side: unbinding all but one persona silences the rest (previous
  bullet), `channelAccessControl` is inbound-only, the controller exposes only
  fleet-wide `SYMPOZIUM_IMAGE_REGISTRY`/`SYMPOZIUM_IMAGE_TAG`, and the sidecar
  Deployment declares `replicas: 1` under an `Agent` ownerReference. The
  upstream fix is a one-line filter on `metadata.instanceName` in the sidecar,
  which the envelope already carries.
- **`deliveryMode: hook` is the default and how this repo avoids the fan-out
  without waiting for upstream.** The templates stop
  substituting the posting instructions into the prompt and instead attach a
  `lifecycle.postRun` container that posts `AGENT_RESULT` to the Slack API
  directly. It touches no shared subject, so the report arrives exactly once
  regardless of how many personas are bound. Egress works because the hook pod
  carries no `sympozium.ai/role=agent` label and so escapes
  `sympozium-agent-deny-all` — verified against `api.test` from inside the pod.
  Two consequences are the point rather than side effects: the persona must
  **not** allowlist `send_channel_message` (otherwise it posts *and* is posted
  for, and the run ends on a tool call), and the report becomes the model's final
  text — which is what fixes the empty `status.result`, since the dominant cause
  was never invalid UTF-8 but `terminal turn had empty text`, 60 occurrences
  against 2 in one day. A hook posts unconditionally, so reach for
  `schedule.interval` if a channel gets too busy. A persona with no
  `sympozium_delivery` channel gets no hook at all, which is what keeps
  `homelab-reviewer` silent by design, and `hook.md` deliberately names no tool:
  a 4B model reads a tool name as permission to call one.

  The other mode is **`reply`**, which the responder uses: a bound persona that
  answers in the thread that asked, through the channel sidecar. It takes no hook
  and needs no configured destination — the hook hardcodes one, and that is how
  two questions asked in two different channels were both answered into a third.
  A `reply` persona carries its own answering contract in its prompt instead of a
  `{{ DELIVERY }}` token, and `templates/ensembles.yaml` fails the combination. **A `reply` persona must not allowlist `send_channel_message`
  either**, for the same reason a hook one must not: the reply is the run's own
  final text, `status.result`, posted into the asking thread by the controller,
  while the tool is a separate path that resolves no destination on a reply run.
  Keeping both cost two answers on 2026-08-31 — the model sent the real answer
  with an empty `chatId` (rejected `channel_not_found`) and then wrote a summary
  of having sent it, which is what the reader got. `tool` mode is gone: it cost a
  duplicate copy of every report per bound persona, and nothing used it.
- **`send_channel_message` takes the destination in `chatId`.** Its `channel`
  argument is the *transport* (`slack`, `telegram`, …), never a `#name`. With
  `chatId` unset the tool still answers `Message sent`, targets "owner (self)",
  and on a scheduled run — which has no owner — Slack rejects it as
  `channel_not_found` in the `<persona>-channel-slack` sidecar log, the only
  place a delivery failure is ever visible. This cost every scheduled report for
  two days. Naming the argument was not enough: the prompts showed the call as
  `chatId: "{{ CHANNEL }}"` and a 4B model copied the quotes into the value, so
  Slack rejected the same way for another two days. A prompt for a model this size
  must never show a value inside syntax the model is also expected to strip.
  **No persona holds this tool any more** — the responder was the last and lost
  two answers to it (previous bullet), so both delivery modes now deliver the
  run's final text and nothing in this chart posts by tool call. Full write-up in
  `agents/sympozium/README.md`.
- **The report names its agent; it never invents a time.** Nothing in this fleet
  returns the current time (verified — the runtime injects no clock and no MCP
  server exposes one), so the header carries agent, ensemble and cadence, the
  prompts forbid any date or duration not read from a tool result, and Slack's
  message stamp is the run time. An authoritative in-message timestamp needs a
  `lifecycle.postRun` gate hook, which is the CRD's mechanism for rewriting
  agent output.
- **An HTTP endpoint replaces a persona's schedule; it does not add to it.** The
  `sympozium_web_endpoint` values tree, the render-time skill append and the
  validator's guard for it are all **removed** — nothing in this chart exposes an
  HTTP trigger any more, and the responder covers "ask it something" properly.
  The three reasons it went are worth keeping, because `webEndpoint` is now a
  first-class persona field and someone will be tempted again. A serving
  `AgentRun` makes the schedule controller skip every tick for that agent,
  silently, with the `SympoziumSchedule` still `Active` and no run failing. A web
  run gets **neither `toolPolicy` nor `lifecycle`**, so it is both unbounded — 60
  tools including `write_file` and `execute_command` — and undeliverable, which is
  how one wrote a full CRITICAL report and delivered none of it. And it
  **truncates the task to its first line**, so anything the `taskFile` said past
  the opening sentence is gone. Never put a requirement in a field a caller can
  replace. If an HTTP trigger is ever wanted again, use
  `agentConfigs[].webEndpoint` and re-verify all three.
- **Test with a hand-applied `AgentRun`, not the HTTP endpoint.** It suppresses
  no schedule and takes `systemPrompt`, `task` and `toolPolicy` inline, so a
  probe can differ from the real thing. The pod is deleted on completion
  whatever `cleanup` says, so stream the log while the run is live. A run that
  has *already* finished is still readable, though: Loki keeps every container
  of it, keyed by `status.podName` over the `startedAt`/`completedAt` window,
  which is the only way to diagnose a scheduled run after the fact — and the
  way to count a failure mode across the fleet instead of guessing at it. Tool
  *results* are logged nowhere; replay the query to see what the model saw. But `status.result` is
  dropped whenever the reply contains invalid UTF-8: the runner ships it to the
  controller over gRPC, protobuf refuses to marshal a bad `string`, and the run
  still reports `Succeeded` with no `error`. Our own header caused it — the model
  was told to echo `·` (U+00B7) verbatim and sometimes emitted a broken byte pair
  — so the delivery prompts are ASCII-only inside every indented block. Nothing
  enforces that now, so grep a prompt you touch for non-ASCII inside an indented
  block (`grep -nP '^\s+.*[^\x00-\x7F]'`). A model can still corrupt a character on its
  own, so stream `kubectl logs <pod> -c agent -f` rather than reading the object
  afterwards, and never read an empty `result` as a quiet run.
- **`toolsAllow` is the prompt budget; `toolPolicy` is only the permission.**
  `toolPolicy` filters at the LLM request, but every tool the server exposes is
  still *registered* and its schema still injected — a persona allowing nine
  tools logs `tools enabled: 60 tool(s) registered`, because grafana alone
  exposes 66 and the persona only denied 14. At roughly 670 tokens per schema
  that is ~40k of prompt — measured: 40,500 first-call input tokens without
  `toolPolicy` versus 4,095 with it — and it is spent on *every* call in the
  loop, not once. That overflowed the window outright while it was 32,768
  (silently truncated from the front, losing the persona and the report format);
  at 65,536 it merely leaves no headroom for a large Prometheus result and gives
  a 4B model sixty tools to choose between. Every persona therefore pins
  `mcpServers[].toolsAllow` to exactly the tools its `toolPolicy.allow` names,
  unprefixed. Drift between the two lists is silent — it costs prompt budget and
  fails nothing — so diff them by hand when editing either. The `toolsDeny` lists are now redundant by construction and kept only as a record
  of which write names are real; they are not the enforcing mechanism.
- **`toolPolicy.allow` is a strict allowlist.** Omitting a tool disables it, so
  adding a capability means adding the tool name *and* wiring its MCP server on
  that persona. The build script cross-checks the two.
- **Schedules are UTC.** No Sympozium CRD has a timezone field, unlike the n8n
  workflows which set `Europe/Madrid` explicitly. Write cron in UTC with the
  local time in a comment.
- **Every CRD-defaulted field is stated.** `mcpServers[].timeout`,
  `schedule.firstTick`, `memory.maxSizeKB` and `sharedMemory.storageSize` all
  carry a `default:` in the Ensemble CRD, so the API server writes them into the
  live object at admission and ArgoCD reports permanent drift against a manifest
  that omits them. Write the value out even when it *is* the default, and
  re-derive the list after a control-plane bump (`kubectl get crd ensembles.sympozium.ai -o json | jq '.. | objects |
  select(has("default"))'`). Note that `kubectl diff` cannot see this class of
  drift — it defaults both sides; diff a `--dry-run=server` apply against the
  rendered manifest instead. Core's ApplicationSet also carries
  `ignoreDifferences` on `memory.maxSizeKB` and `schedule.firstTick`; keep them
  as a backstop for a future default, not as the mechanism.

## The thinking to carry forward

These are the judgement calls behind the current fleet. Apply the same reasoning
rather than copying the outcomes, since the constraints will change.

- **The `mcp-k8s` ClusterRole in core is what actually grants Kubernetes read
  access — the SkillPack RBAC is not.** Every `k8s_*` call a persona makes goes
  through the `datahub-local-core-automation-sympozium-mcp-k8s` ServiceAccount,
  whose ClusterRole is `apiGroups: ["*"], resources: ["*"], verbs:
  [get,list,watch]`. That is the reason a new object kind — a Longhorn volume, a
  CloudNativePG `Cluster`, a cert-manager `Certificate` — works without a core
  change, and it is deliberate: an unlisted group fails silently and the agent
  just writes a blander report. A `SkillPack`'s `sidecar.rbac` grants a *separate*
  identity used only by that pack's sidecar, so narrowing it protects nothing
  unless a persona mounts the pack — none do. Check which of the two you are
  looking at before changing either.
  The cost of the wildcard is that `k8s_resources_get` returns whole objects,
  which for a Secret is the base64 values in full (verified against
  `mcp-slack-token`, 2026-08-24). So that tool is in `BANNED_TOOLS`:
  `k8s_resources_list` returns a table — names, types, key counts, the kind's own
  printer columns — and is the shape a reporter should have. If a persona ever
  genuinely needs an object's contents, narrow the ClusterRole to enumerated
  groups first rather than allowlisting the tool against a wildcard.
- **Verify names against the running system; never infer them.** Every skill,
  MCP server and tool name here was read off the cluster (`kubectl get
  skillpacks`, and a `tools/list` call against each MCP server) because a wrong
  name fails *silently* — the tool simply never appears and the agent produces a
  blander report. Core's own catalog had this bug twice: its k8s server denied
  `delete_resource`/`create_resource`/`update_resource` and its postgres server
  denies `execute_write_query`, and **none of those tool names exist**. The k8s
  half was fixed on 2026-08-23; postgres is still open, and github, argocd and
  grafana carry no catalog denies at all. Personas here re-deny the real names
  themselves, which is the only reason none of it was ever exploitable.
  Re-check after image bumps — every MCP image is pinned `:latest`.
  A whole *server* fails the same silent way: core's `mcp-k8s` was the one
  MCPServer declared `transportType: http`, the discovery bridge asked for the
  service root, and `kubernetes-mcp-server` serves `/mcp` — so it 404'd and every
  `k8s_*` tool was missing from every persona from its creation until
  2026-08-23, with `MCPServer.status.ready` reporting `true` throughout. Read
  `kubectl logs <run-pod> -c mcp-discover` after any transport or image change;
  it prints the per-server tool counts.
- **Split ensembles on trust boundaries, not on subject.** Ensemble-level
  settings apply to every persona inside, so the one agent holding a write tool
  (`renovate-reviewer`, which may only comment) lives in its own ensemble. The
  blast radius is then visible in the directory listing.
- **Breadth comes from more personas, not fatter ones.** A persona carries
  exactly one schedule, so "same agent, different focus on a different day" is
  not expressible — it has to be another persona. When a role grows a second tool
  surface, split it (`db-steward` came out of `service-janitor` for exactly
  that reason) rather than growing the checklist. Keep each run to one question
  and roughly five to seven tools.
- **A correct metric name is not a correct reading.** `sre-sentinel` was told to
  query `kubelet_volume_stats_available_bytes / kubelet_volume_stats_capacity_bytes`
  and flag anything above 80%. Both metrics exist and were verified present — but
  that ratio is the fraction *free*, so it flagged the emptiest volumes and could
  never flag a full one. It called a 2%-used volume "97.9% full, write operations
  failing" on every run for days, and because a non-empty **Filling up** section
  is one of the change conditions, it also forced a Slack post every time. Fill
  expressions now read `100 * (1 - available / capacity)` and carry a
  `group_left` join on `kube_persistentvolumeclaim_info` restricting them to
  `longhorn|longhorn-no-replica`, because all five `nfs` PVCs report the same
  shared 1.9 TB capacity and a per-volume percentage there is meaningless.
  The expression now lives in `datahub-local-ai-mcp`, where a test asserts the direction
  rather than a regex reading the prompt. Give a small model the
  literal expression, not a description of it — it will not assemble a join from
  prose, and it will report whatever it computes with total confidence.
- **A discovery tool that returns several plausible answers is a liability.**
  `grafana_list_datasources` was allowlisted so the Prometheus uid would not be a
  hardcoded guess. It produced one: this Grafana serves three datasources, and
  Loki's uid is the hex string `P8E80F9AEF21F6940` while Prometheus's is the
  literal word `prometheus`. A 4B model takes the hex string for the real
  identifier and the bare word for a placeholder to resolve, so every PromQL
  query went to Loki and answered `404 page not found` — against a prompt that
  stated the right value two paragraphs above. The tool is gone from all four
  Prometheus-reading personas and the uid is pinned; the datasource is
  provisioned `readOnly` by kube-prometheus-stack, so the literal is stable, and
  if it ever changes the agent reports every metric unavailable, which is loud.
  Prefer a pinned literal plus a loud failure over a lookup the model has to
  choose from.
- **A mandatory report format will be satisfied with invented numbers.** With
  Prometheus 404ing, `endpoint-warden` still owed seven columns per node, so it
  filled the disk column from the only tool that answered — relabelling
  `k8s_nodes_top` memory as disk and calling a 5%-full control-plane disk "79%
  disk fill (CRITICAL)", then emitting the whole report twice with different
  numbers. The standing "never report a number you did not retrieve" rule lost to
  the format demanding a value. A format is only safe if it makes absence
  expressible: a column with no metric is now the literal `unavailable`, a row of
  those is a legitimate row, each figure must come from the metric named for it,
  and the sections are emitted exactly once. Verified with a hand-applied
  `AgentRun`, which now returns the real 2-35% spread in one tool call.
- **An instruction to investigate needs a budget and an exit.** `sre-sentinel`
  was told to root-cause every new alert and given no cap. On 2026-08-24 it read
  a real new `TargetDown{job="longhorn-backend"}`, then spent five lookups on it
  — a scrape-job name passed as a pod name, `namespace` written as a term inside
  `labelSelector`, the same call repeated byte-for-byte — and every one returned
  empty. It then emitted a turn with neither text nor a tool call, which the
  runner logs as `terminal turn had empty text`, reports as `Succeeded` with a
  null `result`, and the delivery hook renders as a placeholder. The alert went
  unreported. A model this size does not decide on its own that it has learned
  enough to start writing, so the prompt grants *at most 3 lookups* per alert and
  names what to write when they yield nothing (`cause not determined`, stated to
  be a legitimate finding). Both halves matter: a cap with no escape hatch just
  relocates the silence, exactly as `endpoint-warden`'s mandatory table produced
  invented numbers until absence became expressible as `unavailable`. Give the
  model the literal shape of the call too — `namespace` is its own argument on
  every `k8s_*` tool and never a label — and remember that hook mode removed the
  *dominant* cause of an empty result, not the mechanism. `db-steward` then
  repeated the whole failure the same day against `k8s_resources_list`, because
  the fix had been written for the persona that broke rather than for the tool:
  seven of its fourteen calls guessed selectors for one CloudNativePG `Cluster`
  (`name` as a label, `namespace` inside `labelSelector` again, two contradictory
  equalities on one key, one call repeated byte-for-byte) and the day's Postgres
  and Valkey readings, already in hand, were never written down. So the budget,
  the exit and the selector rules now attach to any prompt naming
  `k8s_events_list`, `k8s_pods_log` or `k8s_resources_list`. Write them into any
  new prompt that names one of those three; nothing checks it for you.
- **`MAX_TOOL_ITERATIONS` is a real ceiling and hitting it is silent.** The
  runner caps tool calls per run at 50; five runs have hit it, and the failure is
  worse than a truncated report — the run ends `status: error` and the whole
  sweep is lost, leaving the delivery hook a failure notice to post instead of a
  report. (The hook *does* run on a failed run — `postRun` is best-effort and
  fires whatever the phase; this file said otherwise until 2026-09-13.)
  `endpoint-warden` used 48 of 50 one run and failed on 50 the next. Both
  ensembles set it to `"100"` in `defaults:`, quoted because the CRD types `env`
  as `map[string]string` and the webhook decodes strictly. The real limit is the
  65536 context every accumulated tool result must fit inside, so raising this is
  headroom, not permission to sweep wider.
- **A cumulative counter is not a state, and the suffix will not tell you
  which is which.** `db-steward`'s prompt called
  `cnpg_pg_stat_archiver_failed_count` "the most important number you look at"
  and never said it was a counter, so a lifetime total of 2 — two failures 5.4
  days old, against a successful archive 95 seconds old and
  `increase(...[24h]) = 0` — paged CRITICAL "recovery is silently broken" on
  every run, twice into Slack. Same class as the fill inversion: right metric,
  wrong reading. Prompts now carry the literal
  `increase(cnpg_pg_stat_archiver_failed_count[1h])` and a rule that a non-zero
  total with a zero increase is *healthy*. Two traps found fixing it.
  `cnpg_backends_total` and `cnpg_backends_waiting_total` are **gauges** despite
  the `_total` suffix, so a suffix rule fails a correct prompt — read the type
  from Prometheus's metadata API instead (`curl -sG .../api/v1/metadata
  --data-urlencode metric=<name> | jq -r '.data[][0].type'`), which is what
  the MCP repo's tests assert. And prose does not work: `endpoint-warden` said
  "take the rate, not the raw counter" twice and still handed the model bare
  metric names, so both prompts now write the window out. A model this size also
  drops the wrapper — given `increase(m[1h])` it sent `m[1h]` and labelled the
  answer as the increase — so the prompts state that an `expr` is the whole
  line, function call included, which is the `chatId` lesson in a new place.
- **A permanent finding is a bug in the prompt, not a problem in the fleet.**
  `endpoint-warden` reported orpi-0's kernel as drift against orpi-1/2/3 every
  run for days. It is not drift: orpi-0 is an Orange Pi 4 LTS (RK3399, rockchip64
  tree), orpi-1/2/3 are Orange Pi 5B (RK3588, rk35xx vendor tree), the amd nodes
  are Debian trixie amd64 and the NAS is TrueNAS. Different SoC families cannot
  converge on a kernel, so the finding could never be actioned and never clear.
  Versions are comparable only *within* a hardware class — the one real pair here
  is amd-1's 6.12.96 against amd-2's 6.12.101 — and a class of one is never the
  odd one out. Check that a rule you give a persona is one the fleet can actually
  satisfy, especially where a non-empty findings section is itself a change
  condition that forces a post.
- **Verify the telemetry exists before writing a prompt against it.** Every
  metric named in a prompt was confirmed present in this Prometheus. Two traps
  found this way: Valkey is scraped by a redis exporter so its metrics are
  `redis_*` and never `valkey_*`, and node-exporter's SMART series is
  `smartmon_temperature_celcius` (upstream typo). A small model cannot recover
  from a plausible-but-wrong metric name. Where telemetry is genuinely missing —
  systemd units, OS package updates, Garage/S3 — the prompt must not pretend
  otherwise; record the enabling change instead
  (`agents/sympozium/MEMORY.md#follow-ups-to-share-with-the-other-repos`).
- **Seed the noise.** Most alerts in this cluster fire permanently, including
  `KubeSchedulerDown`/`KubeControllerManagerDown`, which are artifacts of k3s
  embedding those components with no separate metrics endpoint. A small model
  cannot deduce that, so the known-chronic set lives in `sre-sentinel`'s memory
  seeds and reports are shaped new / still firing / resolved. Re-seed when the
  chronic set changes.
- **Read-only by default, and `toolPolicy` is not the boundary.** Every persona
  denies `write_file` and `execute_command` — the latter is a shell, and with MCP
  servers wired it is also redundant. An agent that changes things should be a
  separate, explicitly authorised one, not a capability quietly added to a
  reporter. But the deny filters *schema registration*, not dispatch: the runner
  logs `tool policy: denied tool "execute_command"`, omits the schema, and then
  executes the call anyway if the model produces it. A SkillPack is what makes it
  produce one — `sre-observability` says "Use `execute_command` for all shell
  commands" and `k8s-ops` claims "full cluster admin access ... kubectl works out
  of the box", and 744 shell commands ran across the fleet in a week on personas
  that denied it. Both packs also declare sidecar RBAC that the controller binds
  to the *shared* `sympozium-agent` ServiceAccount, so mounting one granted every
  agent in `automation` create/delete on pods, `pods/exec`, secrets, deployments
  and rolebindings. Both are removed, and nothing stops a third being mounted, so
  read a pack's `.spec.skills[].content` **and** `.spec.sidecar.rbac`
  before mounting it: a skill is prose competing with the persona's prompt, and
  prose wins.
- **The model constrains the design.** The fleet runs on the LiteLLM gateway in
  `data` (`http://datahub-local-core-data-litellm.data.svc.cluster.local:4000/v1`),
  model `opencode-go/deepseek-v4.1-flash`, with `opencode-go/glm-5.3-flash` as
  the gateway's router fallback. The cluster-local Ollama GPU queue is no longer
  on the path; the 90K window and `OLLAMA_NUM_PARALLEL` reasoning that used to
  live here are history, not constraints. **Every agent prompt must still stay
  short and literal, like a compact GitHub/Copilot prompt:** one job, exact tool
  order, a small lookup cap with an explicit no-result exit, exact output shape,
  and final delivery instruction. Put deterministic gathering, reusable context,
  and detailed method in MCP code or `MEMORY.md`, not prompt prose. Do not
  restore long tutorials, copied schemas, or repeated background explanation.
  `toolsAllow` bounds injected schema and is a context-budget control, not merely
  permission. `workflowType: autonomous`, five-to-eleven-tool allowlists, two
  skills per persona, `runTimeout: 30m` (45m for the reviewer) and staggered
  schedules with `firstTick: afterInterval` all stay as reviewable defaults —
  revisit them with measurements, not assumptions, now that the serving model
  changed. Note the staggering still only holds for cron ticks: the Ensemble
  controller starts a run within the same second as every `SympoziumSchedule` it
  rewrites, so one `helmfile apply` touching N personas queues N real runs —
  they post to Slack, spend `MAX_TOOL_ITERATIONS` and write memory — whatever
  `firstTick` says and with `status.nextRunTime` still pointing at tomorrow.
  Apply once and probe with a hand-applied `AgentRun`. Prompts name the tools to
  call in order and end with a required section layout and a "no report, no run"
  rule.
- **`policyRef: permissive` is deliberate.** `restrictive` and
  `network-isolated` both set `networkPolicy.denyAll` with no `allowedEgress`,
  which would cut agents off from Ollama *and* every MCP server; `restrictive`
  also gates tools deny-by-default against a rule list containing only built-in
  names, denying every MCP tool. Restriction is enforced per-persona in
  `projects/`, where it is reviewable, instead.
- **Don't duplicate n8n.** `agents/n8n/workflows/credentials_expiry_review`
  owns n8n credential expiry; `service-janitor` stays strictly cluster-side
  (certificates, tokens, secrets). Check the n8n workflows before giving a
  Sympozium agent a job.
