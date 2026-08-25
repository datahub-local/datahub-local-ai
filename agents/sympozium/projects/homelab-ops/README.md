# homelab-ops

Five read-only reporters, one question each. None is channel-bound: they deliver
through a `lifecycle.postRun` hook, so no inbound Slack message can start a run
here. The Slack Q&A surface is `../homelab-responder/`, split off because it is
the only inbound path.

Each persona calls one or two facts tools and writes the answer up. The
gathering is `../../../mcp/projects/homelab_facts/` — the readings arrive already
correct, so these prompts are a report contract and nothing more.

| Persona | Facts tools | Question |
| --- | --- | --- |
| `sre-sentinel` | `alerts_snapshot`, `volume_fill` | What is firing that is new, and what is filling up? |
| `endpoint-warden` | `node_fleet` | Is any machine unwell? |
| `db-steward` | `postgres_health`, `cache_health` | Are the stateful services healthy? |
| `service-janitor` | `backup_freshness`, `cert_expiry` | Is the homelab recoverable, and what expires soon? |
| `gitops-auditor` | `argocd_drift` | Does the cluster match git? |

Why the knobs are set the way they are: `../../MEMORY.md`.
