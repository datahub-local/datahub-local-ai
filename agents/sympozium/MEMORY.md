# Sympozium memory

Working notes for `agents/sympozium/`: why each knob is set the way it is, and
what broke when it was set otherwise.

**This file is where that reasoning goes.** Not in comments in the YAML, and not
as another section of `README.md`. The split is: config files carry values,
`README.md` carries the structure and the runbooks, and this file carries every
*why*, including the incidents.

Three rules for writing here:

- **One statement, one place.** The `toolsAllow` note had been pasted into nine
  persona files and the `grafana_list_datasources` note into four. Nine copies
  drift; one does not.
- **Say what was measured, with the date.** A claim with a number and a date can
  be re-checked. "This is slow" cannot.
- **Compress an incident once its lesson is general.** A note is only useful if
  the next person reads all of it. This file reached 248 KB and roughly 4,200
  lines by 2026-08-30, most of it console transcripts re-proving rules stated
  five sections earlier; it was cut to a third of that on the same day, keeping
  every distinct lesson, every literal, every command and every date, and
  dropping the evidence that had already done its work. Add an incident in full
  if it is new; fold it into the rule it confirms if it is not.

---

## Where things live

| What                                                           | Where                                                                                                    | Why                                                   |
| -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| Values only, no rationale                                      | `projects/*/ensemble.yaml`, `projects/*/agents/*.yaml`, `values/default.yaml.gotmpl`, `templates/*.yaml` | A comment restating a decision is a second copy of it |
| Structure, conventions, runbooks, how to test                  | `README.md`                                                                                              | Reference you read before doing something             |
| Every *why* — knob rationale, per-persona decisions, incidents | this file                                                                                                | Read when something surprises you                     |
| Agent behaviour                                                | `projects/*/prompts/*.md`                                                                                | The model only reads the prompts                      |
| Machine-checkable rules                                        | `templates/*.yaml` `fail` calls                                                                          | Rendering is the only gate on `projects/`             |

`values/default.yaml.gotmpl` has one trap: helmfile renders it as a Go template
**including its comments**, so a literal `{{ ... }}` brace pair anywhere in it —
even commented out — is a template action and an undefined function. Writing a
token name with its braces in a comment there broke the ArgoCD CMP once. Name
tokens without braces.

---

## `scripts/validate.py` was deleted, and these checks went with it (2026-08-31)

1,319 lines, guarding three ensembles and seven personas. It went because most of
it was a **second copy of something we do not own**: the `SKILLS` and
`MCP_SERVERS` inventories and their per-server tool lists (read off live
`tools/list` calls), `CATALOG_DENIED` (mirroring `spec.toolsDeny` on catalog
MCPServers we do not author), `CRD_DEFAULTS`, `SCHEDULE_TYPES`, `FIRST_TICKS`,
`LOCAL_PROVIDERS`, `KNOWN_ENV`. Every MCP image is pinned `:latest` and the
control plane bumps independently, so each of those mirrors goes stale on someone
else's release, and **a stale mirror fails a correct config** — which is a worse
failure than the silent one it was guarding, because it blocks the fix. It had
also accumulated ~100 lines of dead code (`CUMULATIVE_COUNTERS`,
`VALUES_ONLY_SKILLS`, `WRITE_TOOLS`, `_web_endpoint_config`, all defined and
never called) without anything noticing, which is its own evidence.

This is the same reasoning that removed `hardware_classes.yaml` from
`agents/mcp/` and the ~600 lines of prose regexes before it. The pattern is
worth naming: **a check that mirrors a system it does not own is a maintenance
liability disguised as a safety net.**

Two things happen to be true and made this cheap. `templates/ensembles.yaml`
already `fail`s on the highest-value cases — name/directory and name/filename
mismatch, a missing or empty `systemPromptFile`, an unsubstituted prompt token, a
`deliveryMode` that is neither `hook` nor `reply`, `reply` plus a
`{{ DELIVERY }}` token, `reply` without a channel binding, a channel binding with
no configured destination, a token in a task prompt. And the admission webhook
decodes `spec` strictly, so unknown keys, bad enums and type errors are rejected
**loudly** at sync time; those never needed a local validator.

What is genuinely unguarded now — every one of these renders and deploys
cleanly, and fails silently or not at all:

| Lost check | What it costs |
| --- | --- |
| `send_channel_message` on a hook or reply persona's allowlist | Cost two answers on 2026-08-31. The cheapest to put back as a `fail` in `templates/ensembles.yaml` |
| `toolsAllow` ↔ `toolPolicy.allow` drift | Prompt budget, silently. See *The tool schemas, not the report, are what fills the context* |
| `BANNED_TOOLS`, and the two shell-teaching SkillPacks by name | An agent that gets a shell. See *A SkillPack overrode every tool decision in this repository* |
| A values-only key set in `ensemble.yaml` | Values win the merge; the source line is dead and reads as live |
| A CRD-defaulted field omitted | Permanent ArgoCD OutOfSync, which `kubectl diff` cannot see |
| A memory seed containing `: ` | Webhook rejects the whole Ensemble. `--dry-run=server` is again the only thing that sees it |
| An MCP `project:` naming a directory that does not exist | Pod crash-loops on `no such project` |
| A wrong MCP server or tool name | The tool silently never appears. See *Tool names are not guessable* |
| Non-ASCII inside an indented `prompts/delivery/` block | An empty `status.result`. `grep -nP '^\s+.*[^\x00-\x7F]'` |
| `allowedSenders`/`allowedChats` unset on the inbound-bound persona | An open door on the one ensemble that takes inbound messages |
| `provider` ↔ `baseURL` ↔ `authRefs` coherence | The three live in two files and the controller matches `provider` byte for byte with no case folding. A miss is a run with no credential, or a metered model pointed at Ollama's `.svc` port — not a startup error. This check was written and never committed |
| A prompt file referenced by nobody | Dead file, harmless |

So the deploy checklist grew in exchange: render through `helmfile`, then
`kubectl apply --dry-run=server` whenever a cluster is reachable, and read the
table above when touching delivery, tools or skills. If any single row starts
recurring, add a `fail` to `templates/ensembles.yaml` for that one row — not a
new validator. Rendering is the gate; keep the checks where the render can see
them, and never re-import an inventory the cluster already answers.

---

## Rules this file keeps arriving at

Every incident below is one of these. Read this list first; the sections are the
evidence.

1. **A tool that does not arrive fails silently.** Wrong name, wrong transport,
   denied at the catalog, stale image, unreadable RBAC — the tool simply never
   appears, the run reports `Succeeded`, and the report gets blander. This is the
   fleet's dominant failure mode and every layer has produced it.
2. **Give the model the literal value, never a description of it and never a
   lookup to choose from.** `chatId`, the datasource uid, the `group_left` join,
   the `increase(...)` wrapper, owner and repo, the catalog name, `endTime`, the
   one permitted SQL statement.
3. **Never show a value inside syntax the model is also expected to strip.** A 4B
   model copies an example character for character, quotes included.
4. **Absence has to be expressible, and a lookup that could not run must never
   render as one that found nothing** — in a prompt, in a tool, or in RBAC. The
   layer with the most authority does the most damage.
5. **A mandatory shape will be satisfied with invented content.** A column with
   no metric behind it gets filled from whatever answered.
6. **An instruction to investigate needs a lookup budget and a named exit.** A
   model this size does not decide on its own that it has learned enough to
   start writing; a cap with no escape hatch just relocates the silence.
7. **A permanent finding is a bug in the prompt, not a problem in the fleet.**
8. **A correct metric name is not a correct reading.** Direction, counter-vs-gauge,
   the join, and the tool's hidden scope are all part of the reading.
9. **A partial enumeration reads as the complete set.** Refusing needs a closed
   list; accepting must never have one.
10. **Prose adjacent to a figure is absorbed into it, and position is not
    decoration.** A caveat can never be last; a rule about what to write belongs
    in the paragraph about writing.
11. **Prose beats configuration.** A SkillPack that names a tool defeats a
    `toolPolicy` that denies it. So does a required output format.
12. **Verify every name and every metric against the running system.** Never
    infer one from a convention, a README or another repository's manifest.
13. **A derived quantity is a reading too.** If a report will compare two
    numbers, compare them in code.
14. **Every answer needs a bound**, and a bounded answer is spent in list order:
    order by how much each row identifies.
15. **Guards do not survive a prompt rewrite; only a test does.**
16. **A false finding in auto-stored memory is not a stale fact, it is an
    instruction not to look.**
17. **A check that mirrors a system it does not own is a liability, not a safety
    net.** It goes stale on someone else's release and then fails a correct
    config, which blocks the fix. Keep checks where the render or a test can see
    them; let the cluster answer for the cluster.

---

## The model constrains the design

Inference is the cluster-local Ollama core deploys, on one 6 GiB RTX 3060 Laptop
(`datahublocal-amd-2`) holding a single resident model. That shapes most of the
choices here.

The model is `qwen3.5:4b` — 3.16 GiB of weights, hybrid attention
(`full_attention_interval = 4`, so only 8 of 32 layers keep a growing KV cache at
~32 KiB/token, roughly 4.5x cheaper than uniform GQA at this size). The window is
65536, set by `OLLAMA_CONTEXT_LENGTH` on core's ollama Deployment with
`OLLAMA_FLASH_ATTENTION=1` and `OLLAMA_KV_CACHE_TYPE=q8_0` to keep the cache on
the GPU. **Read the effective value from `GET /api/ps` with the model resident** —
never from this file, and never from `/api/show`, which reports the
architecture's 262144 ceiling. Re-check `size_vram == size` after any change to
either flag, the window or the model: a spill to CPU does not fail, it just makes
every run several times slower.

What follows from it:

- **`workflowType: autonomous`, not `delegation`.** Delegation needs a model that
  reliably emits `delegate_to_persona` with a coherent payload. Revisit by
  testing, not by assuming.
- **Breadth comes from more personas, not fatter ones.** Five to seven tools and
  one question per run for a reporter. Sixty tools is how you get an agent that
  calls none of them; a fourteen-item checklist is how you get one that does
  three items and writes a confident summary. `homelab-oracle` (29 tools) and
  `renovate-reviewer` (12) are deliberate exceptions, both multi-source by job.
- **Ollama serves one request at a time here.** `OLLAMA_NUM_PARALLEL` is unset and
  must stay unset: llama.cpp divides `n_ctx` across slots, so two slots would hand
  each run the 32768 window that used to truncate the persona out of its own
  prompt. Concurrency costs latency and cache thrash, not correctness — measured
  ~12 s of queue wait on a 3 s call, every request still `200` with
  `truncated = 0` at `n_ctx_slot = 65536`.
- **`runTimeout: 30m` (45m for the reviewer)** against a 10m default.
- **Staggered schedules and `firstTick: afterInterval`.** Holds for cron ticks
  only — see *An apply fires an immediate run per touched schedule*.
- **Short, literal prompts.** One job, exact tool order, a small lookup cap with
  a named no-result exit, exact output shape, delivery. Reporters run 0.8–1.7 KB;
  the oracle 5.8 KB because it routes every question the homelab gets across five
  servers. Deterministic gathering belongs in `agents/mcp/`, durable rationale
  here.
- **Thinking is on at `high`** — see *Thinking was off, and the switch is in the
  wrong repo*.

Swapping in a hosted model is a `baseURL` change plus an `authRefs` secret; the
prompts and allowlists would then be worth loosening. `homelab-oracle` is the
first persona to do it — see *The oracle runs on OpenRouter, and the ensemble is
the only place a credential fits*. Everything above still describes the five
reporters and the reviewer, which stay on Ollama.

---

## Knobs that repeat across every persona

Properties of the platform, not of any one agent. These were the same comment
pasted into every file.

- **`mcpServers[].toolsAllow` mirrors `toolPolicy.allow` with the server prefix
  stripped.** `toolPolicy` filters at the LLM request; every tool the server
  exposes is still *registered* and its schema still injected, so `toolsAllow` is
  what bounds context — it runs at the server. Drift between the two lists is
  unguarded since the validator was removed, and it fails nothing: it just costs
  prompt budget. Diff them by hand when editing either. Measurements in *The tool
  schemas, not the report, are what fills the context*.
- **`mcpServers[].toolsDeny` is redundant by construction** now that `toolsAllow`
  pins the surface. Kept only as a record of which write-tool names are real,
  verified against a live `tools/list`. Not the enforcing mechanism.
- **`grafana_list_datasources` is banned everywhere** — see *Reading the uid was
  worse than pinning it*. No persona wires the grafana server at all now.
- **`schedule.firstTick: afterInterval`, stated rather than defaulted.** The CRD
  carries a `default:` so an omitted value is written in at admission and ArgoCD
  reports permanent drift; and `immediate` would queue every persona's cold run
  against one GPU.
- **Every CRD-defaulted field is written out** for that same drift reason —
  `mcpServers[].timeout`, `schedule.firstTick`, `memory.maxSizeKB`,
  `sharedMemory.storageSize`. `kubectl diff` cannot see this class of drift (it
  defaults both sides); diff a `--dry-run=server` apply against the render.
  Re-derive after a control-plane bump:
  `kubectl get crd ensembles.sympozium.ai -o json | jq '.. | objects | select(has("default"))'`.
- **Schedules are UTC.** No Sympozium CRD has a timezone field, unlike the n8n
  workflows. Local times are in the persona table below, not beside each cron.
- **`MAX_TOOL_ITERATIONS: "100"`** in every ensemble's `defaults:`. The runner
  caps tool calls at 50 and hitting it is silent *and worse than truncation*: the
  run ends `status: error`, so the `postRun` delivery hook never fires and nothing
  arrives. Five runs hit it; `endpoint-warden` used 48 of 50 on 2026-08-24 04:30
  and failed on 50 at 06:15. Quoted because the CRD types `env` as
  `map[string]string` and the webhook decodes strictly. The real ceiling is the
  65536 context every accumulated result must fit inside, so this is headroom,
  not permission to sweep wider.

## Ensemble-level decisions

Split on trust boundaries, not on subject: ensemble-level settings apply to every
persona inside, so the blast radius is visible in the directory listing.

- **`homelab-ops`** — five read-only scheduled reporters, no write tool of any
  kind, no channel binding (delivery is a `postRun` hook). `sharedMemory` is on so
  personas can see each other's notes — though see *Shared memory is inert* for
  why that is currently not true in practice.
- **`homelab-reviewer`** — holds the fleet's only write tool
  (`github_add_issue_comment`), so it gets its own policy binding and its own
  blast radius. No shared memory. `runTimeout: 45m` — reading a changelog and a
  diff is the longest job in the fleet. Bound to no channel: its DO NOT MERGE
  comment on the pull request is the alert.
- **`homelab-responder`** — one persona, `homelab-oracle`, the only inbound
  surface and the only agent driven by text the fleet did not write.
  `deliveryMode: reply`.

## Per-persona decisions

Local times are Madrid, UTC+2 in summer and UTC+1 in winter. **Nothing validates
this table against the YAML in either direction**, and it has drifted in both:
on 2026-08-29 `renovate-reviewer`'s row was stale while `service-janitor`'s YAML
was wrong. A cron change is two edits.

| Persona             | Schedule       | Why that cadence                                                                                                                                                                                                  |
| ------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sre-sentinel`      | heartbeat, 6h  | Not the detector — the digest. Alertmanager already routes every alert to Robusta, which posts to Slack; this adds new-vs-chronic, root cause and the volume fill check no alert rule covers. At 30m it was 48 messages a day restating Robusta. |
| `endpoint-warden`   | `30 4 * * *`   | 04:30 UTC = 06:30 Madrid summer.                                                                                                                                                                                  |
| `service-janitor`   | `0 5 * * *`    | Daily, not weekly: certificates, tokens and backup freshness all move inside a day.                                                                                                                               |
| `db-steward`        | `30 5 * * *`   | Half an hour after the warden so the two do not contend for the GPU.                                                                                                                                              |
| `gitops-auditor`    | every 4h       | Nothing else watches ArgoCD sync state — Robusta forwards events and alerts, not drift. 4h still gives its "drift that survives two consecutive runs" rule an 8h window.                                          |
| `renovate-reviewer` | `0 10 * * 0,6` | Weekends, off the weekday slot: a 4B model re-reviewing the same PR hourly is noise and would hold the GPU against the ops agents.                                                                                 |
| `homelab-oracle`    | none           | Inbound only.                                                                                                                                                                                                     |

Other per-persona notes:

- **`sre-sentinel`'s memory seeds are the known-chronic alert set**, re-verified
  against `ALERTS` on 2026-08-22. Without them the agent reports the same firing
  series forever. A seed is a list of what to *ignore when observed*, never
  evidence that something was observed, which is why each one says so. Re-seed
  when the chronic set changes — by 2026-08-22 `KubeSchedulerDown` and
  `KubeControllerManagerDown` had stopped firing and the set was down to four
  alertnames, which is exactly when a stale seed becomes a fabricated
  observation.
- **`db-steward`'s postgres server denies `execute_sql`** — the one
  write-capable tool there, and postgres-mcp defaults to unrestricted access
  mode. The `analyze_*` tools answer everything it needs. It keeps that server
  because `analyze_db_health` is instance-wide.
- **`db-steward` came out of `service-janitor`** when the role grew a second tool
  surface. A persona carries exactly one schedule, so "same agent, different
  focus on a different day" has to be another persona.
- **`gitops-auditor` needs no `toolsDeny`**: the ArgoCD MCP server exposes no
  write tools at all.
- **`service-janitor` stays strictly cluster-side** (certificates, tokens,
  secrets). `agents/n8n/workflows/credentials_expiry_review` owns n8n credential
  expiry, and its dataset documents why that date lives in the credential's name.
  Check the n8n workflows before giving a Sympozium agent a job.
- **`endpoint-warden` has no host access.** Everything is node-exporter metrics,
  so the agent stays unprivileged. Anything genuinely needing the host is out of
  scope.
- **Nothing here deletes.** `service-janitor` reports cleanup and prints the
  commands; a human runs them.

---

## `values/default.yaml.gotmpl` — the per-cluster knobs

Only settings that could legitimately differ between clusters. Everything
describing *what an agent is* lives in `projects/` and is read at render time.
Nothing rejects a values-only key in `ensemble.yaml` any more: values win the
merge, so a value set in the source renders as whatever `values/` says and the
source line is silently dead.

Chart-only trees (`sympozium_delivery`, `sympozium_delivery_hook`,
`sympozium_mcp_servers`) are deliberately **outside** `sympozium_ensembles`,
because everything under that tree is merged into the Ensemble spec and the CRD
webhook decodes strictly — an unknown key is rejected outright
(`unknown field spec.verbosity`), not pruned.

**Delivery channels are split by what a reader would do about the message**, not
by which agent produced it, because a channel is really one notification setting:

| Channel                 | Carries                                        | Notifications          |
| ----------------------- | ---------------------------------------------- | ---------------------- |
| `#monitoring-ai-health` | the daily personas — hardware, databases, cleanup | scan-later, can be off |
| `#monitoring-ai-alerts` | `sre-sentinel`                                 | on                     |
| `#monitoring-ai-drift`  | `gitops-auditor`                               | on                     |

Keeping the frequent personas out of `-health` is what lets `-alerts` keep
notifications on without the daily hardware report training you to mute it.

`verbosity` and `notify` are absent everywhere, and on a hook-mode persona
neither could do anything anyway: a hook posts unconditionally. Nothing rejects
them now, so a re-added knob would simply be ignored. The cost is real — every report arrives every run. Stretch
`schedule.interval` if a channel gets too busy.

**`channelConfigs`** maps a channel type to the Secret holding its credentials.
The controller sets `ConfigRef` on every generated Agent whose agentConfig lists
that type in `channels`, so a persona bound to a type with no entry here binds to
nothing. `mcp-slack-token` is projected into `automation` by
datahub-local-secrets and carries `SLACK_BOT_TOKEN` (outbound `chat:write`) and
`SLACK_APP_TOKEN` (Socket Mode, inbound).

**`baseURL`** is cluster-local Ollama for `homelab-ops` and `homelab-reviewer`,
deployed by datahub-local-core (`releases/data/values/ollama.yaml.gotmpl`).
Provider `ollama` needs no credentials, which is why those two carry no
`authRefs`. Core's `extraEgressPorts` already allows egress on 11434.
`homelab-responder` points at OpenRouter instead — see *The oracle runs on
OpenRouter, and the ensemble is the only place a credential fits*.

