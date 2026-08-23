# homelab-ops

Five read-only agents whose shared job is answering whether the homelab is
actually *correct* — not whether it is busy. None of them has a write tool.

| Persona | Type | Schedule (UTC) | Skills | MCP |
| --- | --- | --- | --- | --- |
| `sre-sentinel` | heartbeat | every 30m | `sre-observability`, `memory` | `grafana`, `k8s` |
| `gitops-auditor` | sweep | every 1h | `k8s-ops`, `memory` | `argocd` |
| `endpoint-warden` | scheduled | `30 4 * * *` (06:30 Madrid) | `sre-observability`, `memory` | `grafana`, `k8s` |
| `db-steward` | scheduled | `30 5 * * *` (07:30 Madrid) | `k8s-ops`, `memory` | `pg`, `grafana`, `k8s` |
| `service-janitor` | scheduled | `0 5 * * 1` (Mon 07:00 Madrid) | `k8s-ops`, `memory` | `k8s`, `grafana` |

Cron is UTC — no Sympozium CRD carries a timezone — so the local times above
shift by an hour between CET and CEST. The daily ones are deliberately an hour
apart: one GPU with one resident model means concurrent runs queue behind each
other.

## What each one is for

**`sre-sentinel`** — the on-call engineer, and the only agent on a fast cadence.
It works from `ALERTS{alertstate="firing"}` rather than a checklist of its own,
then root-causes whatever is new. The hard part here is noise: most of what fires
in this cluster fires constantly, so the report is shaped as *new / still firing
/ resolved* and the chronic set lives in memory seeds. It also checks the thing
nothing alerts on early enough — PersistentVolumeClaims filling up, via
`kubelet_volume_stats_*` — because a volume filling slowly is the most common way
a homelab app dies.

**`gitops-auditor`** — the highest-value one for correctness. Everything here is
deployed by ArgoCD from the `datahub-local-*` repositories, so "the cluster
disagrees with git" is the most useful question you can ask, and ArgoCD answers
it in one call. It treats OutOfSync-but-Healthy as drift, and drift that survives
two runs as the real finding — a single sighting is usually a sync in progress.
Renovate PRs and repository health belong to `renovate-reviewer`, not here.

**`endpoint-warden`** — the hardware technician. Not workloads: the boxes. Its
best signal is **PSI** (`node_pressure_*`), which measures how long tasks were
actually blocked — the honest version of "the machine feels slow", and the
classic dying-disk symptom. Then SMART health and SSD wear, EDAC memory-error
counters (failing RAM announces itself early if anyone is counting), temperature,
IO saturation, kernel drift, and the UPS. It has no host access, so systemd units
and pending OS updates are out of reach; see
[what the agents can see](../../README.md#what-the-agents-can-see-and-what-they-cannot).

**`db-steward`** — the DBA, split out of the janitor because databases need a
different toolset and a different cadence. `pg_analyze_db_health` for internals,
`cnpg_*` metrics for operational state, `redis_*` for Valkey (the exporter does
not publish `valkey_*`, which is exactly the kind of detail a small local model
cannot guess), and volume growth rates for capacity. Its single most important
number is `cnpg_pg_stat_archiver_failed_count`: broken WAL archiving means
point-in-time recovery is gone while every backup still reports success.

**`service-janitor`** — continuity and housekeeping, scope deliberately small.
Four backup systems run here (Velero, CloudNativePG, Longhorn, Kopia ×5) and each
is checked on its own terms, because a backup system that stopped is worse than
one that never existed — everybody assumes it is working. Then certificate and
token expiry inside 21 days, then accumulation. It reports cleanup commands and
never runs them. n8n credential expiry is out of scope and belongs to
`agents/n8n/workflows/credentials_expiry_review`.

## Shared memory

`sharedMemory` is on (512Mi) so the personas can see each other's notes; the
warden's IO-stall trend is the explanation for the steward's slow queries. Each
persona also keeps private memory, seeded with the judgement calls we do not want
re-litigated every run — which alerts are chronic artifacts, that Valkey is
scraped as `redis_*`, that three nodes legitimately report no SMART data.

`workflowType` is `autonomous`, not `delegation`, and each persona is one
question with five to seven tools — see
[the model constrains the design](../../README.md#the-model-constrains-the-design).

## Notification

All five post with `send_channel_message`, using the `mcp-slack-token` secret
named in `channelConfigs`. Where they post, how much they say and whether they
say it at all come from the `sympozium_delivery` tree in
[values/default.yaml.gotmpl](../../values/default.yaml.gotmpl), substituted into
each system prompt's `{{ DELIVERY }}` token at render time — no CRD field
carries a destination, so prompt text is the only route there is.

That token expands to three files: `prompts/delivery/header.md`, then the chosen
`delivery/<verbosity>.md` and `notify/<level>.md`. The header is what puts the
agent's name on the message — five personas producing a Status line and a few
bullets each are otherwise indistinguishable once they land in a channel. It
also states that the agent has no clock, because nothing in this fleet returns
the current time and an invented timestamp on an ops report is worse than none;
Slack's own message stamp is the run time.

The destination goes in the tool's `chatId` argument, *not* its `channel`
argument, which names the transport (`slack`). The prompts had that backwards
until 2026-08-23 and every scheduled report was silently dropped —
[the write-up](../../README.md#send_channel_message-takes-the-destination-in-chatid-not-channel)
is worth reading before touching these files.

| Persona | Channel | notify |
| --- | --- | --- |
| `sre-sentinel` | `#monitoring-ai-alerts` | `onChange` |
| `gitops-auditor` | `#monitoring-ai-drift` | `onChange` |
| `endpoint-warden`, `db-steward`, `service-janitor` | `#monitoring-ai-health` | `always` |

**Split by what a reader would do about it, not by who produced it.** A channel
is really one notification setting, so mixing the 30-minute alert stream with
the daily hardware report means either the report wakes you or the alert does
not. Keeping them apart is what lets `-alerts` keep notifications on.

**`onChange` is not a detail — it is what makes `-alerts` usable.**
`sre-sentinel` runs every 30 minutes and `gitops-auditor` hourly against a
cluster where most findings are permanent; posting every run is 48 and 24
messages a day of mostly the same content. Each of those two carries a *What
counts as a change* section defining its own test — the criteria are
persona-specific and cannot live in the shared `prompts/notify/onchange.md`, and
the validator fails a persona set to `onChange` without one. The report is still
written on a quiet run; it is only the message that is skipped.

`verbosity` (`quiet`/`normal`/`verbose`) is the other axis: how much of the
report goes in the message. It is deliberately separate from `notify`, and each
level is written in countable terms — *at most five bullets*, *drop the recap
sections* — because a 4B model does nothing useful with "be concise".

Binding a channel also opens an inbound path — a Slack message can start an
`AgentRun` — so `slackOptions.allowedTriggers` is `[mention]` on every persona.
These five hold no write tool, so an unwanted run costs GPU time and nothing
else; `renovate-reviewer`, which can comment on pull requests, is deliberately
not bound. See [Known gaps](../../README.md#known-gaps) for what is still
unverified about the Slack path.

All five also answer over HTTP, so a run can be started without waiting for its
cron — see
[testing an agent over HTTP](../../README.md#testing-an-agent-over-http). That is
switched on from `sympozium_web_endpoint` in values rather than per persona, for
the same reason `renovate-reviewer` is left out of it: which agents have a
trigger in front of them is a per-cluster decision and belongs where it can be
read in one place.
