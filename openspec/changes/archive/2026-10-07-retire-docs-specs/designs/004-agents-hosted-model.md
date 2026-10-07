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

Three things were unknown when this work started. Delegation has since been
probed and verified; the gateway context is still `[UNVERIFIED]` and shapes what
may be changed without a cluster.

| Unknown | State | Consequence |
|---------|-------|-------------|
| Effective context at the LiteLLM gateway | `[UNVERIFIED]` — the old 90K described Ollama, the old 65536 the local model | Budgets and allowlists are loosened modestly; no prompt relies on a number we have not measured. Re-measure from a run log. |
| Whether `workflowType: delegation` works on this control plane and model | Verified 2026-09-13: **yes** (`v0.10.61`, `deepseek-v4.1-flash`) | **Still not enabled in source.** The probe passed in a throwaway ensemble; §7 records the evidence and the same-pack constraint that keeps the source `autonomous` for now. |
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
- [ ] **AI-12** Enable `workflowType: delegation` on one ensemble. The probe ran
  and passed on 2026-09-13 (evidence in §7); enabling is held because the
  responder has no second persona to delegate to. **Do not enable from this
  repository alone.**
- [x] **AI-13** Deterministic status line in `files/deliver-slack.py`; a
  `Verdict` class and its tests. The oracle and the reviewer take no line. §7a.
- [x] **AI-14** First full eval replay, 44 questions, 2026-09-13: all runs
  succeeded, 33/36 self-contained full pass after fixing four scorer defects.
  One real finding: ambiguity is answered rather than asked (fixed by AI-15).
  Rationale in `agents/sympozium/MEMORY.md`.
- [x] **AI-15** Ambiguity fix, 2026-09-13: the clarify branch in
  `03_scope.md` states its own trigger (no antecedent, or a class with more than
  one member) and carves out class-ranging questions, so it is no longer
  overridden by "prefer a lookup"; `02_conversation.md` forbids guessing the
  likeliest subject. `ambiguous` and `elliptical-no-subject` now ask with zero
  tool calls; eight neighbouring questions re-run clean, and the chart renders.

## 6. Risks

| Risk | Mitigation |
|------|------------|
| No live verification of prompt/budget changes | Structural guards kept; delegation held; probe runbook written. |
| Allowlist drift while editing | AI-1 fails the render; CI renders through helmfile. |
| Context smaller than expected at the gateway | No prompt depends on a measured number; caps raised modestly. |
| Prompt bloat creeping back | One job per persona; deterministic text stays in the facts server. |
| A new tool that does not exist fails silently | Rule 12: only names already verified in this repository are added. |

## 7. Delegation staging (AI-12)

**Probe: passed 2026-09-13.** A throwaway two-persona ensemble (`manager` →
`worker`, `workflowType: delegation`, one delegation edge) in a disposable
namespace, on control plane `v0.10.61` and `opencode-go/deepseek-v4.1-flash`,
produced the full signal:

    tool call: delegate_to_persona args={"targetPersona": "worker", "task": "Reply with exactly: PROBE-OK ..."}
    Delegation to "worker" succeeded (8 bytes)
    status.delegates: [{childRunName: sub-<run>-1, phase: Succeeded, result: PROBE-OK, targetPersona: worker}]
    status.result: PROBE-OK

The runner logged `relationship context injected for persona manager` before the
call and the run passed through `AwaitingDelegate`; the child's result returned
verbatim. No prompt coaxing was needed beyond naming the tool.

**What the probe adds: a same-pack constraint.** `delegate_to_persona` is
registered on any ensemble Agent, but the Spawner validates the edge against the
delegator's own Ensemble, so a reporter in `homelab-ops` is not a legal target
from `homelab-responder`. The natural home is still the responder — one inbound
question, many possible expertises, not the scheduled reporters — but it must
first gain a second persona to delegate to. That is a design step, not a config
flip, which is why the source stays `autonomous`.

Remaining steps, when such a target exists:

1. Add the target persona to `homelab-responder` and a `delegation` relationship
   edge from the oracle to it.
2. Set `workflowType: delegation`, apply once, and re-probe with a hand-applied
   `AgentRun` before a schedule or channel can use it. A failed delegated run
   ends `status: error` and the `postRun` hook never fires, so the probe is not
   optional.

## 7a. Message formatting: a deterministic status line (AI-13, landed)

The reports are correct and read poorly. With a stronger model the fix is a
consistent, scannable shape, and the one field that must never be left to the
model is the top-line verdict.

**Decision:** `files/deliver-slack.py` owns the status line. A `Verdict` class
classifies the **converted** report from its own sections and prefixes an
emoji-bearing line to the `Status:` line the model already writes. The model
never emits an emoji.

Classification, in order:

- `ERROR` (red circle) if any line carries the `ERROR:` literal;
- `WARNING` (warning sign) if a finding-bearing section is not one of its
  "nothing" forms, or if `Still firing` names an alert whose line does not say
  `chronic`;
- `OK` (white check) otherwise.

`Still firing` is excluded from the blanket rule because chronic alerts fire
permanently here — treating a chronic-only run as a warning would warn every
run. A `REAL-chronic` or unclassified entry lifts it out of OK, which is the
2026-09-13 shape where the real finding sat inside that section.

**Scope, settled:** the six scheduled reporters, whose reports have a `Status:`
section. `homelab-reviewer` posts a PR comment and keeps its Markdown. The
oracle answers questions, not findings — "what URL is grafana on?" has no
verdict — so it takes no status line and its prompt is unchanged.

Tests live beside the Markdown tests in `tests/test_deliver_slack.py`; the
classification cases are the shapes live reports actually produced.

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