**`authRefs`** appears on `homelab-responder` only. It is ensemble-level in the
CRD and has no per-persona equivalent, so it is the *ensemble* that is the unit
of credential — which is a second reason the responder is its own ensemble,
alongside the trust boundary it was split on.

**`enabled: true` on all three ensembles.** Ensembles ship disabled in the CRD
("catalog-only"), so a manifest without it deploys but never runs.

**`channelAccessControl`** lives here because a sender id names a person, not the
agent — see *`allowedTriggers` is not access control*.

**`policyRef: permissive`** — see *Why the `permissive` policy*, and note that
`SympoziumPolicy` appears to be declarative-only in v0.10.47, which makes the
whole question probably moot rather than merely settled.

---

# Delivery

## Every report arrived five times, and only one agent sent it

Each `homelab-ops` report landed in Slack as five byte-identical copies in the
same second, from a run that called `send_channel_message` exactly once. The
fan-out is in the event bus: `sympozium.channel.message.send` is a fleet-wide
subject, and each `<instance>-channel-slack` sidecar subscribes with its own
ephemeral JetStream consumer whose only filter is the subject — no queue group,
no per-instance filter. All five received all seven messages published that day
(`curl localhost:8222/jsz?consumers=true` on the NATS monitoring port) and all
five called `chat.postMessage`. The sidecar filters on the *transport* in
`data.channel`, which is why a telegram message never lands in Slack, and never
on the `metadata.instanceName` the envelope hands it.

Nothing scopes it from the channel side. `channelAccessControl` is inbound only;
the controller exposes only fleet-wide `SYMPOZIUM_IMAGE_REGISTRY`/`_TAG`; the
sidecar Deployment declares `replicas: 1` under an `Agent` ownerReference.
**And unbinding the other four does not work either** — the ipc-bridge gates
outbound on the agent's own `channels`, so an unbound persona's
`send_channel_message` answers normally, reports `Succeeded`, and the message is
dropped with `Dropping outbound message to channel not configured on this agent`
(verified against `renovate-reviewer`, 2026-08-23). Delivery and the duplicate
are the same switch: **every persona that reports to a channel costs one copy of
every report in the ensemble.**

The upstream fix is one line — filter on `metadata.instanceName` in the sidecar.

### `deliveryMode: hook` is the default, and it sidesteps the bus

`lifecycle.postRun` runs a container after the agent finishes with the report in
`AGENT_RESULT` and the bot token pulled from a Secret by reference. One
`chat.postMessage`, no event bus, one copy. Egress works because the hook pod
carries no `sympozium.ai/role=agent` label, so `sympozium-agent-deny-all` does
not select it.

The hook runs as an **init** container named `post-<name>` in a
`<run>-postrun-*` pod whose main container is `done` — `kubectl logs` without
`-c` gives you the wrong one.

Three consequences are the point rather than side effects:

- **`send_channel_message` is off every hook-mode allowlist.** Keeping it means
  the model posts *and* is posted for, and worse, the run ends on a tool call —
  which leaves `status.result`, and so `AGENT_RESULT`, empty. Over 24 hours the
  causes of an empty result were `terminal turn had empty text` 60,
  `invalid UTF-8` 2; the model's last act being the posting call was the whole of
  the first number. Take the tool away and the report *is* the final text.
- **`hook.md` names no tool at all.** An earlier draft mentioned the posting tool
  while explaining what it replaced; a 4B model reads a tool name as permission
  to call one.
- **A persona with no `sympozium_delivery` destination gets no hook**, which is
  what keeps `homelab-reviewer` silent by design. The template gates on a
  resolved destination, not merely on the mode.

`deliveryMode: tool` is gone: it cost a duplicate copy of every report per bound
persona and nothing used it. The other mode is **`reply`**, which the responder
uses: a bound persona answering in the thread that asked, through the channel
sidecar. It takes no hook and needs no configured destination — the hook
hardcodes one, and that is how two questions asked in two different channels were
both answered into a third. A `reply` persona carries its own answering contract
instead of a `{{ DELIVERY }}` token, and `templates/ensembles.yaml` fails the
combination. **A `reply` cannot be guarded by a hook**: a gate hook
holds the run's *final output*, while a reply leaves mid-run as a tool call, so
there is nothing left to hold by the time the gate would run. The guard for a
responder has to be in what the tools return.

## `send_channel_message` takes the destination in `chatId`, not `channel`

Cost every scheduled report for two days, then cost two more days after the
obvious fix. The signature:

    channel   the *transport* — slack, telegram, discord. Never a #name.
    chatId    the destination. Nothing else carries it.
    text      the message
    threadId  optional, a Slack thread_ts

With `chatId` unset the tool still answers `Message sent ... (target: owner
(self))` and validates nothing. A scheduled run has no owner, so Slack rejects it
`channel_not_found` — logged **only** in
`kubectl logs -n automation deploy/<persona>-channel-slack`, which logs failures
only, so silence there is the success signal. The run itself ends "Report
delivered successfully", because the model is repeating what the tool told it.

Then naming the argument was not enough. The prompts showed the call as an
indented block of `key: "value"` pairs, and the model reproduced it character for
character: `chatId = " \"#monitoring-ai-alerts\""`, a leading space and two
literal quotes, rejected the same way. **A prompt for a model this size must
never show a value inside syntax the model is also expected to strip.** The
prompts now write arguments bare (`chatId    {{ CHANNEL }}`), say outright that
nothing may be added around a value. `validate.py` used to reject a re-quoted
`{{ CHANNEL }}`, and the same shape for `datasourceUid`/`queryType`/`endTime`;
that check went with the validator, so the rule now lives only in the prompts
themselves. It was deliberately narrow, because PromQL in an indented block
legitimately contains quotes (`ALERTS{alertstate="firing"}`).

Only `homelab-oracle` holds this tool now, and its prompt tells it to leave
`chatId` alone rather than showing a value to copy. Confirmed working in
production: a real run called it with `chatId: "C08S5ACNTPB"`, a channel id.

## The model writes Markdown; the hook speaks Slack

`prompts/delivery/hook.md` used to carry eight lines teaching a 4B model to emit
Slack mrkdwn. It did not hold — `**bold**` and `##` arrived anyway, which is why
the converter already repaired both. Two notations were being asked for and one
was being produced. The prompt now says *write standard Markdown* and nothing
about the channel; `files/deliver-slack.py` owns the whole translation (links to
`<url|text>`, `~~s~~` to `~s~`, `**b**` to `*b*`, headings to bold, rules and
fences dropped). Same reasoning as the facts server: the model writes the one
notation it knows and the conversion is deterministic, testable and identical for
every persona.

**It is Python, and that is half the change** (2026-08-30). A sed pipeline
rewrites Markdown *inside* code spans, so a report quoting `increase(m[1h])` had
the one string its reader would copy corrupted. It is the only code in this
sub-project that runs in production, so it has `tests/test_deliver_slack.py`,
wired into `.github/workflows/test-agents.yaml`, and since the validator was
deleted it is the only Python this sub-project runs in CI. The image is
`python:3.13-alpine` and the script is standard library only: a delivery hook that
needs a `pip install` fails on a network blip. `.helmignore` excludes `/tests/`
and must keep `files/` readable, since the template reads the script at render
time.

**HTML is why the converter exists now.** A real `gitops-auditor` report arrived
as `<font face="monospace"**Drift:** Everything is Synced and Healthy.</font>`,
unclosed tag and all. The trap: `s/<[^>]*>//g` matches from `<font` to the `>` of
the *closing* tag and deletes the sentence between them — the line came out empty,
losing the run's only finding. **Python's `HTMLParser` does exactly the same
thing**, which the test caught on the first run. So `_repair_unclosed_tags` runs
first and hands the parser only tags whose `>` arrives before the next `<`;
`<70%`, `<1h` and `5 < 7` match no tag at all. Do not "simplify" this back to one
pass.

**This applies to hook-mode personas only.** `homelab-oracle` delivers through
the channel sidecar, which runs no converter, so its prompt keeps the
Slack-native rule and enumerates what is banned (`**`, `#`, `|`, fences, HTML,
bold labels standing in for headings) *and* what to write instead — one reading
per line as `airflow 19.0MiB`. **Forbid a shape and the model finds the next
shape; name the shape you want.** Do not "make it consistent" without moving its
delivery too.

## The report names its agent; it never invents a time

Nothing in this fleet returns the current time — verified: the runtime injects no
clock and no MCP server exposes one. So the header carries agent, ensemble and
cadence, the prompts forbid any date or duration not read from a tool result, and
Slack's message stamp is the run time. The same absence is why `endTime` is
pinned to the literal `now`, why `node_boot_time_seconds` became a two-year
uptime, and why a 21-day certificate window was never satisfiable.

---

# Readings, and the prompts that misread them

Everything a persona is told to query was checked against this Prometheus first.
Two traps found that way: Valkey is scraped by a redis exporter so its metrics
are `redis_*` and never `valkey_*`, and node-exporter's SMART series is
`smartmon_temperature_celcius` (upstream typo). A small model cannot recover from
a plausible-but-wrong metric name.

What is instrumented and worth leaning on: **PSI**
(`node_pressure_{cpu,io,memory,irq}_{waiting,stalled}_seconds_total` — how long
tasks were actually blocked), **SMART** and **UPS** via core's textfile collector,
**EDAC** memory-error counters, `kubelet_volume_stats_*` per-PVC fill, and since
2026-08-23 `node_systemd_unit_state` and `node_apt_*`.

**SMART coverage is uneven, and the shape matters more than the headline.** The
sidecar publishes `smartmon_*` on all seven nodes, but only four carry health
data — amd-1 and amd-2 (two NVMe each), orpi-0 (one) and nas (four). On orpi-1/2/3
and amd-2's nine iSCSI volumes every device reports
`smartmon_device_smart_available 0`: SD/eMMC and iSCSI cannot answer a SMART
query at all. That is hardware, not a missing exporter. `network_ups_tools_*`
exists on the NAS alone because that is where the UPS is plugged in.

## A right metric read the wrong way round

`sre_sentinel_system.md` said to query
`kubelet_volume_stats_available_bytes / kubelet_volume_stats_capacity_bytes` and
flag anything above 80%. That ratio is the fraction **free**, so it flagged the
emptiest volumes and could never flag a full one. It shipped that way and ran for
days, calling a 2%-used volume "97-98% capacity — write operations failing".
Measured the same day: nothing in the cluster was above 31% used.

It did more damage than a wrong line. A non-empty *Filling up* section is one of
the change conditions, so the inversion forced a Slack post every run — defeating
the anti-noise rule two sections further down the same prompt.

Two things had to change in the expression:

    100 * (1 - kubelet_volume_stats_available_bytes / kubelet_volume_stats_capacity_bytes)
      * on(namespace, persistentvolumeclaim) group_left(storageclass)
        (kube_persistentvolumeclaim_info{storageclass=~"longhorn|longhorn-no-replica"} > 0)

The `1 -` is the fix. The join is the second half: all five `nfs` PVCs report the
same `capacity_bytes` — 1,926,808,731,648, the share itself — so a per-volume
percentage there is the share's fill repeated per claim, which is how "garage-2 at
99%" reached Slack about an empty share. Only `longhorn` and
`longhorn-no-replica` have a real per-volume capacity, and `storageclass` is a
label on `kube_persistentvolumeclaim_info`, not on the metric.

**A correct metric name is not a correct reading.** Both metrics existed and were
spelled right; nothing had checked the direction of the division or what the
denominator meant per storage class. Encoded so it cannot return: the expression
moved into the facts server, where a test asserts the direction. A regex in
`validate.py` policed the same rule in prompt text for a while and went with it —
the successor is the test, not the regex. Fill expressions now live in the facts
server
(`prometheus.py`), where `used_percent()` cannot be the bare ratio at all.

