# Sympozium Agents on the Hosted Model — Design Spec

> **Fourth spec on disk, and the first about the agents.** It extends none of the
> others; the three before it are
> [`001-bodega-spec.md`](001-bodega-spec.md),
> [`002-01-semantic-layer.md`](002-01-semantic-layer.md) with its phase
> [`002-02-semantic-layer-location.md`](002-02-semantic-layer-location.md), and
> [`003-data-quality-and-lineage.md`](003-data-quality-and-lineage.md).
>
> **Numbering:** filenames carry the file number, the prose carries the logical
> one. This is `004-` on disk and the fourth distinct topic.

---

## 0. Gate findings — read first

Three things were unknown when this work started. Two are `[UNVERIFIED]` and
shape what may be changed without a cluster.

| Unknown | State | Consequence |
|---------|-------|-------------|
| Effective context at the LiteLLM gateway | `[UNVERIFIED]` — the old 90K described Ollama, the old 65536 the local model | Budgets and allowlists are loosened modestly; no prompt relies on a number we have not measured. Re-measure from a run log. |
| Whether `workflowType: delegation` works on this control plane and model | `[UNVERIFIED]` — never run | **Not enabled.** Staged in §7 with a probe runbook; the source stays `autonomous`. |
| Whether a stronger model removes the need for the evidence guards | Partly known | It does not. MEMORY.md is explicit that the guards were tool-loop fixes, not 4B workarounds. Only the small-model posture is relaxed. |

The MCP repository is not checked out beside this one, so §6's rule 12 applies:
no new tool name may be added unless it was already verified in this repository.
Every added name below was read off a persona file that recorded a live
`tools/list`.

---

## 1. Context

`c97ddf7` moved all three ensembles from the cluster-local `qwen3.5:4b` to the
LiteLLM gateway in `data`, model `opencode-go/deepseek-v4.1-flash`, with
`opencode-go/glm-5.3-flash` as the router fallback. `agents/sympozium/MEMORY.md`
records that the surrounding design — 5–11 tool allowlists, 30m/45m timeouts,
`MAX_TOOL_ITERATIONS`, three-lookup caps, rigid section counts, the literal-PromQL
rule, `workflowType: autonomous` — was sized for one shared GPU and a 4B model,
and flags it `[UNVERIFIED]` as to whether it still binds.

The model is now stronger and not on the single-GPU queue. The agents should spend
that on deeper investigation, a wider read-only surface and new jobs, without
giving back the deterministic layer that made reports trustworthy.

## 2. Goals and acceptance signals

| # | Goal | Acceptance signal |
|---|------|-------------------|
| G-1 | Reporters investigate deeper | Every reporter prompt carries a named cap (six per subject) and a named exit, and a correlation step where a read-only source server is wired. |
| G-2 | New instrumented readings are used | `endpoint-warden` queries `node_systemd_unit_state`, `node_apt_*` and `node_reboot_required`; `workload-watch` queries resource pressure. |
| G-3 | Cross-source explanation | `sre-sentinel` may reach ArgoCD; `gitops-auditor` may reach GitHub to name the commit behind drift. |
| G-4 | The small-model posture is relaxed | Prompts no longer read as "caveman"; caps are larger; a persona with `facts_promql` may write an expression. |
| G-5 | Allowlist drift is gated at render | `helmfile template` fails when `toolsAllow` and `toolPolicy.allow` disagree. |
| G-6 | The evidence guards survive | Absence, literals, no-clock, no-arithmetic, `labelSelector` ban and the delivery split are untouched. |

## 3. Architecture — what does not move

The facts server still gathers and derives; the model still transcribes. The
change is budget and reach, not the division of labour. Four structural
properties are unchanged by this spec:

1. **`toolsAllow` is the boundary**, enforced at the MCP bridge. `toolPolicy.allow`
   is the LLM-side filter and remains mirrored to it; the new render gate keeps
   the mirror honest.
2. **Absence is a value** — `unavailable`, `n/a`, `not found with <call>`,
   `ERROR:`, `cause not determined` — and every report section may hold one.
3. **No clock and no arithmetic.** Nothing returns the current time; a derived
   quantity is computed in code, not on top of two correct readings.
4. **Delivery is split** — hook for scheduled reporters, reply for the oracle, no
   `send_channel_message` on any persona.

## 4. Design

### 4.1 The render gate

`templates/ensembles.yaml` fails the render when, for any persona:

- an `mcpServers[].toolsAllow` entry, prefixed by that server's `toolsPrefix`,
  does not appear in `toolPolicy.allow`; or
- an MCP tool in `toolPolicy.allow` is not registered by any `toolsAllow`.

Built-in tools (`memory_search`, `memory_store`, `fetch_url`,
`send_channel_message`) are named in the template as exempt. This is a check of
one file against itself, not a mirror of the cluster, so it does not carry the
staleness cost MEMORY.md rule 17 warns about. The documented home for a check
like this is the render, not a new validator.

### 4.2 Prompt posture

Keep the compact, literal, imperative style. Relax only the absolutes:

- reporters move from three to six lookups per subject; the oracle from three to
  six, and from four to seven on a `semantic_*` question;
- a persona given `facts_promql` may write a complete expression when no facts
  tool covers the reading, and must still report `No series matched` as no data;
- a persona given a read-only source server may use it to explain a finding it
  already has, not to answer a fresh question.

Unchanged in every prompt: the no-result literals, the no-arithmetic rule, the
no-invented-number/date rule, the `labelSelector` ban, the read-then-write phase
in the reviewer, and the delivery contract.

### 4.3 Tool surface

Only already-verified names are added:

| Persona | Added | Purpose |
|---------|-------|---------|
| `sre-sentinel` | `argocd_get_application`, `argocd_get_application_events` | relate a firing alert to the app that owns it |
| `gitops-auditor` | `github_get_file_contents`, `github_list_commits`, `github_search_code` | name the commit behind drifting state |
| `workload-watch` | `k8s_resources_list` | HPA and other workload objects; resource pressure via `facts_promql` |
| `db-steward` | `facts_promql` (restored) | store-level depth without returning SQL to the model |
| `renovate-reviewer` | `github_search_code`, `argocd_get_application` | check the deployed app beside the bump |

`facts_promql` is not added to a persona whose prompt does not name it; that was
the state `db-steward` was cleaned of on 2026-08-31 and the same budget argument
holds.

## 5. Implementation plan

- [x] **AI-1** Render gate for `toolsAllow` ↔ `toolPolicy.allow` in
  `templates/ensembles.yaml`.
- [x] **AI-2** README prompt/context section rewritten for the hosted model;
  effective context marked `[UNVERIFIED]`.
- [x] **AI-3** `sre-sentinel`: six-lookup cap, ArgoCD correlation, `argocd` server.
- [x] **AI-4** `endpoint-warden`: systemd/apt/reboot/PSI/EDAC readings and a
  Maintenance section, via named `facts_promql` expressions.
- [x] **AI-5** `db-steward`: `facts_promql` restored; six-call depth.
- [x] **AI-6** `gitops-auditor`: six-call depth and GitHub source correlation.
- [x] **AI-7** `service-janitor`: six-call accumulation depth. OS-update and reboot
  readings were deliberately left to `endpoint-warden` rather than duplicated; the
  janitor stays cluster-side (certificates, tokens, secrets, backups, cleanup).
- [x] **AI-8** `workload-watch`: `k8s_resources_list`, resource-pressure section,
  six-call budget.
- [x] **AI-9** `homelab-oracle`: caps raised, free-form PromQL permitted where no
  facts tool answers.
- [x] **AI-10** `renovate-reviewer`: read budget raised, `github_search_code` and
  `argocd_get_application` added, comment idempotency reinforced.
- [x] **AI-11** Evals extended for the new behaviours; MEMORY.md records the
  model-era rationale and the open `[UNVERIFIED]` items.
- [ ] **AI-12** (blocked) Enable `workflowType: delegation` on one ensemble after
  a probe. Runbook in §7. **Do not enable from this repository alone.**

## 6. Risks

| Risk | Mitigation |
|------|------------|
| No live verification of prompt/budget changes | Structural guards kept; delegation held; probe runbook written. |
| Allowlist drift while editing | AI-1 fails the render; CI renders through helmfile. |
| Context smaller than expected at the gateway | No prompt depends on a measured number; caps raised modestly. |
| Prompt bloat creeping back | One job per persona; deterministic text stays in the facts server. |
| A new tool that does not exist fails silently | Rule 12: only names already verified in this repository are added. |

## 7. Delegation staging (AI-12, blocked)

Do not set `workflowType: delegation` on instinct. Probe first:

1. Hand-apply an `AgentRun` with `spec.model` set to the gateway and
   `systemPrompt` from the candidate manager persona, asking it to hand one
   subtask to a named reporter.
2. Stream `kubectl logs <pod> -c agent -f`; the success signal is a
   `delegate_to_persona` tool call with a coherent payload and a returned child
   result.
3. Only then change `workflowType` in `projects/<ensemble>/ensemble.yaml`, and
   re-probe with a hand-applied run before letting a schedule use it.
4. If delegation works, the natural home is `homelab-responder` (one inbound
   question, many possible expertises), not the scheduled reporters — a failed
   delegated run ends `status: error` and the `postRun` hook never fires.

## 8. Open questions

- The effective context at the gateway, and whether `runTimeout` still binds.
- Whether `db-steward` should gain Trino structure tools; deliberately omitted
  here because it would put SQL composition back in the model.
- Whether the missing `#monitoring-ai-runs` producer belongs in an n8n workflow
  or a core alert.

## 9. Definition of done

- `helmfile template` renders all three ensembles; the render gate passes.
- `pytest agents/sympozium/tests/` and `ruff` pass.
- Every changed prompt was read against its persona's `toolsAllow`.
- `MEMORY.md` carries the new rationale and the `[UNVERIFIED]` items.
- `workflowType` is still `autonomous` on all three ensembles until AI-12's probe
  passes.