`sre-sentinel` spent days storing runs asserting 96-99% fill; fixing the prompt
does not remove those, so its seeds carry an explicit correction telling it to
distrust its own fill history before 2026-08-23. See
[Wiping a persona's memory](README.md#wiping-a-personas-memory) for the
alternative.

### A cumulative counter is not a state, and the suffix will not tell you which

`db_steward_system.md` called `cnpg_pg_stat_archiver_failed_count` "the most
important number you look at" and never said it was a counter. A cluster that had
two failures once and archived perfectly ever since reports `2` forever, and
paired with a hard rule that a failing archiver is CRITICAL that is a permanent
CRITICAL — posted to `#monitoring-ai-health` twice. Measured 2026-08-24 while the
agent called recovery "silently broken":

    cnpg_pg_stat_archiver_failed_count                  2
    increase(cnpg_pg_stat_archiver_failed_count[24h])   0       <- no failure in a day
    time() - cnpg_pg_stat_archiver_last_failed_time     470508  <- 5.4 days ago
    time() - cnpg_pg_stat_archiver_last_archived_time   95      <- 95 seconds ago

The persona's own memory seed said "a *rising* failed_count" and lost, because
the prompt is what names the tool call. Prompts now give both expressions
literally with a hard rule that a non-zero lifetime total and a zero increase is
a **healthy** archiver the report should say so about.

Two traps found fixing it:

- **A `_total` suffix does not mean counter.** `cnpg_backends_total` and
  `cnpg_backends_waiting_total` are gauges; the first draft of the validator
  keyed on the suffix and immediately failed a correct prompt. It then held an
  explicit `CUMULATIVE_COUNTERS` set read off Prometheus's metadata API, and that
  set now lives as a test in `agents/mcp/tests/`. Read the type from the metadata
  API, never from the name.
- **The model drops the wrapper.** Given `increase(m[1h])` it sent `m[1h]` and
  labelled the raw counter as the increase. Prompts state that an `expr` is the
  whole line, function call included — the `chatId` lesson in a new place. Prose
  did not work: `endpoint-warden` said "take the rate, not the raw counter" twice
  while handing the model bare metric names.

### Right metrics, wrong rows: node-exporter has no node name

The 2026-08-24 13:25 Fleet table read plausibly and was wrong in five places at
once: four rows said `unavailable` for figures that were available, the NAS was
given amd-1's disk percentage, every uptime was wrong by two orders of magnitude,
and three ARM nodes with 5 pending security updates were reported as having none.
The single Finding — "CPU waiting pressure on amd-1 peaked at 52.7%" — was 0.47%
in reality; the loaded machines were orpi-1/2/3 at 21-30%.

**No `node_*` series in this Prometheus carries a machine name.** They are keyed
by `instance`, an IP and port. The only hostname anywhere is the `nodename` label
on `node_uname_info`. The prompt demanded a per-node table and never said how to
get from a series to a node, so the model improvised — `by (node)`, which is
neither valid PromQL nor an existing label, written on four different metrics —
and invented `node_uptime_seconds` before falling back to
`node_boot_time_seconds`, an absolute epoch reported as a duration of decades.

The fix is the one this file keeps arriving at: **write the literal expression,
including the join.**

    max by (nodename) (<inner> * on(instance) group_left(nodename) node_uname_info)

`by_nodename()` in the facts server now owns it and cannot drop it.

Two things generalise. **`unavailable` needs a definition or it absorbs every
bug** — it was introduced so a missing metric could be stated rather than
invented, and then silently absorbed a broken join. It now means *the query gave
no value for this node*, never *this node is missing from an answer that did
arrive*; scattered `unavailable`s almost always mean the join was dropped. And
the second word matters as much: `n/a` means *this machine has no such sensor*,
which is hardware and not a finding. **And `node_hwmon_temp_celsius` covers all
seven nodes while `smartmon_temperature_celcius` covers four** — the prompt had
both without saying which was the Temp column, so the table inherited SMART's
coverage gap for no reason.

## Reading the uid was worse than pinning it

`grafana_list_datasources` returns all three datasources this Grafana serves:
Prometheus at the literal uid `prometheus`, Alertmanager at `alertmanager`, and
Loki at the hex string `P8E80F9AEF21F6940`. Only one of those *looks* like a uid.
A 4B model takes the hex string for the real identifier and the bare word for a
placeholder it was supposed to resolve, and sends every PromQL query to Loki —
which answers `404 page not found` for every metric, against a prompt that stated
the correct value two paragraphs earlier.

**A discovery tool that returns several plausible answers is a liability at this
model size.** The agent has to choose, a wrong choice fails silently, and the
failure looks like the thing being discovered is broken. Prefer a pinned literal
plus a loud failure: if the uid ever changes the agent reports every metric
unavailable, which is loud. The tool is in `BANNED_TOOLS`, and no persona wires
the grafana server at all now — the facts server queries Prometheus and Loki
directly, so no uid exists on either path to get wrong.

### It then invented the numbers rather than report none

The 2026-08-24 04:30 run of `endpoint-warden` is the part that cost trust. With
every Prometheus query 404ing, the mandated Fleet table still required seven
columns per node, so the model filled the disk column from the one tool that had
answered — `k8s_nodes_top` — relabelling memory percentages as disk and calling a
5%-full control-plane disk "79% disk fill (CRITICAL)". It then emitted the whole
report twice with different numbers. The standing rule "never report a number you
did not retrieve" lost to the format rule demanding a value in every column.

**A format is only safe if it makes absence expressible.** A column with no
metric is the literal `unavailable`, a row of seven of those is a legitimate row,
every figure must come from the metric named for it, and the sections are emitted
exactly once.

### The Fleet table is gone: the copy was the defect (2026-08-25)

Those changes made the table *correct to produce* and left it a table the model
still had to retype. Two probe runs against a fixed facts server that handed over
every reading correctly:

| what the tool printed                   | what the report said                   |
| --------------------------------------- | -------------------------------------- |
| `amd-1 ... smart 47.0 ... uptime 8.1d`  | `amd-1 ... smart n/a`                  |
| `orpi-0 ... smart 38.0 ... uptime 8.1d` | `orpi-0 ... smart n/a ... uptime 38.0` |
| `orpi-3 ... 6.1.115`                    | `6.1.1.115`                            |
| `nas: runtime 13m`                      | `31 minute runtime`                    |

orpi-0's SMART reading landed one column left, and both rows gained an `n/a` —
worse than a typo, because `n/a` is a *defined* word that retires a real reading
by fiat. One run invented a machine, `asfpm-2`.

Prose could not hold it: the prompt already said "the table is correct as
printed", "do not recompute a column" and "in the column it was printed under",
and the delivery contract already said **no tables** because the destination
cannot render one. So the copy is gone rather than better policed. **Fleet** is
now one line — how many machines answered, how many are clean, which are not —
and the table stays in the tool result, where it is aligned and where nothing can
shift it. The general rule went into `prompts/delivery/hook.md` so it reaches
every persona now and later: *never retype a tool's table or a row of one; write
only the figures you are making a claim about, next to the claim.* A figure
attached to a claim is one a reader can check.

Both halves of this pair are the same shape as the caveat below: **the model
being asked to carry data it has no reason to touch.** The cure each time was to
stop routing it through the model.

## A name search answers "what is it called", never "what does it do"

Asked in Slack for "the status of the stream and S3 services" on 2026-08-31, the
oracle held no tool for either. It fell through to `facts_find_object` and
returned `datahub-local-core-data-s3-gdrive` — an unrelated Service that merely
has `s3` in its name — while reporting that no stream service could be found, on
a cluster running a three-broker Redpanda.

Neither answer was a lookup failure. Both calls did exactly what they are built
to do; a name search matched names. The gap is that **the two services are not
named for what they do** — S3 here is Garage, streaming is Redpanda — and no
amount of better resolving fixes a vocabulary mismatch. The failure mode is
worse than a plain "not found", because the S3 half returned a real object with a
ready pod and an IngressRoute, which reads as a confident correct answer.

So the fix is routing, not search. The prompt now maps the words a person
actually uses — S3, object storage, bucket, stream, Kafka, topic, partition,
broker, retention — onto the three fact tools, and says outright that
`facts_find_object` is the wrong tool for those words. Both questions are in
`evals/questions.yaml` alongside the bucket-size and retention questions that
have the same shape. The general rule: before adding a tool, ask what a person
would *call* the thing it reads. A correct tool the model never routes to is the
same outcome as no tool at all.

## A memory seed containing `: ` is not a string

Adding the seed above failed the Ensemble outright, and only at the last check
that could see it. A seed is a bare YAML list item, so one containing a colon and
a space parses as a **mapping** rather than as text. The file is still valid
YAML, so `validate.py` passed and `helm template` rendered; the webhook then
refused the object with

    strict decoding error: unknown field
    spec.agentConfigs[0].memory.seeds[3].<the first half of the sentence>

Only `kubectl apply --dry-run=server` shows this, which is the standing reason
this repo runs one before committing rather than trusting a render. The seed is
rewritten with ` - ` instead of `: `. A three-line check in `validate.py`
rejected any seed that did not parse as a string; it went with the validator, so
`--dry-run=server` is once again the only thing that sees this class — which is
the standing reason to run one. Note what made it dangerous: every layer that could have
caught it was *satisfied*, because a mapping is a perfectly good YAML value. Any
schema-free field written as free text has this trap.

## A permanent finding is a bug in the prompt, not a problem in the fleet

The reports flagged `datahublocal-orpi-0` on `7.1.2-edge-rockchip64` against
orpi-1/2/3 on `6.1.115-vendor-rk35xx` as kernel drift, every run, for days. It is
not drift — it is four hardware classes on four kernel trees:

| node(s)                | hardware                 | kernel                             |
| ---------------------- | ------------------------ | ---------------------------------- |
| orpi-0                 | Orange Pi 4 LTS (RK3399) | `7.1.2-edge-rockchip64`            |
| orpi-1, orpi-2, orpi-3 | Orange Pi 5B (RK3588)    | `6.1.115-vendor-rk35xx`            |
| amd-1, amd-2           | amd64 / Debian trixie    | `6.12.96` / `6.12.101+deb13-amd64` |
| nas                    | Intel N305 / TrueNAS     | `6.12.15-production+truenas`       |

The seed said "the odd one out is the finding", which is true only within a
class. Different SoC families cannot converge, so the finding could never be
actioned and could never clear — and a non-empty findings section is a change
condition that forces a post. Kernels are compared within a hardware class only,
which the facts server derives at query time (kernel flavour plus architecture);
the sole comparable pair is amd-1 against amd-2, and a class of one can never be
the odd one out.

Same class of bug elsewhere: `db-steward`'s Valkey section read "Memory max:
reported as 0 bytes — unable to determine actual limit" on every run, because this
Valkey has no `maxmemory` set and the container carries no memory limit either, so
"compare used against max" could never be satisfied. It now reads
`redis_memory_used_bytes` with its trend and `increase(redis_evicted_keys_total[1h])`
— evictions being the direct measurement of what a ceiling would have warned
about — and says outright that there is no percentage to compute.

**Check that a rule you give a persona is one the fleet can actually satisfy.**

### The caveat then ate the finding it sat next to (2026-08-25)

Moving the comparison into `facts_node_fleet` made the *reading* right and the
*conclusion* wrong. The section printed the real pair —
`deb13-amd64/x86_64: DRIFT within class - amd-1 behind` — and then closed with a
paragraph explaining that nodes in different classes can never converge "so a
version difference between them is not drift and can never be actioned". A probe
attached that sentence to the DRIFT line directly above and dismissed the one
genuinely actionable finding in the fleet. Replayed at temperature 0 across three
seeds, the old wording dismissed it twice and dropped it entirely once.

Two structural changes: **the scope note leads the section instead of closing
it** (a model summarising a block takes the last line as the conclusion, so a
caveat can never be last) and it no longer contains the word *actioned* at all;
and **every line carries its own verdict** — the DRIFT line ends "this is a real
finding and belongs in your report". All three seeds then reported it.

**Prose adjacent to a figure gets absorbed into it.** If a sentence qualifies some
lines of a section and not others, put it on the lines it governs or above all of
them. `tests/homelab_facts/test_tools.py::TestKernelSection` pins both halves.

## A version string is a quantity a 4B model will invent

Asked about kernels, `homelab-oracle` answered that amd-1 was "6 months behind"
amd-2 and that amd-2 was "15 minor versions" ahead. The readings were perfect —
`6.12.96` and `6.12.101`, correctly joined and grouped. The truth is five patch
releases inside one series, and a kernel string carries no date at all.

**The facts server fixed the readings, not the arithmetic on top of them.**
Handing over two correct numbers and letting the model state the relation puts
the relation back in the model's hands. So `fleet.version_gap()` computes the
distance and states it in the only unit the readings support ("amd-1 is 5 patch
releases behind, both on 6.12"), followed by a line saying no release date is
knowable and the gap is not to be restated in another unit. `tests/test_fleet.py`
asserts the word "minor" cannot appear for it.

**If a report will compare two readings, compare them in code. A derived quantity
is a reading too.**

## An instruction to investigate needs a budget and an exit

Four personas, one shape, four times.

- **`sre-sentinel`, 2026-08-24.** Read a real new `TargetDown{job="longhorn-backend"}`
  and set out to root-cause it as instructed. Five lookups: a scrape-job name
  passed as a pod name, `namespace` written as a term inside `labelSelector`, the
  same call again byte-for-byte, `app=longhorn` when the real selector is
  `app=longhorn-manager`. Five empty results, then a turn with neither text nor a
  tool call. `Succeeded`, `status.result` null, the alert unreported.
- **`db-steward`, the same day.** Seven of fourteen calls on one CloudNativePG
  `Cluster` that a bare `apiVersion` + `kind` + `namespace` returns: `name` as a
  label, `namespace` inside `labelSelector` again, two contradictory equalities on
  one key, one call repeated byte-for-byte. The day's Postgres and Valkey
  readings were already in hand and none were written down.
- **`homelab-oracle`, twice.** Eight calls concluding a running grafana did not
  exist, and five on `i want to know the polaris database` before reaching for the
  out-of-scope refusal.

**A model this size does not conclude on its own that it has learned enough to
start writing.** Prompts grant *at most 3 lookups* per subject and name the
outcome when they yield nothing — `cause not determined` or `not found`, stated to
be a legitimate finding. Both halves are load-bearing: a cap with no escape hatch
relocates the silence, exactly as a mandatory table produced invented numbers
until absence became expressible.

Two corrections that came out of the repeats:

- **Scope the fix to the tool, not the persona.** The first fix said
  "root-cause" in one prompt and nothing in the other. The rules now attach to any
  prompt naming a lookup tool.
- **`service-janitor` then lost all of it in a prompt rewrite** — see *What a
  prompt review finds that a run does not*. Nothing reads every prompt any more,
  so if it regresses a third time the guard has to be a new test rather than a
  line added back to a validator.

## What a prompt review finds that a run does not

Reading all seven prompts against the tools they actually call, 2026-08-29. Every
finding was the same shape: the prompt and the server disagreed, and nothing
failed.

- **A tool the prompt never names is a tool the model has to invent a use for.**
  `endpoint-warden` was told "at most 3 calls per machine" without naming a single
  tool to make them with; `renovate-reviewer` was told to "fetch release notes"
  while `fetch_url` — the only tool that can — appeared nowhere in its prompt, and
  to "check ArgoCD app health" without `argocd_list_applications`. That is the
  `grafana_list_datasources` failure inverted: there the model was given a choice
  and picked wrong, here it is given a job and no name at all. Both now name the
  tool and the literal call shape.
- **A section the server computes and the report has no room for is a dropped
  finding.** `facts_alerts_snapshot` emits `## Resolved since last run`, and
  `sre-sentinel`'s four-section format had nowhere to put it — so an alert clearing
  was computed every run for nothing, and this file's own description of the
  persona ("new / still firing / resolved") had quietly stopped being true. Now a
  fifth section. The mirror of it: `endpoint-warden`'s **Findings** listed five of
  the note kinds `_notes()` prints, and a 4B model reads a partial enumeration as
  the complete set — so an uncorrectable-memory-error line, the most serious thing
  that tool emits, was not in the list of things to report. It now says every line
  the tool printed.
- **Guards do not survive a rewrite.** `service-janitor` had gained the lookup
  budget, the no-repeat rule and the `cause not determined` exit alongside
  `db-steward`, and had none of them a fortnight later — only the
  `namespace`-is-its-own-argument half survived the rewrite to short prompts. The
  check that would have caught it went too, with the prose validators the facts
  server replaced. The regexes deserved to go; this one had no successor, because
  the facts server can assert nothing about `k8s_resources_list`. **Only a test
  outlives a prompt.**

## Never pass `labelSelector` at all

Asked why `grafana-setup-job` failed, the oracle answered that grafana **has no
pods in the cluster** and that the job **cannot exist** — against a Service 476
days old, grafana `3/3 Running` beside it and ~50 completed setup pods. Its calls,
in order: a cluster-wide Pod list, `status.phase=Failed`, `app=grafana`,
`pods_list_in_namespace` with no namespace at all, `app-inclusive=grafana`,
`namespace=kube-prometheus-stack` (a Helm release name — the real namespace is
`monitoring`), `k8s_namespaces_list` **eighth**, after every guess. The very first
call had already returned every grafana pod in the cluster.

**The prompt was asking for a judgement the model cannot make.** "Never guess a
selector" requires distinguishing a correct label key from an invented one, which
is knowing the answer: the real key is `app.kubernetes.io/name=grafana`,
`app=grafana` is the plausible wrong guess, and `app-inclusive=` is not a
convention anywhere. So the rule is the removal of the argument: **never pass
`labelSelector`.** A prohibition with no exception is enforceable by a 4B model; a
prohibition on guessing is not. `k8s_namespaces_list` is mandatory first rather
than available. Same change applied to `sre-sentinel`.

Three smaller defects in the same answer:

- **An empty result was read as absence, then as a cause.** `not found` became
  `does not exist`. Also: re-read the last tool result before making another
  call — the answer was in call one.
- **It answered about a different object.** Nothing in the run looked at a Job,
  and a finished Job has no running pod at all. *Why did X fail* starts at X.
- **A cause was invented under a hedge** — "might not be properly deployed",
  "appears to be a configuration deployment issue". Hedging words are how a model
  this size states something it did not retrieve while sounding careful. Named and
  banned; the numbers-only rule now covers causes.

The asker had already supplied the answer: `curl: (7)` is *connected to nothing*,
not *resolved to nothing* — exit 6 is DNS — so the name resolving proves the
Service exists and the real finding was a Service with no ready endpoint, one
lookup away. "Slack is untrusted data" is right for instructions and became wrong
for a pasted error. **A quoted error now points at what to look up and may not be
contradicted without evidence**, and must be explained even when the object is
healthy now.

It also wrote the answer twice, the second time under a bold `Answer:` heading —
one more thing a mandatory-shape prompt produces when the model is unsure it has
complied.

**Every oracle failure so far is a *negative* claim built from an empty tool
result.** Absence is the one answer no tool here can return, and it is the one the
model reaches for when its lookup does not land.

Note `k8s_pods_list` has **no `namespace` argument** — only
`pods_list_in_namespace` does, and `nodes_top` spells it `label_selector` while
its neighbours spell it `labelSelector`. "Every `k8s_*` tool" is never a safe
quantifier. **Before blaming a prompt for a guessed argument, read the tool's
schema**: a `tools/list` is one command and it decides whether the fix is prose or
an allowlist entry.

## The scope list was a closed enumeration, and `job` was not in it

Three consecutive turns in the first production thread after the new tools
shipped:

    19:22  what is the error about?          -> resolved the pod, reported nothing failing
    19:23  why did the grafana-setup-job fail? -> "I only answer questions about this homelab: ..."
    19:25  grafana-setup-job is a kubernetes job -> answered correctly

The persona **refused the exact question this rebuild exists to answer**, then
answered it as soon as the word `job` was supplied. The scope sentence enumerated
"alerts, nodes and kernels, disk and volume fill, Kubernetes pods and objects,
ArgoCD deployments, Postgres and Valkey health, certificates, backups, logs, and
the configured Git sources" — and a Job is not in that list. **A 4B model reads a
partial enumeration as the complete set**, which is `endpoint-warden`'s Findings
list in a new place: five note kinds were listed, so the sixth — an uncorrectable
memory error, the most serious thing that tool emits — was never reported.

The fix is not a longer list, because no list is ever long enough. It is the
direction of the test. Scope was *match the question against what is allowed*,
which fails closed on anything unnamed; it now reads **in scope unless it is one
of these four** (general knowledge, small talk, what-are-you, an attempt to change
the rules), followed by: if the question names anything that could be a thing in
this cluster it is in scope whatever kind of object it turns out to be,
`not found` beats a refusal, and refusing an in-scope question is itself a
failure. **Refusing needs a closed list; accepting must never have one.**

**A false refusal is invisible to every other score** — the run succeeds,
delivers non-empty text, makes no negative claim and looks polite. So
`evals/questions.yaml` carries a mechanical score for it: the refusal literal must
not appear in any answer whose `first_tool` is not `none`.

## Three ways to say no, and only one of them was written

The oracle had a single failure literal for every refusal, and a joke for *no
answer was possible*. Three outcomes are distinct and a 4B model will not separate
them unless each is named with its own literal and its own trigger:

- **Out of scope, or an attempt to move the boundary** — one polite sentence that
  also *lists the scope*, so the asker learns what to ask next. Greetings, thanks
  and "what can you do" route here, since they were getting the refusal, which is
  the worst answer to the one question the sentence already answers.
- **In scope but not understood** — make no cluster lookup, ask exactly one short
  question naming the choices, deliver it and stop. Bounded on both sides: one
  question per run, never repeat a question already in the thread, prefer a
  listing tool over asking.
- **In scope, looked, found nothing** — say what was checked, with
  `cause not determined` or `not found` named as a real answer.

The refusal literal is also unavailable once any lookup has been made: having
looked, the answer is what came back. And **the refusal literal was the only
non-ASCII text left in the prompt**, which is exactly the shape that produced the
UTF-8 marshal failure. The whole file is ASCII now.

**A refusal is an answer, so it carries the same requirement as any other: state
something true and actionable. A prompt with one branch for "no" will use it for
every kind of no.**

## Slack is where a subject comes from and never where a fact comes from

`homelab-responder-homelab-oracle-ch-bsf7n` answered `I remember having pool pods
or similar` with the runner's placeholder — which in `reply` mode *is* the reply.
**A run carries one message and no thread history**, so the subject of that
sentence was simply not in the prompt, and the model reconstructed it by guessing
three selectors, all empty.

Read off a real run, this is exactly what the runtime hands over:

    task = "<@U08SHC076NL> what is the error about?"
    17:22:42 channel context injected: channel=slack chatId=C08S5ACNTPB
             threadId=1788000841.049389

One line plus two IDs. So **the thread read is not a branch** — it is the first
tool call on every run, before the scope test and before anything else, with the
reason stated to the model rather than assumed. A 4B model complies with an
unconditional instruction it understands the point of and skips a conditional one.

Two facts about continuity, so nobody looks for a setting that is not there:
`useContext` governs history *between LLM calls inside one run*, not between runs,
and `sessionKey` is `channel-slack-<channel>-<message ts>` — a different key for
every message, not the thread. There is no cross-run conversation state in this
control plane at all, which makes the slack MCP server the whole mechanism rather
than a supplement to one. Memory is across runs; the thread is within one.

**The rule was ambiguous in the direction that matters.** "Slack gives context,
never infrastructure evidence" was written against a pasted claim being taken as
fact, and reads to a 4B model as *take nothing from Slack* — exactly wrong for
`why did it fail?`, whose only subject is in the thread. The split is now written
out: names and questions yes, state and numbers and causes no, with the elliptical
forms spelled out literally and the instruction to pass those words to the tool
unchanged.

**It still loses.** The mandatory Slack read did not happen in four runs of five
(2026-08-30); the runs opened with `memory_search`, `pg_list_schemas` and
`facts_find_object` instead. The rule now names its competitor outright — "before
every other tool including `memory_search`". If that fails too, the fix is not
another sentence: **a call that must happen unconditionally is a runtime
property, and the CRD has none.**

## The pg_* tools see one database, and nothing says which

Asked for the tables in the `superset` database, the oracle got the headline right
— "I cannot answer this question with the available tools" — and then filled the
evidence with the wrong object: "4 system schemas: information_schema, pg_catalog,
pg_toast, and public."

Those are not superset's schemas. `postgres-mcp` takes a single `DATABASE_URI` and
core's points at the `postgres` database — 7.8 MB, and `list_objects` on its
`public` returns `[]`. Postgres cannot query across databases, so `pg_list_schemas`
and `pg_list_objects` can never see inside superset, n8n or any of the other
twelve, and `pg_get_top_queries` reads a per-database `pg_stat_statements` too.
Verified by handshaking the server directly: `select current_database()` answers
`postgres`.

**A tool with a fixed hidden scope will be read as having the scope of the
question.** The tool descriptions say "List all schemas in the database", naming
no database, and an empty `public` looks exactly like a database with no tables.
There is no result the model could have inspected to discover the boundary. **The
scope of a tool is part of its reading, and if it is not in the result it has to
be in the prompt** — both prompts now carry it as a literal, including
`db_steward_system.md`, where `pg_get_top_queries` had been quietly returning the
empty database's query stats as "query-level detail" for the whole fleet.

## The oracle offered SQL it did not have

Asked for the size of each schema on 2026-08-30, the oracle replied with its own
plan — "Let me run a SQL query that calculates the total size of each schema" —
and stopped, then closed the follow-up with "I can run that if you'd like". It
never could. `pg_execute_sql` was in its `toolsAllow`, its `toolPolicy.allow` and
its prompt, and core's catalog MCPServer carries `spec.toolsDeny: [execute_sql]`
(generation 2 — changed at some point from `execute_write_query`, which is not a
tool that server has, to the one that is). **A catalog deny stops *discovery*, so
the bridge never sees the tool and a persona allowlist has nothing to select.**
The only trace is one line in the run log:

    Discovered 3 tools from "...mcp-postgres"

against four allowlisted names. The render, the validator, `MCPServer.status.ready`
and the run itself were all green.

Three changes, because the shape will recur:

- The tool is gone from the persona and the prompt. What a persona lists is now
  what it actually holds.
- `validate.py` carried `CATALOG_DENIED`, mirroring `spec.toolsDeny` on each
  catalog MCPServer, and failed an allowlist entry naming one. That mirror is why
  the validator went: it is a second copy of a file we do not own, and the
  argument for keeping it — loud drift against a silent bug — stopped holding once
  the copy needed re-reading after every image bump. Read the live `toolsDeny`
  before adding an allowlist entry. Same
  trade as `MCP_SERVERS` and `SKILLS` beside it. Re-derive with
  `kubectl -n automation get mcpservers -o json | jq '.items[] | select(.spec.toolsDeny)'`.
- The prompt says a tool it was not given does not exist for it, and that it may
  never offer a query, a check or a next step. **A capability named in a prompt is
  a promise the model makes on your behalf**, and it cannot discover the promise
  is empty: an unregistered tool is not an error it sees, it is a tool it never
  gets the chance to call.

The no-offer rule then had to move. Written in the middle of the prompt, the reply
still ended "Let me know if you want to see that breakdown instead". It now lives
in the final paragraph, the one that governs writing, and says why: an offer is a
promise there is no later turn to keep. **A rule about what to write belongs in
the paragraph about writing. Position is not decoration at this model size.**

---

# Tools, servers and what actually bounds them

## The tool schemas, not the report, are what fills the context

`toolPolicy` filters at the LLM request. It does not stop a tool being
*registered*, and every registered tool's JSON schema is injected into the prompt
on every call. The runner says so plainly on a run with nine allowed tools:

    tools enabled: 60 tool(s) registered

Sixty, because the grafana MCP server alone exposes 66 and the persona only
denied 14. Measured with two throwaway `AgentRun`s differing in nothing but
`toolPolicy`: **40,500 first-call input tokens without it, 4,095 with it.** At the
time Ollama's window was 32768, so 40,500 did not fit — and nothing errors: the
request is truncated from the front, which is where the persona, the report
format and the delivery instructions live. That is the whole explanation for
`(Agent completed its task via tool calls but did not produce a final text
summary.)` on the web path. The agent was not ignoring its instructions; it never
received them.

The fix is `toolsAllow` on each `mcpServers` entry, which filters at the server
and bounds what is registered at all. Every persona pins it to exactly the tools
its `toolPolicy.allow` names, unprefixed. Drift in either direction is now
unguarded and silent — a tool in `toolsAllow` but not `toolPolicy.allow` is prompt
weight the model can never use, and the reverse never reaches the agent.

**The window was then raised to 65536, which does not retire the rule.** 40,500
now fits, so the overflow is gone. The rule survives for three reasons that have
nothing to do with the window's size:

- At ~670 tokens per schema, sixty tools is ~40k of prompt on *every* call in the
  loop, not once — the difference between 433,866 input tokens for a 16-call web
  run and ~160,000 for a comparable scheduled one, all serialised through one GPU.
- A 4B model chooses badly among sixty tools. A registered-but-unallowlisted tool
  is described to the model and then refused, which is the worst of both.
- Headroom is what absorbs a large Prometheus result mid-run.

**On a local model the tool surface is a prompt budget before it is a permissions
question, and the budget is spent on every call.**

## A 16 KB tool result ends the run with no report

`gitops-auditor` delivered "The run finished but produced no text" at 20:05 on
2026-08-24: four tool calls, `tool_result_bytes=24126`, then
`terminal turn had empty text`. The run four hours earlier made five calls for
8,483 bytes and wrote a normal report. The difference is one tool,
`argocd_get_application_resource_tree`, worth roughly 16 KB on its own.

Not a context overflow — cumulative input was 25,423 tokens against 65,536. A 4B
model simply stops producing a final turn when one answer is that large.

The tool is in `BANNED_TOOLS` and the prompt says why rather than leaving a silent
gap. **A tool whose answer has no natural bound is a liability in the same way a
tool returning several plausible identifiers is** — prefer the one with a bounded
answer, and if there is no alternative, bound it in the arguments. Every facts
tool declares a byte budget, truncates by whole lines and says that it did; a full
nine-reading sweep is ~14.7 KB and no single answer exceeds 4 KB.

## Tool names are not guessable

Every tool name here was read off the running MCP servers with a `tools/list`
call, never inferred, because guessing silently disarms the thing you were
configuring. Core's own catalog has had this bug twice: its k8s server denied
`delete_resource`, `create_resource` and `update_resource`, none of which exist
(the real names are `resources_create_or_update`, `resources_delete`,
`resources_scale`, `pods_delete`, `pods_exec`, `pods_run` — fixed 2026-08-23), and
its postgres server denied `execute_write_query`, which that server has never had.
**A deny that matches nothing reads as protection and is not any.**

The three servers with *no* catalog denies — github, argocd, grafana — are the
same exposure with none of the noise: `mcp-github` publishes `merge_pull_request`
and `push_files`, `mcp-grafana` publishes `grafana_api_request`, which reaches the
whole Grafana API. Harmless only because of what `projects/` allows. Re-check after
image bumps; every MCP image in the catalog is pinned `:latest`.

**A whole *server* fails the same silent way.** Core's `mcp-k8s` was the one
MCPServer declared `transportType: http`, the discovery bridge asked for the
service root, and `kubernetes-mcp-server` serves `/mcp` — so it 404'd and every
`k8s_*` tool was missing from every persona from its creation until 2026-08-23,
with `MCPServer.status.ready` reporting `true` throughout, because that tracks the
Deployment and not a `tools/list`. **Read
`kubectl logs <run-pod> -c mcp-discover` after any transport or image change**; it
prints per-server tool counts, and a whole server failing is otherwise invisible.
The caveat that remains: `spec.deployment` is now null while the Deployment serving
that URL is still owned by the MCPServer CR, so deleting and recreating the CR
cascade-deletes the Deployment and never rebuilds it.

**And the same silence covers a stale image.** `Publish MCP Image` ran
13:33:17 -> 13:36:18 while the chart applied at 13:33:42, so the pod pulled `:main`
as it existed two and a half minutes earlier: `imagePullPolicy: Always` pulls when
a pod is *created*. The deployment sat on a nine-tool manifest with
`status.ready: true`, the persona's `toolsAllow` named a tool the server did not
expose, and neither end failed. After any change to `agents/mcp/`, wait for the
build, then
`kubectl -n automation rollout restart deploy/datahub-local-ai-mcp-homelab-facts`,
and confirm with a `tools/list` against the pod rather than with an agent run.

## Three weeks of "no permissions" was a repo name the model shortened

`renovate-reviewer` reported `Not Found` for every repository on every run since
it was installed, and read that as a token failure. The Loki logs show the calls:

    github_list_pull_requests owner=datahub-local repo=bootstrap
    github_list_pull_requests owner=datahub-local repo=core
    github_list_pull_requests owner=datahub-local repo=ai

The repositories are `datahub-local/datahub-local-bootstrap`, `-core` and `-ai`,
all public and readable with no token. The prompt named them correctly but never
said which half was the owner, so the model split the slug at the hyphen. Three
real open Renovate PRs went unreviewed while the reports said there were none.

- **A tool argument the prompt does not state is one the model will derive, and it
  will derive it wrongly and confidently.** Name the literal value; the prompt now
  writes owner and repo as separate labelled values and says the `datahub-local-`
  prefix is part of the repo name.
- **`Not Found` reads as "you lack access", so the model stops.** GitHub answers
  404 for a missing repo and a private one alike. The prompt states what the 404
  means here and grants one retry.
- **Then the wrong conclusion made itself permanent.** Runs 2 and 3 auto-stored
  "All GitHub tools fail across bootstrap, core, and ai repos"; run 4 auto-injected
  it, cited it as evidence, and gave up after six calls in 23 seconds against a
  budget of 100. **A false finding in memory is not a stale fact, it is an
  instruction not to look.** Auto-stored memory is written unconditionally by the
  runner, so nothing filters a failure narrative out of it. Correcting the prompt
  alone leaves the poisoned entry being injected every run — the memory PVC has to
  be cleared too.

## One turn, three write calls, two contradicting verdicts

`renovate-reviewer` posted two comments on datahub-local-core#216 thirty-six
seconds apart in a single run: `REVIEW NEEDED ... pending CI status`, then
`SAFE TO MERGE`. Both are still on the PR. The prompt already said "Post one
`github_add_issue_comment`" and "One comment per PR per run".

**This model emits several tool calls per turn.** Its 23 calls were
`list_pull_requests` x3, `get_pull_request_files` x2, `get_pull_request_status` x2,
`argocd_list_applications` x2, `get_file_contents` x2, `get_commits` x2,
`fetch_url` x2, `add_issue_comment` x3. On read tools that is waste; on the one
write tool in the fleet it is a duplicate comment on a live PR.

The prompt now separates the phases rather than restating the cap — every read for
every repo finishes before `github_add_issue_comment` is called at all, and a PR
already commented on this run is finished. That removes the state the model has to
track. It is still prose, and prose is what lost here: **the durable fix is a write
guard the model cannot talk its way past** — an idempotency key, or a wrapper that
refuses a second comment per PR per run. Until it exists, read the PRs after a
reviewer run; the failure is silent (three calls, `Succeeded`, 1,415 bytes of
result).

## The facts server: code gathers, the model writes

`agents/mcp/` exists because **every failure in this fleet was a tool-loop failure,
not a writing failure.** Each incident above added a paragraph to a prompt and a
regex to `validate.py`, and it did not converge: prompts reached 6–12 KB and
roughly 600 validator lines were policing English. Both are gone — prompts are
4–6 KB, the surviving checks are `agents/mcp/tests/` assertions about the
expression the server sends, and the validator was deleted outright, because the
method moved into code.
The design lives in `agents/mcp/README.md`; four properties are structural rather
than instructed, and each retires a class of report that reached Slack: a wrong
query is not expressible, absence is a value with a definition, every answer is
bounded in code, and trends are measured in the server. Nothing about the homelab
is written down — node names, hardware classes and sensor coverage are derived at
query time, because a stale node list produces the exact failure the server exists
to prevent.

The tools do **not** replace reach; the win is budget reallocation. Mandatory
readings drop from eight-plus calls to one or two, leaving the iteration budget for
real investigation.

### The chain after the name

`find_object(term)` exists because **nobody types an exact name.** A person types
`grafana`; the objects are `datahub-local-core-kube-prometheus-stack-grafana` in
`monitoring` and 45 pods called `e-monitoring-grafana-job-setup<hash>-postsync-*`.
No prompt wording closes that gap — the model is being asked to produce a string it
has never seen. One free-text argument, matched exact, then substring, then **every
word**; `grafana-setup-job` appears nowhere in this cluster and all three of its
words appear in the real pod name. It returns the namespace rather than asking for
one, names the kinds it searched, states that not-matched is not proof of absence,
and reports Service endpoints in the same call.

`why_failed`, `logs` and `endpoints` run the chain *after* the name — object, pods,
containers, events, log tail — which is four calls of exact arguments in a fixed
order and the step every failed run in this fleet got wrong. Three decisions inside
them:

- **A pod is reached from its owner, never from a label.** A Job's pods come from
  `ownerReferences`, a Deployment's and a Service's from that object's own
  `spec.selector`. No label key originates in the model or in this repository.
- **A crash-looping container is not running, so its current log is empty.**
  `_pick_container` returns `previous=True` for anything in `_FATAL_WAITING` or
  with a non-zero exit. Reading the wrong instance returns nothing, and nothing
  reads as *it logged nothing*.
- **"Nothing here is failing right now" is one of the verdicts.** A format that
  demands a fault is how invented ones get written.

Verified on the incident's own question: `why_failed` on `grafana setup job`
returns the Job, its one pod, the log line and the verdict in **one call and 1,651
bytes**. The run it replaces made eight calls and got the answer backwards.

### The argument invariant, and three things only the cluster could say

"No fact tool takes any argument" was the rule with `promql` as its exception. The
real rule is that **an argument is safe when any string is valid.** `expr` and
`term` have no shape to copy wrong; `chatId` had exactly one, and cost two days.
`tests/test_expressions.py` fails any fact tool that grows an argument named
`namespace`, `labelSelector`, `fieldSelector`, `datasourceUid` or `endTime` — the
five values the model cannot know and has supplied wrong.

- **A 403 came back as an empty list.** With `find_object` live the oracle called
  it correctly and got `searched-and-not-matched` for grafana on a cluster running
  grafana: the ClusterRole granted the kinds the original nine tools read, and
  `kube.list` swallowed every exception into `[]`, so *not permitted to look* and
  *looked and found nothing* were the same value. **This repository's own rule
  broken by the tool written to enforce it.** `kube.KubeForbidden` is now raised
  for a 403 and only a 403 (an absent CRD still degrades to an empty list, which
  is normal here); `find_object` names forbidden kinds under `NOT SEARCHED` and
  returns `ERROR` when nothing at all could be read. **A lookup that could not run
  must never render as a lookup that found nothing — in a prompt, in a tool, or in
  RBAC. The layer with the most authority does the most damage.**
- **`Ingress` is the wrong kind here.** 35 `traefik.io/v1alpha1` IngressRoutes and
  **zero** `networking.k8s.io/v1` Ingresses, so a search covering only the standard
  kind could never answer "what URL is X on". Same shape as Valkey being scraped as
  `redis_*`. An IngressRoute's row is the hostname out of its `Host(...)` rules.
- **Truncation eats the end, so cardinality decides the order.** `grafana` matches
  2 Services, 1 IngressRoute, 2 Deployments, 1 PVC — and 45 Pods and 153 Jobs with
  near-identical rows. In the obvious order the generated instances consumed the
  whole 3 KB budget and truncated away the Service, its endpoints and the hostname.
  `_KINDS` is ordered identity-first, generated-instance-last, and Service endpoint
  lines are emitted next to the Service table. **Order a bounded answer by how much
  each row identifies, and let repetition be what gets dropped.**
- **`lookup.resolve` sorts by match strength, then kind order, then recency.**
  `grafana setup job` matches a Job and its pod equally well; the Job is the better
  subject because it answers for pods that no longer exist. **The ordering is a
  decision the model no longer makes**, which is the point of all of this.
- **Running it against the cluster found the bug testing could not.** `logs` came
  back as a single line: the Kubernetes client deserialises a `str`-typed response
  by calling `str()` on the raw bytes, so a log arrives as a Python **bytes repr**
  with escaped newlines, which every line count, filter and byte budget then reads
  wrong. Invisible in unit tests, because the fake returns a real string. `pod_log`
  passes `_preload_content=False` and decodes itself. **The fake in a test is
  written from the same understanding as the code.**

### Why each knob in `templates/mcpservers.yaml` is set that way

Read off the cluster on 2026-08-25 and verified after the ArgoCD app synced.

**Two pod labels decide whether it works at all, and one is an absence.**
`app.kubernetes.io/name: mcpserver` must be present — core's `agent-allow-tools`
NetworkPolicy grants agents egress on 8080 only toward that label and
`sympozium.ai/component: shared-memory`, so without it every call times out with
no useful error. `app.kubernetes.io/part-of: sympozium` must be **absent**: it is
selected by `sympozium-allow-otel`, whose only rule is ports 4317/4318, and a
NetworkPolicy selecting a pod for egress restricts it to the union of what the
selecting policies allow — so wearing that label would confine the server to the
OTel collector. Core's own MCP pods deliberately omit it.

**`toolsPrefix` is required by the CRD and only a server-side apply says so.** It
carries no `default`, so `helm template` renders happily and the webhook rejects
with `spec.toolsPrefix: Required value`. It is `facts` — and this is the
prefixed/unprefixed split to keep straight: `toolPolicy.allow` names
`facts_volume_fill` because that is what the model sees, `mcpServers[].toolsAllow`
names `volume_fill` because that filter runs at the server. Backwards in either
direction is a rule that matches nothing, silently. Run
`helm template ... | kubectl apply --dry-run=server -f -` before believing a render.

**`url:` and not `deployment:`** stops the controller reconciling a deployment of
its own; we own the workload and the CR only points at it.

**The RBAC is enumerated, and Secrets carry `list` without `get`.** Withholding
`get` makes a single-object Secret read impossible at the RBAC layer and not only
in the code, which strips `data`/`stringData` at its boundary as the second line of
defence. `cert_expiry()` narrows with a field selector rather than filtering
afterwards — an unfiltered cluster-wide Secret list transfers every value in every
namespace, 25 MB here, and broke the connection outright. The ClusterRole gained
`events` and `pods/log` when the diagnose chain landed; a kind missing from it is
a 403, which the code keeps distinct from an empty result.

**No `toolsDeny`, because there is nothing to deny.** Every tool is a read, the
server holds no credential, and it has no code path that writes. An empty list is
the honest form.

**A memory limit and no CPU limit.** `CPUThrottlingHigh` is already chronic across
roughly ten workloads here; a CPU limit would add an eleventh permanently-firing
alert to a fleet whose whole problem was noise.

**An emptyDir for the snapshot state, not a PVC.** Losing the snapshots degrades a
computed diff to "first observation", which every tool states explicitly, so it can
never produce a *wrong* diff. A PVC would put a volume under this chart's
management, and every storageclass here is `reclaimPolicy: Delete`.

**The image is multi-arch** (`linux/amd64,linux/arm64`) because agents land on the
Orange Pis; an arm64-less image is unschedulable there, which the agent experiences
as the tool simply not existing.

**The one check neither Helm nor the API server can make.** Helm's `.Files` cannot
read above the chart root, so the template cannot see whether
`agents/mcp/projects/<project>/` exists, and the API server validates the MCPServer
either way. A wrong project name deploys cleanly and crash-loops on
`no such project`. `validate.py` resolved the name the way the template does —
hyphens to underscores — and failed on a project that was not there; that check
is gone, so check the directory exists in `agents/mcp/projects/` by hand when
changing the name.

**`LOKI_URL` points at `datahub-local-core-loki.monitoring.svc:3100`**, direct
rather than through Grafana, for the same reason Prometheus is: no datasource uid
exists on that path, so none can be resolved to the wrong one.

## Every MCP server the control plane runs, wired onto one persona

The oracle held two servers and so could not answer questions this homelab
actually gets — "total size of each db" came back as node CPU load. It now holds
all six, in a priority order its prompt states, and the order is the design:

| #   | Server   | What it answers                           | Tools |
| --- | -------- | ----------------------------------------- | ----- |
| 1   | facts    | the standing readings, pre-computed       | 13    |
| 2   | k8s      | what exists right now                     | 4     |
| 3   | argocd   | what is deployed and what each app owns   | 3     |
| 4   | trino    | what is *in* the databases                | 5     |
| 5   | slack    | the thread that asked                     | 2     |
| 6   | github   | what the source says                      | 3     |

Thirty allowed MCP tools plus `send_channel_message`. Measured by summing the
`tools/list` entries the allowlists name, not estimated: 19,541 bytes of schema
across the 29 wired before Trino replaced postgres, roughly 5,900 tokens on every
call. (`token_usage` in a run log is **cumulative across the loop**, not the last
call, which is why a number this size is affordable where it looks alarming.)

What decided the selections:

- **A tool that returns a whole manifest is out**, whatever server it is on.
  `argocd_get_resources` and `argocd_get_application_managed_resources` are the
  ArgoCD equivalents of `k8s_resources_get`.
- **`argocd_get_resource_actions` is out because of its name.** It only lists
  available actions, but a 4B model reads a tool that enumerates actions as
  permission to run one — the SkillPack lesson.
- **Grafana is unwired entirely.** The whole server is 73.8 KB of schema and
  includes `create_datasource`; what was wanted from it was Loki, and the facts
  server reaches Loki directly. That takes the hex datasource uid out of the prompt
  for good.
- **GitHub is read-only here.** `add_issue_comment` stays on `renovate-reviewer`,
  which is bound to no channel; giving the inbound persona a write tool would
  collapse the trust split the ensembles exist to express.
- **Four tools left when a fact tool started answering their question with no exact
  value to supply**: `k8s_pods_list` (cluster-wide, 8.1 KB that answers nothing),
  `k8s_pods_log`, `k8s_nodes_top`, `argocd_get_application_resource_tree`.

Two argument traps came out of reading the schemas, both the `chatId` failure in a
new place — **an optional argument a model will fill in rather than omit**:
`argocdBaseUrl` is optional on every ArgoCD tool and `gitops-auditor` invented
`https://argocd.example.com` for it on a real run (the prompt now says never to
pass it); `datasourceUid` is required on every Loki tool, which is why it has to be
a pinned literal rather than a lookup.

**The cost to watch is not the window, it is the choosing.** 29 tools is the most
any persona holds, against a documented failure at sixty. The mitigation is that
the prompt is a numbered ladder with "stop at the first one that answers" rather
than a menu. If runs start wandering between servers, split the persona before
trimming the ladder.

---

# What actually bounds an agent

Read-only is the default and **`toolPolicy` is not the boundary.** Every persona
denies `write_file` and `execute_command`, but the deny filters *schema
registration*, not dispatch: the runner logs `tool policy: denied tool
"execute_command"`, omits the schema, and then executes the call if the model
produces the name from anywhere else. What holds hard is
`mcpServers[].toolsAllow`, enforced at the bridge, and the absence of a skill
sidecar to execute anything.

## A SkillPack overrode every tool decision in this repository

`endpoint-warden` delivered a placeholder, `sre-sentinel` reported no firing
alerts while four were firing, and `db-steward` wrote a whole daily report out of
its own memory. Three symptoms, one cause, and it was **not** context size: the
largest prompt Ollama saw across those runs was 15,294 tokens against
`n_ctx_slot = 65536` with no truncation. (Read `n_ctx_slot` and `task.n_tokens`
from Ollama's slot log before blaming the window; per-run token figures on the run
list are cumulative across LLM rounds.)

The cause was the mounted skill Markdown. `sre-observability`: "You are running
in-cluster with `kubectl`, `curl`, and `jq`. Use `execute_command` for all shell
commands." `k8s-ops`: "You are running inside a Kubernetes pod with full cluster
admin access ... kubectl works out of the box." Every `homelab-ops` persona
carried one. A 4B model follows that over a nine-tool allowlist, and the runner
executes the call anyway. **744 shell commands ran across the fleet in the 7 days
to 2026-08-24**, on personas that denied `execute_command`.

What each symptom was: `endpoint-warden` spent 11 of 16 calls on `curl` against
four guessed Prometheus URLs, `ls /workspace`, `getenforce`, `ps aux`;
`sre-sentinel` made two correct `grafana_query_prometheus` calls *first* and then
buried them under 18 kubectl results, writing `Still firing: None` while four
alerts fired; `db-steward` sent `endTime: "1725489600"` — 2024-09-04 — on all six
queries because the skill demonstrated `NOW=$(date +%s)` and the model reproduced
the shape without a shell to evaluate it, then wrote a full report from
`memory_search`.

**The read-only guarantee was never real.** `k8s-ops` declares sidecar RBAC, which
the controller realises per run as a Role plus RoleBinding in `automation` — 109
pairs had accumulated, owned by retained AgentRuns — and every binding targets the
**shared `sympozium-agent` ServiceAccount**, the identity every agent pod in the
namespace runs as. Verified: `create pods/exec` yes, `delete deployments` yes,
`get secrets` yes, `create rolebindings` yes — a self-escalation path out of the
namespace, true since 2026-08-21, applying to personas that never listed the pack.
Nothing in `projects/` would have stopped it: a per-persona `toolsDeny` filters an
MCP server, and this path used no MCP server at all.

Both skills are gone from every persona, which leaves `memory` alone and deletes
the sidecar, so the RBAC is never created again. `validate.py` kept them out by
name (`SHELL_TEACHING_SKILLS`) rather than by a general rule, because the objection
is to what these two say; with it gone, nothing stops a third pack being mounted —
read `.spec.skills[].content` and `.spec.sidecar.rbac` before you do. The stale pairs needed deleting once by hand:

```bash
kubectl get rolebinding,role -n automation -o name \
  | grep sympozium-skill- | xargs kubectl delete -n automation
```

**The rule: a SkillPack is prose competing with the persona's own prompt, and prose
wins.** Read the Markdown of every pack before mounting it
(`kubectl get skillpack <name> -n automation -o json | jq -r '.spec.skills[].content'`)
**and** read `.spec.sidecar.rbac` with it, because mounting a pack grants its RBAC
to the whole namespace. Two skills per persona was a budget decision about
attention; it is now also a trust decision. `memory` and `code-review` carry no
sidecar, no RBAC and no shell instruction.

Related and settled by the same investigation: **a `SkillPack` cannot carry tool
wiring.** The CRD gives `skills[].content`, `skills[].requires` (documentation —
nothing reads it), `sidecar` and `runtimeRequirements`. No MCP servers, no
`toolsAllow`, no `toolPolicy`, no parameter substitution. So the tool half can only
live on the persona, and moving the prose into a pack buys an extra object and a
second place to look. **Shared prompt text belongs *in* the prompt** —
`prompts/shared/promql.md`, substituted into every persona holding `{{ PROMQL }}`,
after the `## Calling grafana_query_prometheus` section had been pasted into four
prompts and two of the copies had already lost a rule. The trap is worth keeping
even though the checks are gone: a content check has to read the prompt the
*model* sees, expanding tokens first, or it starts passing vacuously the moment
the text moves into a shared file. Any future test over these prompts inherits
that requirement.

## An inbound Slack message runs with no `toolPolicy` at all

Asking `sre-sentinel` "@Homelab current status of amd-2 machine" produced
`(no response)`. The run underneath it is worse than the silence:
`AgentRun/...-ch-g44pj`, created by the channel sidecar, carries **no
`toolPolicy`** — not a narrower one, none. Zero `tool policy:` lines where the
scheduled run logs 13. The first thing it did:

    tool call: execute_command args={"command":"kubectl get nodes","target":"k8s-ops"}

The run is built from the `Agent` object, and `Agent.spec.agentConfig` has no
`toolPolicy` field — the Ensemble controller can only park the prompt in
`spec.memory.systemPrompt`, and the tool policy has nowhere to go. So
`write_file`, `execute_command`, `edit_file`, `fetch_url`, `delegate_to_persona`
and `schedule_task` are live on any run started from a Slack mention. **The
read-only guarantee holds for scheduled runs only.**

The exposure is narrower than "unrestricted", and two obvious fixes do nothing:

- **MCP tools are already bounded**, because `toolsAllow` lives at
  `Agent.spec.mcpServers`, which the Agent *does* carry, and is enforced at the
  bridge. The channel run loaded the same 5 tools as the scheduled one.
- **`execute_command` is already dead**, as a side effect of removing the
  SkillPacks: the executor was the skill sidecar's `[tool-executor]`, so the runner
  writes the request and nothing answers. Do not read this as safety — it holds
  only while no persona mounts a pack with a sidecar.
- **`SympoziumPolicy.toolGating` looks like the fix and is not.** It has exactly
  the right shape and the Agent does carry `policyRef`, but it is not observably
  implemented in v0.10.47: no container logs `toolGating`, `featureGates` or
  `policyRef`, and every Sympozium NetworkPolicy in `automation` traces to the Helm
  chart or to core, `network-isolated`'s `denyAll: true` included. A custom
  hardened policy would deploy cleanly, read as a fix in review, and change
  nothing.
- **`channelAccessControl` gates *who* may trigger a run, not what the run may do.**

What is left reachable, in order: **the persona's own memory through `autoStore`
rather than through a tool** — the runner auto-injects memory into every run's
prompt and auto-stores each run's task and response with no tool call involved, so
**no `toolPolicy` and no admission patch can stop it**. A Slack message is the task
of a channel run and lands in that persona's memory, which its next scheduled run
reads back as its own prior finding. Then `delegate_to_persona`, `fetch_url`
(bounded by NetworkPolicy) and the pod's ephemeral workspace.

**What does work is a `MutatingAdmissionPolicy`** — GA here
(`admissionregistration.k8s.io/v1`, k3s v1.36.2), no webhook server. Match `CREATE`
on `agentruns.sympozium.ai`, condition on `!has(object.spec.toolPolicy)` so runs
carrying one are untouched, and patch in a `deny` list. Deny-only is the right
shape: the runner treats `allow` and `deny` as separate mechanisms, so it is a
blocklist and leaves MCP tools alone. `failurePolicy: Fail`, because a guard that
fails open is the silent kind of failure this whole file is about — which does mean
a CEL error stops every run, so probe after applying. Landed in core on 2026-08-24
as fix (6) in `sympozium_upstream_fixes.yaml`. **It is defence in depth, not a
boundary**: what it buys is that the model is no longer *handed* those tools, which
is the observed path.

So the choice is: keep inbound @-mentions with the schema hole closed and the
dispatch hole open, or drop `channels: [slack]` and close both. Only unbinding is
complete — which is why `homelab-reviewer`, the one ensemble with a write tool, is
not bound.

## Shared memory is inert

`workflow_memory_*` is the shared store's tool set and **no persona allows any of
the three** — every scheduled run logs `tool "workflow_memory_search" not in allow
list`. `homelab-ops-shared-memory` holds 2 records, both written by policy-less web
runs, against 10 in `sre-sentinel`'s private store. So `sharedMemory: enabled` buys
nothing today and the rationale recorded for it — that personas see each other's
notes — is not true in practice. Either allowlist `workflow_memory_search`
somewhere or stop claiming the ensemble shares anything.

## The `mcp-k8s` ClusterRole is what grants Kubernetes read access

Every `k8s_*` call goes through the
`datahub-local-core-automation-sympozium-mcp-k8s` ServiceAccount, whose ClusterRole
is `apiGroups: ["*"], resources: ["*"], verbs: [get,list,watch]`. A SkillPack's
`sidecar.rbac` grants a *separate* identity used only by that pack's sidecar, so
narrowing it protects nothing unless a persona mounts the pack — none do. Check
which of the two you are looking at before changing either.

The wildcard is deliberate: it is why a Longhorn volume, a CloudNativePG `Cluster`
and a cert-manager `Certificate` all answer without a core change, and an unlisted
group fails silently and the agent just writes a blander report.

**The cost is one tool.** `k8s_resources_get` returns the whole object, and for a
Secret that is the base64 values in full — verified 2026-08-24 against
`mcp-slack-token`, which came back with both tokens intact. `service-janitor`
allowed it, so a scheduled "read-only" persona could have read every secret in the
cluster and put it in a Slack report. `k8s_resources_list` returns a **table** —
names, types, key counts, the kind's own printer columns — and never contents. The
tool is in `BANNED_TOOLS`. If a persona ever genuinely needs an object's contents,
narrow the ClusterRole to enumerated groups first.

**The check that needed it was never satisfiable anyway.** `service-janitor` asked
for Certificates "whose renewal or notAfter date falls within 21 days", which needs
`resources_get` to read `status.notAfter` and then needs a **clock**, which the
agent does not have. cert-manager has already done the comparison and written the
answer into the `STATUS` column, so the check is now "READY is not True, or STATUS
says anything other than up to date", and the Secret half uses the relative `AGE`
column. **Before allowlisting a tool, ask what the persona would do with an answer
it cannot interpret.** A date is uninterpretable without a clock; a lifetime
counter without a window; a datasource list without knowing which uid is
Prometheus. Each time the fix was to move the interpretation out of the model and
into the query or the source.

## `allowedTriggers` is not access control

`homelab-oracle` is the only object in this chart an outsider can trigger, and for
its first days bound it restricted the *kind* of inbound message
(`allowedTriggers: [mention, dm]`) and not the sender. Anyone in the workspace who
could @-mention the bot got a run holding the facts server, `k8s_pods_log`,
`k8s_resources_list` and `send_channel_message`.

`channelAccessControl.slack.allowedSenders` gates *who*, is inbound-only, has no
default and no controller warns when it is missing. It lives in `values/` because a
sender id names a person, not the agent — same reason as `channelConfigs` — and it
is in `VALUES_ONLY_KEYS`. `validate.py` failed a channel-bound persona whose
ensemble set neither `allowedSenders` nor `allowedChats`, and warned on a missing
`denyMessage`; both are unguarded now. An unset `denyMessage` drops a rejected
sender in silence and reads as a broken agent rather than a refusal, and an unset
allowlist on the one inbound-bound persona is the open-door case — check both
whenever `homelab-responder`'s binding changes.

## Why the `permissive` policy

| Policy             | `networkPolicy.denyAll` | `toolGating.defaultAction`       |
| ------------------ | ----------------------- | -------------------------------- |
| `permissive`       | `false`                 | `allow`                          |
| `restrictive`      | **`true`**              | `deny`                           |
| `network-isolated` | **`true`**              | `allow` (but `fetch_url` denied) |

`restrictive` and `network-isolated` both deny all egress except DNS and the event
bus and neither declares `allowedEgress`, so binding either would cut the agents
off from Ollama *and* every MCP server. `restrictive` additionally gates tools
deny-by-default against a rule list that knows only built-in names, so every MCP
tool would be denied. Restriction is enforced where it is reviewable — the
per-persona `toolPolicy` and `toolsAllow` in `projects/`.

A hardened policy is still the better end state and needs a custom
`SympoziumPolicy` with `denyAll: true` plus explicit `allowedEgress` for Ollama and
each MCP service. `allowedEgress` takes a `host`, and whether the controller can
turn a service DNS name into a NetworkPolicy peer needs verifying before anything
depends on it — as does whether `SympoziumPolicy` is enforced at all on this
version.

## The agent NetworkPolicy blocks shared memory and every MCP server

**Resolved by core on 2026-08-21/22**, kept because it is the upstream chart's
default and will bite the next person who deploys this chart elsewhere. The
chart's `sympozium-agent-deny-all` selects `sympozium.ai/role=agent` and
`sympozium-agent-allow-eventbus` punches holes back — on port 8080 to exactly
`sympozium.ai/component=memory`, `app.kubernetes.io/name=model` and
`app.kubernetes.io/component=apiserver`. The **shared memory server**
(`component=shared-memory`) and the **MCP servers**
(`app.kubernetes.io/name=mcpserver`) are labelled neither, so a chart shipping
both reaches neither. `policyRef: permissive` does not help: those policies come
from `networkPolicies.enabled` and select all agent pods regardless of the bound
`SympoziumPolicy`.

The two failure modes followed directly: every `homelab-ops` pod hung in
`PodInitializing` on the `wait-for-shared-memory` init container and reported
`Job failed` with `reason: infra` and no agent logs at all; `homelab-reviewer`
started, reached Ollama, and died on `exceeded maximum tool-call iterations (50)`
with every MCP call blocked. Note the first request or two *succeed* — k3s programs
the policy a second after the pod starts, so an immediate probe sees a working
network.

Core's fix is `agent-allow-tools`, allowing 8080 to those two label selectors —
deliberately narrower than adding 8080 to `extraEgressPorts`, which renders as a
rule with no `to:` and opens the port to the whole cluster.

### The same policy set took the delivery hook, and the Python rewrite is what exposed it (2026-08-31)

Every scheduled report from 2026-08-30 12:05 UTC onward reached Slack nowhere.
The run itself was fine — `Succeeded`, a full `status.result` — and the only
trace was `PostRunFailed` on the run plus one line in the hook pod's log:

    DELIVERY FAILED: <urlopen error [Errno -3] Try again>

`Errno -3` is `EAI_AGAIN`: the resolver timed out. CoreDNS was not the problem —
one replica, `up` throughout, zero `SERVFAIL`, a flat ~4.9 req/s across the whole
window — and a plain pod in `automation` resolved `slack.com` and reached
`https://slack.com` on the first try.

The postRun pod is not a plain pod. The controller stamps
`app.kubernetes.io/part-of: sympozium` onto it, which is the podSelector of the
upstream chart's `sympozium-allow-otel` — `policyTypes: [Egress]`, one rule,
ports 4317/4318. A pod selected by *any* Egress policy is denied every other
egress, so port 53 was closed. Reproduced exactly by giving a bare pod that one
label: first lookup answers, every lookup after it returns `Errno -3`.

That first answer is the mechanism, and it is the race recorded two sections up —
k3s programs the policy about a second after the pod starts. **The policy has
been starving these pods since 2026-08-20; what changed is how fast the hook
runs.** The last delivered report and the first lost one are consecutive ticks of
the same schedule, and the run objects say what differed:

| run | hook | outcome |
| --- | --- | --- |
| `gitops-auditor-schedule-27`, 08:04:40Z | `curlimages/curl:8.11.1`, `/bin/sh -c`, one `curl --max-time 30`, no retry | delivered |
| `gitops-auditor-schedule-28`, 12:05:07Z | `python:3.13-alpine`, `python3 -c`, 3 attempts with 2s/4s backoff | `Errno -3` |

87ef870 landed at 10:10 UTC that morning, between the two. One `curl` fires
inside the window; CPython starting, importing and converting the report does
not, and by attempts two and three the rules are long since programmed — a
retry loop cannot rescue a permission that only exists for the first second.
So the rewrite did not cause the bug, it stopped hiding it, and the diagnosis is
not "a coin that had been landing the same way": it is a specific, dated change
in how long the pod waits before its first packet. **A capability that depends on
winning a race is not a capability, and the thing that reveals it can be a
refactor that made the code better.**

Scope, because the first read of this was wrong in both directions:

- **Only hook-mode personas are exposed** — the five `homelab-ops` reporters.
  `homelab-oracle` is `deliveryMode: reply` and `renovate-reviewer` is unbound,
  so neither run carries a `lifecycle` at all (`.spec.lifecycle` is `null`). The
  responder never touches this path: its answer leaves through the
  `homelab-oracle-channel-slack` sidecar, a long-lived Deployment (up since
  2026-08-25) with an egress policy of its own, so there is no pod start to race.
  It answered normally all through the same window.
- **The 2026-08-26 `PostRunFailed` on `db-steward-schedule-3` is a different
  bug**, not an early instance of this one. Its log is still in Loki and reads
  `sed: bad regex ... Unknown character class name` — the fence-stripping
  expression in the *shell* hook, which the Python rewrite deleted. Do not read
  it as evidence for the race.

The gap is upstream's and it is legible once the three workload classes are put
side by side: `sympozium-agent-allow-eventbus` grants agent pods 53 and 443,
`sympozium-channel-allow-egress` grants the channel sidecars 53 and 443, and the
postRun pod — the one that exists to make an outbound HTTPS call — is granted
neither, only 4317/4318 by way of a policy about telemetry it never sends.

**Core owns the fix**, as
`datahub-local-core-automation-sympozium-post-run-allow-egress` (applied
2026-08-31 05:28:58Z). It selects `sympozium.ai/component: post-run` — the
controller's own label for these pods, narrower than `part-of: sympozium`, so it
widens nothing else — and grants 53 to `k8s-app: kube-dns` in `kube-system` plus
443 to anywhere. DNS goes to the resolver by label rather than to the ClusterIP,
because a hardcoded `10.43.0.10/32` fails in exactly the way this bug did.

This chart briefly carried the same policy in `templates/networkpolicy.yaml` and
it was **deleted once core applied one**, not kept as a backstop: a postRun pod
is a platform object, this sub-project declares `Ensemble`s only, and two owners
of one rule is the drift this repo keeps refusing to create. NetworkPolicies
being additive is what made a local copy *possible*, not what made it right.

Verified end to end: `db-steward-schedule-9` at 05:30:01Z, the first tick after
the policy landed, logged `slack response: {"ok": true, ...}` and `delivered ok`
— the first report delivered since 2026-08-30 08:04:40Z.

## The `channel-slack` Deployments have no resource requests or limits

Every other workload the controller creates for a persona is bounded; the channel
container is the exception. The memory sidecar takes `50m/64Mi` from its
SkillPack's `spec.sidecar.resources`; the channel Deployment is built from
`spec.channels[]`, which has no equivalent field anywhere in the `Ensemble` or
`Agent` CRD (confirmed by searching both schemas). Not settable from this
repository or from core's values, and not patchable the way core's other chart
fixes are — `_kustomize.yaml.gotmpl` patches chart-rendered resources, and these
are created by the controller long after the chart renders. Upstream wants a
`resources` field on `ChannelSpec`; a `LimitRange` in `automation` is the stopgap,
worth it only if the unbounded pods actually cause a scheduling problem.

# Running, testing and observing the fleet

## Test with a hand-applied `AgentRun`, not a trigger

It suppresses no schedule and takes `systemPrompt`, `task` and `toolPolicy`
inline, so it is the only probe that carries the persona's real restrictions. The
pod is deleted on completion whatever `cleanup` says, so stream the log while the
run is live:

    kubectl logs <pod> -c agent -f

## A completed run's log is in Loki, not gone

A run that has already finished is not unrecoverable: Loki keeps every container
of it, keyed by `status.podName` over the `startedAt`/`completedAt` window. That
is the only way to diagnose a scheduled run after the fact, and the only way to
*count* a failure mode across the fleet instead of guessing at it.

```bash
kubectl port-forward -n monitoring svc/datahub-local-core-loki-gateway 3199:80 &
curl -sG http://localhost:3199/loki/api/v1/query_range \
  --data-urlencode 'query={pod="homelab-ops-sre-sentinel-schedule-75-rqmbq"}' \
  --data-urlencode 'start=2026-08-24T06:07:00Z' \
  --data-urlencode 'end=2026-08-24T06:11:00Z' \
  --data-urlencode 'direction=forward' --data-urlencode 'limit=5000'
```

The `agent` container carries the tool calls and the terminal warning;
`mcp-bridge` carries which server each call went to; `mcp-discover` prints the
per-server tool counts. **Tool *results* are logged nowhere** — replay the query to
see what the model saw.

The fleet-wide counters:

    {namespace="automation",container="agent"} |= "terminal turn had empty text"
    {namespace="automation",container="agent"} |= "exceeded maximum tool-call iterations"

The `ollama-proxy` sidecar on the ollama pod logs every request body, which is how
a run becomes readable rather than inferable:

    kubectl -n data logs <ollama-pod> -c ollama-proxy --tail=400 | grep 'DEBUG output'

The container was called `metrics-proxy` until 2026-08-29, so **Loki history is
split on the container label**: match `container=~"ollama-proxy|metrics-proxy"`
when looking back.

## An empty `status.result` has three causes, and two are still live

Reading an empty `result` as a quiet run is always wrong: the phase is `Succeeded`,
there is no `error` and no condition.

1. **Invalid UTF-8 in the reply** — the runner ships it to the controller over
   gRPC and protobuf refuses to marshal a bad `string`, so it is dropped with
   `rpc error: ... string field contains invalid UTF-8` one line above the result
   marker and no `response` key in the payload. Our own header caused it:
   `prompts/delivery/header.md` ordered the model to reproduce `·` (U+00B7)
   character for character, and a 4B model at a `q8_0` KV cache sometimes emits a
   lone continuation byte. Three throwaway ASCII-only runs stored 2, 72 and 1,599
   characters without trouble while persona runs mandating the `·` came back empty
   at 26 of 45. Headers are `|`-separated now, and an indented block in
   `prompts/delivery/` must stay ASCII-only because it *is* the text the model is
   told to emit. `validate.py` enforced that and no longer exists, so grep it
   yourself: `grep -nP '^\s+.*[^\x00-\x7F]' prompts/delivery/*.md`. The durable fix is
   control-plane side — sanitise or lossy-decode before the marshal, so a corrupt
   byte costs a replacement character rather than the whole report.
2. **`terminal turn had empty text`** — the model stopped writing, usually after a
   spiral of empty lookups or one oversized result. `deliveryMode: hook` removed
   the *dominant* cause (the run ending on the posting call), not the mechanism.
   Measured over 48h on 2026-08-29: seven runs — `gitops-auditor` twice,
   `sre-sentinel` three times, `endpoint-warden` once, the oracle once, roughly one
   run in ten. **Run that query before believing a prompt fixed it.** Note the
   runner *does* have a reasoning fallback, and the wording is about *prior* turns,
   so a non-empty reasoning trace on the terminal turn itself is not one it takes.
3. **`exceeded maximum tool-call iterations`** — worse than the other two, because
   the run ends `status: error` and the `postRun` hook never fires, so nothing
   arrives at all, not even a placeholder. Hence `MAX_TOOL_ITERATIONS: "100"`.

In `reply` mode the runner's placeholder *is* the reply, so it goes into the
thread as the answer.

**An empty result hides every other bug in the prompt behind it.** `db-steward`'s
Valkey section had been unsatisfiable since the persona was written and nobody
could see it, because the runs that would have shown it delivered a placeholder.

## Thinking was off, and the switch is in the wrong repo

Between 2026-08-28 20:33 and 2026-08-30, `qwen3.5:4b` ran with thinking disabled:
the ollama sidecar force-merged `{"reasoning_effort":"none"}` over every
`POST /v1/chat/completions`. Worth writing down because the switch is not in this
repo, not in the Ensemble, and invisible from every object an agent touches.

**Sympozium has a `thinking` field and the Ensemble is the one CRD without it.**
`AgentRun.spec.model.thinking` and `Agent.spec.agents.default.thinking` both take
`off|low|medium|high`; `Ensemble.spec.agentConfigs[]` has `model`, `provider` and
`baseURL` and no `thinking`, so a persona cannot carry one and all seven live
Agents read `UNSET`. That gap is the whole reason the knob ended up at the proxy,
which is fleet-wide and reaches `dlt_runner`'s bodega enrichment too.

**Forcing it was the wrong shape; defaulting it is the right one.**
`OLLAMA_PROXY_REQUEST_OVERRIDES` merges *over* the client body, so nothing
downstream could opt back in. The sidecar grew `OLLAMA_PROXY_REQUEST_DEFAULTS`,
which merges *under* it — precedence is overrides > client > defaults — and core
sets the level there. If the Ensemble CRD ever grows `thinking`, the persona wins
without a core change.

**Thinking fixes a class of misreading this fleet has hit repeatedly.** Replaying
`db-steward`'s terminal turn against a fixture carrying the archiver trap
(`failed_count total=2`, `increase(...[1h])=0`): thinking off, 1 of 5 runs called
it CRITICAL — the exact false page that reached Slack twice; thinking on, 0 of 10.

**It also introduced a new way to lose a report.** On 2026-08-30
`homelab-ops-db-steward-schedule-8` reported `Succeeded`, 5 tool calls and
`No result available`; the proxy debug log has the terminal response with
`finish_reason: "stop"`, `content: ""`, and 266 tokens of complete analysis sitting
in `reasoning`. The repair is in the sidecar, the only layer we control:
`OLLAMA_PROMOTE_REASONING_TO_CONTENT` (default `true`) copies `reasoning` into an
empty `content` on non-streaming `/v1`. Two guards matter — a choice carrying
`tool_calls` is legitimately content-empty and is skipped, or every intermediate
turn would get prose written into it; and `reasoning` is copied, not moved.
Streaming is deliberately uncovered: knowing content stayed empty means buffering
the whole stream. **Treat the promotion as a floor, not a fix** — what arrives is
chain of thought and does not honour the section contract, so it converts a silent
drop into a badly formatted report.

**The level is `high`, against the measurement.** At n=5 per level, `high` showed
no gain over `low` on any axis measured and produced one perfectly formatted but
empty report plus one promoted run that failed the format check; higher thinking
also makes promoted text longer and less report-shaped. Small sample, so a weak
result rather than a refutation — re-measure before concluding either way. What is
not in doubt is that the gain over `none` arrives at `low`.

One unrelated trap found while measuring: Ollama occasionally answers a tool-heavy
request with `{"error":{"message":"XML syntax error on line 14: unexpected EOF"}}`.
Rare, upstream, independent of thinking level — do not read it as a reasoning
failure.

## The oracle runs on OpenRouter, and the ensemble is the only place a credential fits

`homelab-responder` moved off `qwen3.5:4b` to `deepseek/deepseek-v4-flash-0731`
on OpenRouter. It is the first persona in this fleet on a metered endpoint, and
it is the right one to be first: the oracle answers a person who is waiting, it
routes across six MCP servers with a 29-tool allowlist, and it is the only
persona whose failures are seen by the asker rather than by nobody. The reporters
and the reviewer stay on Ollama — nothing scheduled needs to cost money.

**A three-way split across two files, and the third half is the trap.**
`provider` and `model` are the agent, so they are `defaults:` in
`projects/homelab-responder/ensemble.yaml`; `baseURL` and `authRefs` are the
cluster, so they are in `values/`. All three must agree and none of the
disagreements is loud:

- The controller selects the credential with `ref.Provider == persona.Provider`
  — a plain string compare with **no case folding**, unlike
  `agentAllowsModelCredential` two functions away, which uses `EqualFold`. A
  mismatched string is a run with no credential, not an admission failure.
- An empty `baseURL` is not an error either: `newOpenAIProvider` falls through to
  the OpenAI SDK default, so a cloud provider with no endpoint sends the run to
  `api.openai.com` with an OpenRouter key. The cluster-local `.svc` URL left
  behind after a swap is the same failure pointed at Ollama's port.

**The runner reads five key names and `OPENROUTER_API_KEY` is not one of them.**
This is the whole reason the wiring is worth writing down. `agentrun_controller.go`
keeps an `allowedAuthSecretKeys` allowlist and injects each of its eleven names
from the auth Secret individually as an *optional* `secretKeyRef` — deliberately,
so an auth Secret carrying unrelated keys cannot leak into the agent container.
`OPENROUTER_API_KEY` and `DEEPSEEK_API_KEY` are both on that list. But
`cmd/agent-runner/main.go` resolves the key with
`firstNonEmpty(API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, AZURE_OPENAI_API_KEY,
PROVIDER_API_KEY)` and reads neither. So a Secret keyed the obvious way is
injected, present in the pod, and never read: the run starts, calls OpenRouter
unauthenticated and gets a 401. **The key must be `API_KEY`** (or
`OPENAI_API_KEY`). Note the two lists disagree in the other direction too —
`PROVIDER_API_KEY` is read by the runner and absent from the controller's
allowlist, so it can never arrive. Neither list is documented; both were read out
of the source at v0.10.48. Re-check them after a control-plane bump.

**Egress and the thinking knob, the two things that did not need doing.** Egress
already works: the chart's own `sympozium-agent-allow-eventbus` opens TCP 443 to
`to: []` for exactly this case, and `agentSandbox.enabled: false` keeps the
narrower `sympozium-sandbox-restricted` off the pod. And the oracle no longer
passes through the ollama-proxy sidecar, so it loses the fleet-wide
`OLLAMA_PROXY_REQUEST_DEFAULTS` thinking level from core — no action needed,
because OpenRouter reports this model as `default_enabled: true` at effort
`high`, but it does mean the knob in *that* repo no longer describes this
persona.

**Cost is unmeasured here on purpose.** $0.065/M in, $0.18/M out against a 1.31M
context, and the chart's pricing table (`files/pricing/defaults.yaml`) carries
`openai`, `anthropic` and `bedrock` only — no `openrouter` entry, so Sympozium's
own cost estimate for these runs is empty rather than wrong. Add
`pricing.extraEntries` in core if the number is ever wanted; that is a
cluster-side change, not one for this chart.

## An apply fires an immediate run per touched schedule

`firstTick: afterInterval` is not the whole story. The Ensemble controller
reconciles each persona in turn and every `SympoziumSchedule` it **rewrites**
starts a run within the same second — no cron tick involved, `status.nextRunTime`
left pointing at tomorrow. Read straight off the controller on 2026-08-24:

```
07:49:20 controllers.Ensemble  Updating SympoziumSchedule for persona  db-steward
07:49:20 controllers.SympoziumSchedule  Created scheduled AgentRun  ...-db-steward-schedule-5
07:49:23 controllers.Ensemble  Updating SympoziumSchedule for persona  endpoint-warden
07:49:23 controllers.SympoziumSchedule  Created scheduled AgentRun  ...-endpoint-warden-schedule-6
```

The db-steward schedule still reported `lastRunTime: 05:30`, `nextRunTime:
tomorrow` while `-schedule-5` was running, so **schedule status is no guide to what
is executing.** A run started that way is a real run: it posts to Slack, it counts
against `MAX_TOOL_ITERATIONS` and it writes memory. **Apply once**, and use a
hand-applied `AgentRun` for probes.

A *fresh* schedule does not queue a run — the six created on the 2026-08-25 sync
came up with `nextRunTime` at their next cron tick and no run at all, because
`firstTick: afterInterval` holds on creation. The same-second behaviour is about a
schedule being **rewritten**. Fixing this upstream means not resetting a
schedule's tick on a spec update that did not change the cron.

## `Ensemble.spec.enabled: false` does retire what it stamped out

The CRD's field description reads as though `enabled` gates creation only. It does
not. Patching both ensembles to `false` on 2026-08-25 retired within ten seconds:
6 `Agent`s, 6 `SympoziumSchedule`s, 6 per-persona memory Deployments, Services and
PVCs, and the ensemble-owned shared-memory objects. It is a real off switch and the
lever to reach for rather than deleting Agents by hand.

Two things follow. **Turning it back on is not free** — N personas means N real
runs against one Ollama slot, per the section above; enable one at a time after a
hand-applied `AgentRun` has proved the persona. And **`enabled: false` destroys
memory**, since the memory PVCs carry an ownerReference on the generated `Agent`
and every storageclass here is `reclaimPolicy: Delete`. That was wanted once. It
will not always be.

## Editing `memory.seeds` in git does nothing to a running ensemble

The controller writes seeds once, at install, into
`ConfigMap/<ensemble>-<persona>-memory` under the key `MEMORY.md`, with no
`ownerReferences` and no reconcile afterwards. Apply a changed `seeds:` list and
the Ensemble updates, the `systemPrompt` and `toolPolicy` on the next `AgentRun`
update — and the run's `## Memory Context` still carries the old text. Verify
against the next run's task, not the Ensemble:

    kubectl get agentrun -n automation <run> -o jsonpath='{.spec.task}'

**This had been true for three days and nobody checked.** Measured 2026-08-24:
every memory ConfigMap still carried `creationTimestamp: 2026-08-21T19:04:59Z` and
three of five personas were short of what git said — `endpoint-warden` 7 seeds
against 12, `sre-sentinel` 4 against 7, `db-steward` 4 against 5. The missing ones
were not incidental: `db-steward` was still being told a rising archiver count is
"the most serious finding available here", the exact wording the counter correction
replaced, and `endpoint-warden` still carried the kernel-drift rule the
hardware-class correction had fixed. **A seed correction is not done when it is
committed.** `reseed-memory.sh` regenerates every ConfigMap from
`projects/*/agents/*.yaml`; run it after any seed change and verify with the
ConfigMap. Stored run records are separate and survive it.

## A hand `kubectl apply` owns the personas, and nothing takes them back

The live `homelab-ops` Ensemble was clobbered on 2026-08-26 and repaired by hand
the same morning. `--show-managed-fields` records the result:

    argocd-controller          Apply   06:48:50  spec.agentSandbox, baseURL, channelConfigs,
                                                 enabled, policyRef, sharedMemory, workflowType
    kubectl-client-side-apply  Update  06:49:07  spec.agentConfigs

`spec.agentConfigs` — the personas, and every cron, task and tool list inside them
— is owned by a client-side `kubectl apply` made 17 s after ArgoCD's sync. The app
syncs with `ServerSideApply=true`, but `agentConfigs` is atomic to the API server,
so a client-side apply takes the whole field in one move.

That would self-correct if the app healed, and it does not: its sync policy is
`{"automated": {}}` — no `prune`, no `selfHeal`, and **no** Application in this
cluster sets either. Automated sync means *on a new git revision*, so in-cluster
drift is detected, reported `OutOfSync`, and then left alone indefinitely.

**A hand apply to an Ensemble is a durable change, not a temporary one**, and
**`OutOfSync` is the only alarm there is.** `gitops-auditor` reads precisely this
signal every 4h, which makes its "drift that survives two consecutive runs" rule
the one thing that would have caught this, and makes treating its output as noise
expensive.

## Measuring whether a prompt change worked

Every fix in this file was verified by one hand-applied `AgentRun` and argued from
a Loki query afterwards. That confirms a mechanism and does not tell you whether
the fleet got better: there is no number that moves.

1. **A question set.** Built: `evals/questions.yaml`, 20 questions — the incidents
   this file writes up, the standing readings, resolution, reachability and logs,
   and three that must produce no lookup call at all. Each carries the tool the run
   should reach for first, a lookup cap, and `must_name`/`must_not` strings. Two
   decisions in it are the interesting part: `answer` records what was true on
   2026-08-29 and is deliberately **not** scored, because a figure moves and a
   stale expectation becomes a permanent false finding; and a `must_not` string has
   to be one that cannot appear in a *correct* answer either — "CRITICAL" and
   "expired" both failed that, since "no CRITICAL alerts" and "nothing has expired"
   are right answers.
2. **A runner.** Not built. Applies each question as an `AgentRun` against the live
   persona, streams the agent log, and records tools called in order, iterations
   used, first-call input tokens, result bytes, and whether the run ended with text.
3. **Five mechanical scores**, none needing a judge: did it call a resolving tool
   before any exact-value tool; did it repeat a call byte-for-byte; did it make a
   negative claim after an empty result; did it deliver non-empty final text; did
   the refusal literal appear in an answer that should have looked something up.
4. **One standing counter** — the `terminal turn had empty text` Loki query over a
   fixed 48h window, the fleet-wide version of score 4.

The mechanical ones are falsifiable today, which the prose ones never were.

## The endpoint *replaces* the schedule — it does not sit beside it

The `sympozium_web_endpoint` values tree, the render-time skill append and the
per-persona knobs under it are **gone**. `homelab-oracle` covers "ask it
something" properly. The three reasons are kept here, because `webEndpoint` is now
a first-class persona field and someone will be tempted again:

- **A serving `AgentRun` makes the schedule controller skip every tick for that
  agent, silently.** Enabling the endpoint creates one long-lived `AgentRun` in
  phase `Serving` per persona, which puts the `Agent` into `Serving`, and the
  schedule logs `Skipping trigger — instance has a serving AgentRun` while the
  `SympoziumSchedule` stays `Active`. Observed, not inferred: the endpoints came up
  at 05:24:30Z on 2026-08-23 and the next two due ticks never produced a run. No
  failed run, no event, no change in phase — the fleet just stops.
- **A web run gets neither `toolPolicy` nor `lifecycle`.** The proxy builds the
  child `AgentRun` from the **`Agent`** object, which has no `spec.toolPolicy` and
  no `spec.systemPrompt`, so the run is both unbounded — 60 tools registered
  including `write_file` and `execute_command`, against a persona that allows nine
  — and undeliverable, which is how one wrote a full CRITICAL report and delivered
  none of it. Same root cause as the inbound Slack path.
- **It truncates the task to its first line.** The persona's four-paragraph
  `taskFile` arrived as `Do an on-call sweep now.` — the last paragraph, the only
  place that told the agent to deliver, gone. The system prompt still described
  *how* to post and *when*; what it never said was that posting is required, and a
  4B model reading "here is how to post" plus a task that stops at "do a sweep"
  reasonably stops after writing the report.

**Never put a requirement in a field a caller can replace.** Anything a run needs
in order to be correct has to live in the prompt the persona always carries. That
is three separate ways this repository has paid for the same lesson, and each
failed by producing a plausible run that did less than it claimed.

If an HTTP trigger is ever wanted again, use `agentConfigs[].webEndpoint` and
re-verify all three. Two smaller things if you do: the serving run has
`useContext: true` on a *fixed* session key, so successive requests accumulate
history while every scheduled run starts clean; and its per-request `AgentRun` Jobs
are ordinary agent pods carrying `sympozium.ai/role=agent`, so the usual policies
cover them. The proxy pods themselves are labelled
`sympozium.ai/component: agent-server` while the chart's own
`sympozium-web-proxy-allow-ingress` selects `component: web-proxy` — the policy
matches nothing, leaving `sympozium-allow-otel` as the only Egress policy selecting
them, which restricts them to ports 4317/4318 and so denies the Kubernetes API they
need to create a run at all. Core added a matching policy; upstream should fix the
selector.

## Agent Sandbox is wired, disabled, and inert in both directions

All three ensembles state `agentSandbox.enabled` explicitly — including the two
that are false — so the fleet's sandbox state is one grep rather than an inference
from absence. It lives in `values/` and is in `VALUES_ONLY_KEYS`: whether a run can
have a kernel boundary depends on runsc being on the nodes and on the controller's
RBAC, neither of which a persona knows anything about. `RUNTIME_CLASSES` is
`{gvisor}`, the only one datahub-local-bootstrap installs; any other name deploys
cleanly and leaves every sandbox Pending. No `warmPool` anywhere — it keeps
pre-warmed pods resident for the life of the ensemble, and one weekday run does not
justify two idle sandboxes on a single-GPU fleet. The capability spans three
repositories — runsc in bootstrap, the controller's RBAC in core, the per-ensemble
opt-in here — and no check here could ever see more than the third.

Four things were found turning it on:

1. **The backend is gated in core and fails before the pod.** A probe went straight
   to `Failed` with `agent-sandbox mode requires dynamic client (agent-sandbox CRDs
   not available)`. The CRDs existed; the controller's permission to see them did
   not, gated by `agentSandbox.enabled` upstream ("when false ... no RBAC rules for
   Sandbox CRs are created"). The failure is **before** the pod, so there is no log
   and, for a scheduled persona, nothing that looks broken.
2. **The Sandbox CR the controller builds is invalid.** Core landed the gate on
   2026-08-26 and the controller now logs `Creating Agent Sandbox CR` and never
   gets one: `Duplicate value: {"name":"TRACEPARENT"}` and two more, across the
   agent container, a sidecar and an init container. The pod-template builder in
   `controller:v0.10.47` injects the OTLP tracing env twice, once from the base
   builder and once from the sandbox wrapper. **It never fails and never gives
   up** — `status` stayed literally `null`, 15 reconciles in six minutes on
   exponential backoff, the `AgentRun` `Pending` forever. Under
   `concurrencyPolicy: Forbid` one of these blocks every later tick for that agent.
   The duplicate comes from `SYMPOZIUM_DEFAULT_OTEL_ENABLED=true` on core's
   controller Deployment; turning the chart's `observability` defaulting off
   *should* stop it — untested, and it costs the fleet's traces for every run.
3. **Nothing scheduled reaches that path.** The field lands intact on every `Agent`
   and then stops: `sympoziumschedules.sympozium.ai/v1alpha1` has no `agentSandbox`
   in its spec schema, so every `AgentRun` a schedule stamps out carries
   `spec.agentSandbox: null` and takes the Job backend. The controller resolves the
   backend from the `AgentRun` alone. **Do not read "the ensembles say
   `enabled: true`" as "the runs are sandboxed". The only proof is a pod, and there
   has never been one.**
4. **Channel-triggered runs have the same propagation defect.** Confirmed
   2026-08-27: a Slack mention was rejected at admission with `agent-sandbox mode
   is required by policy`, because `ChannelRouter.handleInbound` did not copy the
   field.

So on 2026-08-27 all three ensembles went to `agentSandbox.enabled: false` and back
to `policyRef: permissive`, with the requested state left explicit rather than
omitted. **Do not re-enable for only the scheduled personas**: every creator — the
responder, schedules, API, delegation, pipelines — must copy the Agent's
configuration into the `AgentRun`, each with a regression test that binds a policy
requiring Agent Sandbox and asserts the created run preserves `enabled` and
`runtimeClass`. Reverting the policy only restores unsandboxed execution; it is not
a fix. `validate.py` was deliberately coupled to the two states — `permissive`
while disabled, the core hardened policy while enabled — so a partial rollback
could not be rendered; that coupling is gone, so the two halves are now only
paired by this note. When it lands, record the controller version, the trigger
paths verified and the probe evidence here, and set all three back together.

**The rollout order is reviewer-first, responder-last**, which inverts where
isolation is most wanted and is about the cost of being wrong: a sandboxed run that
cannot reach Ollama costs the reviewer one silent weekday morning on a persona that
posts nowhere by design, and costs the responder a question that never gets an
answer.

**Still unverified, and a security question rather than a connectivity one:**
whether a sandboxed run pod carries `sympozium.ai/role=agent`. If it does not, *no*
NetworkPolicy selects it — `sympozium-agent-deny-all` included — so it would have
unrestricted egress and be *less* contained than an ordinary agent while
connectivity looked perfect. Check with `kubectl -n automation get pod <run-pod>
--show-labels` on the first sandboxed run; as of 2026-08-26 it cannot be checked at
all, on either count above.

The hardened policy itself
(`datahub-local-core-automation-sympozium-hardened-agent-sandbox`) requires the
backend, injects `gvisor` when a run omits a runtime class and rejects any other,
blocks shell execution, local file writes, delegation and subagents at admission,
disables the code-execution/browser/subagent feature gates, limits lifecycle-hook
images to the delivery image registry, and rejects lifecycle RBAC for identities,
secrets and RBAC resources. It is deliberately **not** `networkPolicy.denyAll`: the
allow-egress peers for Ollama and the MCP services must be verified in the core
chart first, and a deny-all without them silently cuts every agent off from the
model and its facts.

# Known gaps

- **A failed outbound send is only visible in the sidecar.** The tool answers
  `Message sent` before anything has been sent, so neither the agent, the
  `AgentRun` phase nor `status.result` can show a delivery failure — only
  `kubectl logs deploy/<persona>-channel-slack`, and it logs failures only.
  Anything watching for "the reports stopped arriving" has to watch Slack or that
  log, not the run history.
- **`#monitoring-ai-runs` has no producer.** A failed `AgentRun` notifies nobody:
  an agent that cannot run cannot report that it cannot run, which is how the
  Ollama restart on 2026-08-22 cost three runs in silence. It happened again on
  2026-08-26 and that one shows how little is left behind — `renovate-reviewer`
  fired at 06:00, the Ollama pod restarted at 06:01:00, the run died three seconds
  later on `connect: connection refused`, and the `AgentRun` retained
  `phase: Failed`, empty `status.message`, empty `status.result`,
  `conditions: null`, with the Job already pruned so the pod log was gone too. The
  whole diagnosis came from the controller log, where `agent.run.failed` with
  `reason: llm_error` lands. That signal has to come from outside the fleet — an
  alert on `AgentRun` phase, or an n8n workflow polling it, alongside
  `Catch Errors` which already does this job for n8n.
- **Slack channels are named, not `C0…` ids.** Slack accepts a name for
  `chat.postMessage`, but it is the legacy form and it breaks silently on a
  rename. Swapping is a one-line values change per channel.
- **`NodeClockNotSynchronising` is a true positive — do not seed it.** It fires on
  orpi-0 through orpi-3, which run no time daemon at all:
  `node_systemd_unit_state{name="systemd-timesyncd.service", state="active"}` is
  `0` on each against `1` on both amd nodes, and the NAS runs `chrony`. With
  nothing telling the kernel it is synchronised, `node_timex_sync_status` is `0`
  and the alert is correct. No clock has drifted yet —
  `max(abs(node_timex_offset_seconds))` across the fleet is 575 microseconds — so
  it is a latent fault that will only widen. The fix is at the node, not in the
  seeds: seeding it would teach the agent to ignore the one alert here telling the
  truth. Worth noting *how* it was diagnosed: before core enabled
  `--collector.systemd` the alert was indistinguishable from chronic noise. One
  metric turned a guess into a one-query answer.
- **S3 capacity is instrumented now, and looking for `garage_*` finds almost
  none of it.** Core's ServiceMonitor landed 2026-08-24 and this entry used to
  say the opposite; re-read it before trusting any "not instrumented" note here.
  The trap it leaves behind is worse than the gap was: only **four** metrics
  carry a `garage_` prefix (`garage_local_disk_avail`/`_total`,
  `garage_replication_factor`, `garage_build_info`). Everything that matters is
  published under bare names — `cluster_healthy`, `cluster_partitions_quorum`,
  `cluster_storage_nodes_ok`, `table_size`, `block_resync_errored_blocks`,
  `api_s3_request_counter`, `api_s3_error_counter` — so a prompt or a query
  written against the prefix finds four metrics and concludes the store is barely
  observable, while a bare name would collide with anything else publishing it.
  `facts_object_store_health` scopes every one of them by job. Still missing:
  repo-level CI history, because the GitHub MCP server ships no Actions or
  workflow tools.
- **Per-bucket S3 usage is the one reading in this fleet with no
  unauthenticated source.** Garage publishes no bucket label and no stored-bytes
  gauge to Prometheus at all, so bucket size and object count exist only behind
  the admin API's bearer token (`GET /v2/ListBuckets`, `GET /v2/GetBucketInfo`,
  which returns `bytes`, `objects` and `quotas`; verified against the v2.3.0
  OpenAPI spec, matching the running build). That is why `garageSecret` is an
  opt-in chart value rather than a requirement: unset, the facts server holds no
  credential at all and the bucket section reports itself `unavailable`, which
  keeps the server's original property true by default. Where a token *is*
  given, put the boundary in the code and not in the credential —
  `mcp_runner/garage.py` exposes two `GET`s by name with no generic request
  method, so a write endpoint is not expressible whatever the token permits, and
  it strips each bucket's `keys` because that field carries access key ids
  straight into a Slack message.

  Three deployment facts decided how this is wired. **A `secretKeyRef` cannot
  cross a namespace**, and core's own `garage-credentials` lives in `data` while
  the facts server runs in `automation`. The ExternalSecret `mcp-s3-token` in
  `automation` is what closes that, carrying `GARAGE_ADMIN_TOKEN` and
  `GARAGE_ADMIN_URL` (2026-08-31).

  **Both refs are `optional: true`, which is load-bearing rather than cautious.**
  An unresolvable `secretKeyRef` leaves the pod in `CreateContainerConfigError`
  indefinitely — that takes down all sixteen tools for every persona, not the one
  section that needs a token. Optional degrades it to the server's own no-token
  path, which states itself in the report and leaves every other reading intact.

  **Each key is named individually; never `envFrom`.** `mcp-s3-token` also
  carries `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`, which are S3 *write*
  credentials this server has no code path for. `envFrom` would hand all six keys
  to a read-only reporter to save two lines of YAML, and the pod would then hold
  credentials that can delete objects. Name the keys you use.

  **The token is the unscoped master admin token.** Garage v2 supports scoped
  tokens (`garage admin-token create --scope ListBuckets,GetBucketInfo`), and a
  scoped one would make the code-side rules a second line rather than the only
  one; with this token, `garage.py`'s two-GETs-by-name shape *is* the entire
  boundary. Re-mint scoped if that boundary ever has to hold against more than
  this one caller. Egress needs no change: no NetworkPolicy
  in `automation` selects `app.kubernetes.io/name: mcpserver`, so the facts
  server reaches `data:3903` the same way it already reaches Prometheus in
  `monitoring` — the deny-all here binds `sympozium.ai/role=agent`, which these
  pods deliberately do not carry.
- **The disk under a store is not the store's headroom.** Garage's data volumes
  sit on the shared 1.9 TB nfs share, but its *layout* assigns each node 10 GiB
  and it refuses writes at that figure however empty the filesystem is. Reporting
  the disk overstates the store by two orders of magnitude and would show a full
  store as 1% used — the same class of error as the fill inversion, with a wrong
  denominator instead of a wrong direction. `role_capacity` is a **label** rather
  than a sample value, so it cannot be summed in PromQL and the parsing happens
  in the tool. Ask what a store actually stops at before picking the number to
  divide by.
- **Redpanda publishes its cluster-wide counts from the controller leader
  alone.** `redpanda_cluster_brokers`, `_topics`, `_partitions` and
  `_unavailable_partitions` come from exactly one broker of three, and which one
  moves with leadership. Read per pod that is two brokers with no data — a
  finding that would fire forever and could never be actioned, the orpi-0 kernel
  shape again. The tool aggregates and says that one reporter is normal.
- **A young store is not a lossy one.** Prometheus here is configured for 30d and
  was holding 2.6h, because its PVC had been recreated 2.6h earlier. Judged
  against the configured window alone that is a CRITICAL on every run for a
  month; judged against the server's own uptime it is *filling*, which is the
  truth and clears by itself. `facts_metrics_store_health` computes the
  comparison. Before shipping a rule, ask what it reports the morning after a
  legitimate restart.
- **systemd unit state and pending OS updates are instrumented but unused.** Both
  landed 2026-08-23 (`node_systemd_unit_state`, `node_apt_upgrades_pending`,
  `node_apt_security_upgrades_pending`, `node_reboot_required`) and
  `endpoint-warden` was written around them not existing. Verify each against
  Prometheus before it goes in a prompt; that rule has not changed just because the
  metrics arrived. Standing in for systemd today, the warden checks the node's
  *Kubernetes* system workloads — `kube-system` and `monitoring` pods grouped by
  node — which on a k3s box is most of what systemd would have told you.
- **`facts_promql` is allowlisted on reporters whose prompts never mention it.**
  It costs a schema on every call in the loop and it is the one tool that makes a
  wrong query expressible again — the property the facts server exists to remove.
  Keep it only where a prompt names it, or drop it from the rest. It was dropped
  from `db-steward` on 2026-08-31 when three fact tools were added there and the
  schema budget had to come from somewhere; `gitops-auditor`, `service-janitor`
  and `sre-sentinel` still hold it without naming it.

---

## Follow-ups to share with the other repos

**Landed, kept as a record of what to re-check after a chart bump.** Four changes
to core's `kube-prometheus-stack.yaml.gotmpl`, all verified against the live
cluster on 2026-08-23: the k3s phantom components are disabled (no
`KubeSchedulerDown`/`KubeControllerManagerDown` rule and no scrape target at all —
re-check with `/api/v1/rules` and `/api/v1/targets`, since "not firing" and "not
defined" look identical from a dashboard); OS update counts and scoped systemd unit
state are published by the textfile sidecar; and the drifted node-exporter
`extraArgs` were re-synced. The SkillPack fixes landed 2026-08-24 (cut `k8s-ops`'s
sidecar RBAC to `get,list,watch` — it granted `create/patch` on `roles` and
`rolebindings` against the shared ServiceAccount — and stop the skill Markdown
prescribing a shell), as did the `MutatingAdmissionPolicy` for policy-less
`AgentRun`s, and core's half of the Agent Sandbox gate on 2026-08-26.

**Still open on core's side:** `mcp-k8s`'s Deployment is
unmanaged (`spec.deployment` is null while the Deployment it needs is still owned
by the CR); `mcp-postgres` denies `execute_sql` outright (see *Open, and not
ours*); github, argocd and grafana carry no catalog-level `toolsDeny` at all; and
`web-proxy` floats on `:latest` against a v0.10.47 control plane. Per-run skill
Roles and RoleBindings are owned by retained AgentRuns and accumulate — 109 pairs
by 2026-08-24 — so either set a retention on AgentRuns or give the RBAC objects a
shorter-lived owner.

**Upstream `sympozium-ai/sympozium`, ready to file, none fixable from either of our
repositories.** All of them share one failure mode — the run reports `Succeeded`
and quietly does less than it claims:

- `status.result` is dropped on invalid UTF-8 by the gRPC marshal; sanitise or
  lossy-decode before it.
- `toolPolicy` is enforced at schema registration and not at tool *dispatch*, so a
  denied name produced from anywhere else still executes.
- `Agent.spec.agentConfig` carries no `toolPolicy`, so every channel- and
  web-created run is ungated; per-run skill RBAC should also bind a per-instance
  ServiceAccount rather than the shared `sympozium-agent`.
- The web proxy drops `toolPolicy` and truncates the task to its first line.
- `MCPServer.status.ready` reports `true` for a server that answers no
  `tools/list`.
- The channel sidecar fan-out: filter on `metadata.instanceName`, which the
  envelope already carries.
- The sandbox pod-template builder injects the OTLP tracing env twice, so every
  Sandbox CR is rejected as invalid and the run hot-loops `Pending` forever.
- The controller's `allowedAuthSecretKeys` and the runner's key resolution are two
  hand-maintained lists that disagree in both directions: the controller injects
  `OPENROUTER_API_KEY`/`DEEPSEEK_API_KEY`/`GOOGLE_API_KEY`/`GROQ_API_KEY`/
  `MISTRAL_API_KEY`, which the runner never reads, and the runner reads
  `PROVIDER_API_KEY`, which the controller never injects. Either list alone looks
  correct, so a Secret keyed for the named provider yields a silent 401. Also
  `resolveAuthRefs` matches the provider string exactly while
  `agentAllowsModelCredential` uses `EqualFold` — see *The oracle runs on
  OpenRouter*.

**Needed in datahub-local-secrets for the oracle.**
`openrouter-auth-credentials` must reach `automation` and must publish the key as
`API_KEY`; its current `endpoint`/`api_key` pair is not in the controller's
allowlist and is never injected.
- `SympoziumSchedule` has no `agentSandbox` field, so nothing on a cron can request
  the backend; the same propagation is missing from `ChannelRouter.handleInbound`.
- `Ensemble.spec.agentConfigs[]` has no `thinking`, though `Agent` and `AgentRun`
  both do.
- `ChannelSpec` has no `resources`.
- A schedule's tick is reset on any spec update, including one that did not change
  the cron.

### Per-database schema and table sizes: the CNPG ConfigMap to hand to core

`facts_postgres_health` reports per-*database* sizes only, and nothing in the fleet
can see inside a database — see *The pg_\* tools see one database*. The path is
`spec.monitoring.customQueriesConfigMap` on the CNPG `Cluster`, where a query
carrying `target_databases: ['*']` is run once per database by the instance's own
exporter with the credential the operator already has. Not a proposal:
`pg_extensions` in `cnpg-default-monitoring` already does it, and
`cnpg_pg_extensions_update_available` carries a `datname` label spanning all
thirteen real databases (verified 2026-08-30). **The field is a list**, so append a
second entry rather than editing the operator's default. CNPG names the series
`cnpg_<key>_<column>`, matching the existing `cnpg_pg_database_size_bytes`.

```yaml
pg_schema:
  query: |
    SELECT pg_catalog.current_database() AS datname,
           n.nspname AS schemaname,
           pg_catalog.sum(pg_catalog.pg_total_relation_size(c.oid))::int8 AS bytes,
           pg_catalog.count(*)::int8 AS tables
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid OPERATOR(pg_catalog.=) c.relnamespace
    WHERE c.relkind OPERATOR(pg_catalog.=) ANY (ARRAY['r','p','m'])
      AND n.nspname OPERATOR(pg_catalog.!~) '^pg_'
      AND n.nspname OPERATOR(pg_catalog.<>) 'information_schema'
    GROUP BY 1, 2
  metrics:
    - datname:    {usage: "LABEL", description: "Database"}
    - schemaname: {usage: "LABEL", description: "Schema"}
    - bytes:      {usage: "GAUGE", description: "Total size of the schema in bytes"}
    - tables:     {usage: "GAUGE", description: "Tables in the schema"}
  target_databases: ['*']

pg_table:
  query: |
    SELECT pg_catalog.current_database() AS datname,
           n.nspname AS schemaname,
           c.relname AS relname,
           pg_catalog.pg_total_relation_size(c.oid)::int8 AS bytes,
           (SELECT pg_catalog.count(*)
              FROM pg_catalog.pg_attribute a
             WHERE a.attrelid OPERATOR(pg_catalog.=) c.oid
               AND a.attnum OPERATOR(pg_catalog.>) 0
               AND NOT a.attisdropped)::int8 AS columns,
           COALESCE(s.n_live_tup, 0)::int8 AS rows_estimate
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid OPERATOR(pg_catalog.=) c.relnamespace
    LEFT JOIN pg_catalog.pg_stat_user_tables s ON s.relid OPERATOR(pg_catalog.=) c.oid
    WHERE c.relkind OPERATOR(pg_catalog.=) ANY (ARRAY['r','p','m'])
      AND n.nspname OPERATOR(pg_catalog.!~) '^pg_'
      AND n.nspname OPERATOR(pg_catalog.<>) 'information_schema'
      AND pg_catalog.pg_total_relation_size(c.oid) OPERATOR(pg_catalog.>) 1048576
  metrics:
    - datname:       {usage: "LABEL", description: "Database"}
    - schemaname:    {usage: "LABEL", description: "Schema"}
    - relname:       {usage: "LABEL", description: "Table"}
    - bytes:         {usage: "GAUGE", description: "Total size of the table in bytes"}
    - columns:       {usage: "GAUGE", description: "Live columns in the table"}
    - rows_estimate: {usage: "GAUGE", description: "Planner row estimate"}
  target_databases: ['*']
```

Add the schema rollup first — roughly twenty series. Before landing the per-table
query, check what the floor lets through, per database:

    SELECT pg_catalog.count(*) FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind = ANY (ARRAY['r','p','m'])
      AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
      AND pg_catalog.pg_total_relation_size(c.oid) > 1048576;

CNPG has no per-query scrape interval, so it runs on every scrape of every
database; raise the 1 MiB floor rather than accepting a long tail of tiny tables.

**The column *count* rides along free; a column *list* is refused, and that is a
design decision.** A list of column names is a catalog, not a time series: the
value would carry no information, only the labels would, and Prometheus would
scrape and retain five long string labels per column every 30s for data that
changes on a migration and never otherwise. The stronger objection is that **the
facts server could not deliver it anyway** — every tool answer is capped at ~4 KB
and one 16 KB result reproducibly ends a run. So `columns` is a number on a row
that already exists, answering "how wide is this table", which is the question a
report can use. If column names are ever genuinely needed, the tool shape exists:
`get_object_details(schema_name, object_name)` on the postgres MCP, pointed at the
one database someone cares about.

The payoff lands in this repository with no credential: the readings become
`facts_promql`, then a bounded `facts_*` tool, and `agents/mcp/` keeps the property
that it holds no DSN.

### Trino answers structure; metrics answer size

Proposed and wired on 2026-08-30, correcting an earlier rejection. "A second
MCPServer per application database" was dismissed as thirteen Deployments, thirteen
credentials and thirteen tool prefixes. Thirteen **Trino catalogs** are none of
those: they are `.properties` keys in one ConfigMap behind one Deployment, one MCP
server and one tool prefix, sharing one read-only role. **Reject the shape, not the
idea.**

| Question | Route |
| --- | --- |
| What tables exist, what columns, what types | Trino `information_schema` |
| How big, and is it growing | CNPG `target_databases: ['*']` metrics |

Neither subsumes the other: `information_schema` has no size column and the JDBC
connector surfaces none, while metrics carry history a catalog lookup never can.

`homelab-oracle` dropped the postgres MCP entirely for
`datahub-local-core-automation-sympozium-mcp-trino` (prefix `trino`). Nothing was
lost: `pg_list_schemas` and `pg_list_objects` only ever saw the empty `postgres`
database and `pg_get_top_queries` read its `pg_stat_statements`, so none had ever
returned a real finding. `db-steward` keeps its postgres server —
`analyze_db_health` is instance-wide and Trino replaces none of it.

**`execute_query` is in, against the recommendation, and the prompt is what bounds
it.** A 4B model composing SQL is the failure class this fleet spent months
removing; only a passthrough reaches bytes. So the prompt carries exactly one
query, written out in full, with a rule that no other SQL may be composed and that
a question needing a different one gets "say so" — the `increase()` lesson applied
to SQL. Writing it found a bug reasoning would not have: `SELECT * FROM
cat.system.query(query => '...')` is what the documentation reads like and what a
model will produce, and it is a `SYNTAX_ERROR` reported at the same offset as a
plainly malformed statement, so the message never points at the missing
`TABLE(...)` wrapper.

**Core shipped the server within the hour and three of the wiring's assumptions
were wrong** — the prompt had been written from a naming convention, a README and a
syntax test against a catalog that did not exist yet, each of which is exactly what
this document says to read off the running system.

What held: the MCPServer name, `toolsPrefix: trino`, `status.ready: true`, a
`tools/list` of precisely `list_catalogs`, `list_schemas`, `list_tables`,
`get_table_schema`, `execute_query` and `explain_query` (deliberately not taken),
`rules.json` granting the `mcp` user `read-only` on every catalog and `none` on
`system`, and no `spec.toolsDeny`. What did not:

- **The catalogs are `postgresql_<database>`, not `postgres_<database>`**, and
  there are six, not thirteen: `airflow`, `miniflux`, `n8n`, `openwebui`,
  `polaris`, `superset`. The prompt does not let the model build the name — it
  calls `trino_list_catalogs` and copies the exact string out, the same rule as
  every `facts_*` term. A database with no catalog is `not found with
  trino_list_catalogs`, because a missing catalog is otherwise indistinguishable
  from a broken one.
- **The `system.query` passthrough is denied to the `mcp` user**
  (`Cannot execute function postgresql_superset.system.query`), so the size query —
  the whole reason `execute_query` was taken — could never have run, and would have
  surfaced as the oracle apologising in Slack with render, validator and
  `status.ready` all green. `SHOW STATS FOR <catalog>.<schema>.<table>` **is**
  permitted (verified against `bronze.bodega.raw_invoices`), so the prompt carries
  that instead: `row_count` on the row whose `column_name` is empty, and
  `data_size` per column stated as an estimate rather than bytes.
- **The `viewer` Postgres role does not exist**, so every `postgresql_*` catalog
  answers `FATAL: password authentication failed for user "viewer"`. The properties
  set `connection-user=${ENV:POSTGRES_VIEWER_USER}` against the `-r` read replica,
  but `pg_roles` lists only `admin`, `app`, `cnpg_metrics_exporter`,
  `cnpg_pooler_pgbouncer`, `postgres` and `streaming_replica`. The Iceberg catalogs
  answer normally through the same server, which isolates this to the credential.

**So the wiring is correct and inert** until core does two things, in order:

1. **Create the read-only role the catalogs already reference** — `viewer`, with
   `CONNECT` on the six databases plus `USAGE` and `SELECT` on their schemas, and
   the password matching the secret behind `POSTGRES_VIEWER_USER`. It is also what
   makes the next item safe. Worth adding while it is being fixed: the seven
   databases with no catalog — `app`, `commafeed`, `dagster`, `mealie`, `nessie`,
   `sqlmesh`, `postgres` — if they are meant to be reachable at all.
2. **Only then, if per-table bytes are wanted through Trino**, permit the
   passthrough:

       {"user": "mcp", "catalog": "postgresql_.*", "schema": "system",
        "function": "query", "privileges": ["EXECUTE"]}

   Trino does not parse the passthrough string, so `allow: "read-only"` on the
   catalog does **not** stop `query => 'DELETE FROM ...'`. The read-only boundary
   for that path is the Postgres role and nothing else. The CNPG metrics route
   needs neither change and also gives history.

**Trino requires no authentication here** — `web-ui.authentication.type=FIXED`
covers the UI only and the HTTP API accepts any `X-Trino-User`, verified by running
`SHOW CATALOGS` as an invented user — so a Trino-backed tool holds no credential,
which is the property `agents/mcp/` is built around. And the payoff is larger than
the question that prompted it: nothing in this fleet can currently see the Iceberg
warehouse at all, and the same four tools reach `bronze`/`silver`/`gold`/`test`.

## It answered, then offered, then refused

The first thread on the wired Trino path, 2026-08-30. Asked for superset's tables
and sizes, the oracle reached `postgresql_superset`, counted **52 tables** — real,
the `viewer` role existed by then — named the schema correctly, and then wrote
"I can provide you with the full list of table names if you'd like." Asked "i like
it", it replied with the out-of-scope refusal.

Four defects in three messages, and each one a rule that was already in the prompt:

- **It had the list and printed a count instead.** The no-offer rule was
  prohibitive — "no offer to run, check or show something" — and the model did not
  read *listing what it already held* as an offer to run anything. Forbidding a
  shape finds the next shape, so the rule is now positive and sits in the writing
  paragraph: when a tool result holds the names, rows or list the question asked
  for, print them; a count or a summary is not an answer.
- **`i like it` got the refusal sentence.** The four out-of-scope cases include
  "a greeting or small talk", and a three-word reply matches that on its face. The
  subject-inheritance rule above it is written for *questions* with no subject, so
  the model never reached it. The refusal is now unavailable in any thread the
  oracle has already answered in, whatever the message looks like.
- **It emitted `**156.7MiB total**`.** The oracle is `deliveryMode: reply`, so it
  has no `lifecycle.postRun` hook and **nothing converts its Markdown** — the
  channel sidecar passes the text through as written. The rule was there and said
  "never `**like this**`", exhibiting the exact string it was banning. Same trap as
  `chatId: "{{ CHANNEL }}"`: a model this size copies what a prompt shows it. The
  rule now describes the failure without displaying the pattern.
- **It described SQL it never ran** — "joining pg_namespace with pg_tables" —
  which is the `#the-oracle-offered-sql-it-did-not-have` failure returning in
  narrative form rather than as an offer. The writing paragraph now bans
  describing a query as well as offering to run one.

The lesson under all four: **a rule the model breaks is usually in the wrong
paragraph or the wrong mood.** Three of these were present and correct, and lost to
position (scope rules read before the thread rules), to mood (prohibitions invite
the adjacent shape), or to exhibiting the thing they forbade.


## `security.refresh-period` does not reload the access-control rules

Trino's `access-control.properties` sets `security.refresh-period=60s`, and the
`file` access control did **not** pick up an edited `rules.json` — the `mcp` user
kept getting `Access Denied: Cannot access catalog postgresql_superset` well past
any refresh window, and every `postgresql_*` catalog was missing from
`list_catalogs` entirely. It took a coordinator restart. So a permission change to
this Trino is a **restart**, not a config reload, whatever the refresh period
claims; a `kubectl rollout restart` on the coordinator is part of the change, and
verifying one before the pod comes back reads as `connection refused` rather than
as a denial.

Two readings that look alike and are not, worth keeping apart when this breaks
again:

| Symptom | Cause |
| --- | --- |
| catalog missing from `list_catalogs` | access control denies it to `mcp` |
| `Access Denied: Cannot access catalog X` | same, reached by exact name |
| `FATAL: password authentication failed for user "viewer"` | the Postgres role |
| `connection refused` on `/v1/statement` | coordinator not up yet |

**Verified end to end after the restart**, which is the state the oracle's prompt
now describes: `list_catalogs` returns all six `postgresql_*` catalogs beside the
Iceberg ones; `list_schemas(postgresql_superset)` gives
`information_schema`/`pg_catalog`/`public`; `list_tables` gives 53 tables in 984
bytes, and 132 tables in 3,352 bytes for `postgresql_n8n` — the widest case here
and still inside a tool answer's budget; `get_table_schema` returns columns and
types; and `SHOW STATS FOR postgresql_superset.public.dashboards` answers.

Running it also corrected two things the prompt had asserted about `SHOW STATS`
without having seen its output. `row_count` sits on the one row whose
`column_name` is **`null`**, not "empty" — and `data_size` is `null` for most
columns on this connector rather than merely approximate. Both are now written
the way the result actually reads. That is the third time in this thread that a
prompt written from documentation was wrong in a way only the live call showed,
after the missing `TABLE(...)` wrapper and the `postgres_` versus `postgresql_`
catalog prefix: **never describe a tool result in a prompt until you have read
one.**


## The list was right and the count over it was not (2026-08-31)

The fourth ask of the same question — superset's tables and their sizes, 08:19 —
and the first one the oracle answered properly. All four fixes from
*It answered, then offered, then refused* held: it **printed all 53 table names**
rather than counting them, it did not offer, it described no SQL it had not run,
and it emitted no doubled asterisks. Diffed name by name against
`information_schema.tables` on the live coordinator: **no name missing, none
invented.**

One defect left, and it is arithmetic — or so this read at the time. Both of the
fixes below were then deployed and broken on the next run; see *Suppression is a
rule this model can follow; translation is not*. The list was headed
**"52 total tables"** over 53 correct names. Nothing was wrong with the data — the model counted its own
output and got it wrong by one, which is the operation a 4B model is worst at and
the one thing on that line no tool had given it. The previous fix made printing
the list mandatory; it did not make labelling it optional, so the model did both.
So the writing rule now ends the answer at the rows: **a total you worked out
yourself is a number no tool gave you**, which is the standing "invent no figure"
rule reaching the one place it had never been pointed — the model's own output,
rather than the cluster.

Worth naming as a pattern, because this is the second time in this thread:
**fixing a rule by making a behaviour mandatory adds a shape rather than
replacing one.** "Print the list" did not displace "state a count" any more than
"no offer to run something" displaced "describe the query in prose".

### Per-table bytes through Trino: closed, both routes, verified

The question is now settled rather than open, so nobody needs to rediscover it.
Both readings were run as the `mcp` user against the live coordinator *after*
core's rules change:

| Route | Result |
| --- | --- |
| `pg_class.relpages * 8192` via `postgresql_superset.pg_catalog` | `SHOW TABLES` there returns **zero rows** |
| `TABLE(postgresql_superset.system.query(query => ...))` | `Access Denied: Cannot execute function` |

The first one matters most, because it is the only route that needed **no core
change at all** and it looks available: `SHOW SCHEMAS` does list `pg_catalog`
beside `information_schema` and `public`. It is empty through Trino — the JDBC
connector reports `pg_class` as a `SYSTEM TABLE` and surfaces only `TABLE` and
`VIEW` — so `DESCRIBE ...pg_catalog.pg_class` is `Table does not exist`. **A
listed schema is not a readable one**, and this is a third instance of the
catalog-lookup trap in this section: the name resolves, the contents do not.

The second confirms that core's 08b5eef did *not* incidentally open the
passthrough. `{"user": "mcp", "catalog": "(memory|postgresql_.*|bronze|gold|silver|test)", "allow": "read-only"}`
scopes which catalogs are reachable; **a catalog privilege is not a function
privilege**, and the `system.query` EXECUTE grant is still a separate rule that
nobody has to add — the CNPG `customQueriesConfigMap` two sections up reaches the
same figures with history, no SQL composed by a 4B model, and no credential in
`agents/mcp/`. Prefer it and leave the passthrough denied.

Of the two things core owed here, the first is **done**: the `viewer` Postgres role
exists and every `postgresql_*` catalog answers with real rows. The second should
stay undone on purpose.

### A probe minutes stale reads as a denial

Recording the sequence because it cost a wrong conclusion and will recur.
`SHOW CATALOGS` returned **10** catalogs with no `memory` among them; four minutes
later, 11 with `memory` present. Nothing was flaky — core rolled the coordinator
in between, and the pod age (`...-89zn8`, 4m41s) is what said so. This is
*`security.refresh-period` does not reload the access-control rules* seen from the
other end: because a permission change here is a **restart**, the old state
survives intact right up to the roll, so a probe taken before it is not merely
out of date, it reads as a live denial. **Check the coordinator pod's age before
believing a negative from this Trino.**


## Suppression is a rule this model can follow; translation is not (2026-08-31)

The two fixes above went live — confirmed in the deployed object, not just in the
repo: `kubectl get ensemble homelab-responder -o json` showed the new no-total
sentence inside `spec.agentConfigs[].systemPrompt`. The very next run broke both.
It printed all 53 names again, correctly, and wrapped them in doubled asterisks,
asterisk bullets, **"(52 total)"** and a **"52 table names found:"** label. So the
count rule was not mispositioned or ambiguous; it was read and lost, and the
Markdown defect that the 08:19 thread had cleared came straight back.

**The answer was already written down in this repo, in code.** `files/deliver-slack.py`
opens by saying it: the prompt asks for plain Markdown and the *file* owns the whole
translation to Slack mrkdwn, because "asking a 4B model to emit mrkdwn directly did
not hold - `**bold**` and `##` arrived anyway." The five hook-mode reporters have had
a deterministic converter since that refactor. The oracle is `deliveryMode: reply`,
its text leaves through the `homelab-oracle-channel-slack` sidecar unaltered, and it
was being asked to do by prompt the exact thing that file records as not working.
**A lesson learned on one delivery path does not travel to the other by itself**, and
the reply path is the one with no code in it.

There is nothing to configure. The Ensemble CRD's `slackOptions` carries
`allowedTriggers`, `threading`, `threadStickiness` and the three `emojiOn*` fields
and **no formatting or mrkdwn option at all**, so conversion on the reply path is an
upstream change, not a values change (filed below).

What is left is the prompt, and the distinction the previous two attempts missed:

| Ask | Kind of task | Holds? |
| --- | --- | --- |
| emit Slack mrkdwn | translate one notation to another | no — `deliver-slack.py` |
| bold is one asterisk, not two | discriminate one character from two | no — twice |
| use no asterisk at all | suppress one character | plausible |

The old rule required the model to *count asterisks*, which is the same operation as
counting its own table names, and it fails at both. So the rule no longer asks for
bold: no asterisk anywhere, for emphasis or as a bullet, and a list opens with a
hyphen. **Deleting the requirement deletes the discrimination.** Likewise the count
rule stopped forbidding a placement — "do not head or close them with a total" was
answered with a total in *both* positions plus one inline — and now forbids the
quantity itself, wherever it appears. Prohibitions that name a position get the
other position; this is the third time in this thread that forbidding a shape found
the next shape.

Plain text is an acceptable answer here in a way it would not be for a scheduled
report: a Q&A reply degrades gracefully without bold, whereas a reporter's headings
carry the section structure the format demands. That asymmetry is why the two paths
can legitimately have different rules, and why the fix below is still worth making.

No validator rule was added for any of this. A regex asserting that a prompt
contains the right English is precisely what the ~600 lines removed with the MCP
server were, and it would pass on the prompt that just failed twice.


## The answer went nowhere and the narration was the reply (2026-08-31)

Asked "give me the status if stream and S3 services", the oracle answered twice and
the reader got neither answer. Both times what arrived in the thread was a report
*about* the answer - "The answer has been sent via Slack. I explained that ...",
then "I have delivered the answer about Stream (Redpanda) and S3 (Garage) service
status". The real text existed, was correct, and was thrown away.

The mechanism, from three logs that each show one half:

- `kubectl logs deploy/homelab-responder-homelab-oracle-channel-slack` at both run
  times: `failed to send Slack message  chatId:"" threadId:"" error: ...
  chat.postMessage rejected request: channel_not_found`.
- The run's agent log in Loki: the last call of each run is
  `send_channel_message args={"channel":"slack","text":"Stream/Redpanda: 3 brokers,
  3 topics, 18 partitions - all healthy ...` - the whole answer, in the argument of
  a call that was rejected.
- `status.result` on the `AgentRun`: the narration. **In reply mode `status.result`
  is the reply**, so the narration is what the controller posted into the thread.

**The posting instruction was a coin flip, and it only ever destroyed an answer.**
Five oracle runs on 2026-08-31: the three whose answers arrived intact
(`ch-lfr68`, `ch-2t8kj`, `ch-d4kbh`) never called `send_channel_message` at all -
they ended on their final text and the reply path delivered it. The two that obeyed
the prompt and called it (`ch-tgjxk`, `ch-t4kgs`) are exactly the two that were
lost. There was never a run in which the call helped.

So `send_channel_message` is off the oracle's allowlist, the prompt names no
posting tool and no delivery step. `scripts/validate.py` rejected the tool on a
`reply` persona the way it already rejected it on a hook one, and that check went
with the validator the same day — so an allowlisted `send_channel_message` now
renders and deploys, and this incident is repeatable. It is the cheapest thing to
put back as a `fail` in `templates/ensembles.yaml` if it recurs. **This is the hook
lesson arriving on the other path**, and the second time in two days that one has
had to walk over: `#deliverymode-hook-is-the-default-and-it-sidesteps-the-bus`
already said take the tool away and the report *is* the final text, and the reply
path had been left carrying both a tool call and an order to repeat its own text
afterwards. A model that has just "delivered" writes a delivery report as its next
turn; that is the whole failure.

Two notes on `chatId`, which the prompt had been trying to steer around by saying
to leave it unchanged. There is nothing to leave unchanged - a reply run resolves no
destination, the model emitted `chatId: ""`, and the tool answered `Message sent`
anyway (`#a-failed-outbound-send-is-only-visible-in-the-sidecar`). And the earlier
note that this was "confirmed working in production ... a real run called it with
`chatId: "C08S5ACNTPB"`" was one run's luck, not the contract.

The facts side of the same two runs was sound, which is worth separating out
because the report read like one failure:

- `ch-tgjxk` ran at 10:51, before `facts_stream_health`/`facts_object_store_health`
  reached its `toolsAllow` at 10:56, and fell through to six name searches for
  "stream service", "S3 service", "streaming", "streaming server" - the
  `#a-name-search-answers-what-it-is-called-never-what-it-does` failure again,
  landing on the unrelated `s3-gdrive` Service, and six lookups against a stated
  cap of three.
- `ch-t4kgs`, six minutes later with the tools wired, did it in four calls: thread
  read, `facts_stream_health`, `facts_object_store_health`, and the answer. Both new
  tools were called once, with no arguments, and answered. The two prompt bullets
  naming Garage and Redpanda worked on their first live question.

Also seen and not fixed here: `ch-2t8kj` and `ch-d4kbh` opened with `memory_search`
rather than the Slack read the prompt makes the first call of every run. The
ordering rule holds when the run is a thread follow-up and slips when the question
looks self-contained.


## Open, and not ours

- **The reply path has no Markdown converter, and should.** `lifecycle.postRun` gives
  the five hook-mode reporters `files/deliver-slack.py`, which is deterministic and
  tested; `deliveryMode: reply` goes out through the controller's
  `<persona>-channel-slack` sidecar, which passes the model's text through
  unconverted. The result is that the responder is the one persona whose Markdown
  reaches a reader as literal characters, and the only available remedy is prompt
  text asking a 4B model not to type asterisks. The sidecar is the right place for
  the conversion — one implementation for every reply persona, and the same
  Markdown-in/mrkdwn-out contract the hook already proves. Failing that, a
  formatting field on `slackOptions` would at least make it configurable; there is
  no such field today. Verified against the CRD and the live sidecar, 2026-08-31.

- **Restoring SQL to the responder is a core change.**
  `datahub-local-core-automation-sympozium-mcp-postgres` denies `execute_sql` in
  its catalog `spec.toolsDeny`, so no per-persona allowlist can bring it back. The
  server already runs `--access-mode=restricted`, which is where read-only was
  meant to be enforced; whether the deny on top of that is deliberate is a question
  for that repo. Lifting it would not help the size question anyway — that server
  holds one `DATABASE_URI` pointing at the empty `postgres` database.
- **`TargetDown{job="longhorn-backend"}` has been firing since the Longhorn
  v1.12.1 bump on 2026-08-24**: all five `longhorn-manager` pods answer
  `connection refused` on :9500 while the manager reconciles replicas normally. A
  scrape target left stale by the upgrade. The config lives in datahub-local-core.
- **One malformed request takes the postgres MCP server down.** A `tools/list` sent
  *before* `initialize` gets no reply from the FastMCP child, and core's stdio
  adapter — one child, one pipe, no per-request timeout — then blocks forever,
  including on `/healthz` and `/readyz`. The liveness probe kills the container
  about 40 s later and it comes back clean, so the blast radius is one restart and
  roughly a minute of every persona's `pg_*` tools timing out. Verified twice on
  `crystaldba/postgres-mcp:0.3.0` (restart count 0 -> 2, `Error/137`). The other
  four servers reject a pre-init request cleanly, so this is the adapter, not the
  protocol. The fix is a read deadline on the stdio adapter, or health handlers
  that do not share the child's lock. **Handshake properly** (`initialize`,
  `notifications/initialized`, then `tools/list`) when reading that server's
  manifest by hand.
