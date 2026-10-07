# Design

## Context

The bump is `0.10.87` → the target release. Every claim below about the target
chart was read on **2026-10-07** from the chart tarball and the registry, not from
release notes:

- `helm pull sympozium/sympozium --version 0.11.2` then diffed against
  `--version 0.10.87`. `0.11.3`'s chart is **not** in the repo yet
  (`helm search repo sympozium/sympozium -l` tops out at `0.11.2`), so the diff
  is `0.10.87` → `0.11.2`.
- `ghcr.io/v2/sympozium-ai/sympozium/{controller,apiserver,web-proxy}/manifests/<tag>`
  for tag existence.

Two halves move. **core** owns the pin, the upstream workarounds, the policies
and the kustomize patches. **here** owns the ensembles, personas, delivery and the
mounted MCP config. The split is the repo boundary, not a preference: the
control plane is a core release, and a persona is a `datahub-local-ai` object.

## 0. Gate findings — read first

Nothing is inferred. Where a fact could not be read, it is marked
`[UNVERIFIED]` and becomes a task, not an assumption.

| # | Finding | Evidence (2026-10-07) | Consequence |
|---|---------|-----------------------|-------------|
| 1 | **The chosen target `0.11.3` is not deployable.** | `helm search repo sympozium/sympozium -l` tops out at `0.11.2`; GHCR manifest for `controller`, `apiserver`, `web-proxy` at `v0.11.3` returns **404**, at `v0.11.2` returns **200**. | The pin is written to `0.11.3` per the user's decision, but **the apply is blocked** until the chart and all three images publish. `0.11.2` is the newest deployable release and is the fallback. |
| 2 | **One model key per Agent is enforced, and this fleet shares one Secret five ways.** | `0.11.0` release note; PR #650: owner recorded in `sympozium.ai/model-key-owner` — "one Agent, or the members of one Ensemble". | `values/default.yaml.gotmpl` names `litellm-auth-credentials` on all three ensembles; `templates/pi-render-session.yaml` names it on the `pi-render` Agent. Cross-Ensemble sharing is what the release refuses. **This is the change most likely to break the fleet.** |
| 3 | **`toolGating` is now enforced and `ask` is gone.** | `sympozium.ai_sympoziumpolicies.yaml` 0.11.2: `defaultAction` and rule `action` are `enum: [allow, deny]`, and the `ask` member is dropped. | The chart's built-in `permissive` policy is `defaultAction: allow` with no rules, so `policyRef: permissive` still yields the full tool surface. Core's two custom policies use only `allow`/`deny` and remain valid. A policy that used `ask` would now fail admission. |
| 4 | **Skill sidecars lose Secret reach, and a new admission policy refuses a workaround.** | New `templates/skill-secret-admission.yaml` in 0.11.2 (absent in 0.10.87): `ValidatingAdmissionPolicy` `skill-secret-references`, `failurePolicy: Fail`, denies `sympozium-run-*` accounts creating/updating workloads that mount a Secret (`volumes[].secret`, projected secret sources) or read one into the environment (`secretKeyRef`, `envFrom.secretRef`). Opt out per policy with `spec.skillPolicy.allowSecretAccess`. | No persona mounts a SkillPack today, so nothing breaks now. It becomes load-bearing the moment a SkillPack is mounted, and it is the reason `skillPolicy` must be a conscious field, not a default. |
| 5 | **The bundled PostgreSQL renders only under Celln mediation.** | New `templates/model-gateway-database.yaml` and the `sympozium.modelGatewayBundledDatabase` helper gate on `include "sympozium.cellnMediation"`. Core sets no `celln.mediation.enabled`. | No new workload, PVC or Secret appears in `automation` from this chart. If it ever does, it is a mediated-Celln install, not this fleet. |
| 6 | **The Agent CRD still carries no `toolPolicy` field.** | `sympozium.ai_agents.yaml` diff 0.10.87→0.11.2 is hook-`timeout` doc text only. | Core's `MutatingAdmissionPolicy` for policy-less `AgentRun`s (fix 6) is **still required**; the "drop once the Agent CRD carries toolPolicy" note has not come due. |
| 7 | **The network-policy and controller templates are byte-identical across the bump.** | `diff` of `templates/network-policies.yaml` and `templates/controller-deployment.yaml` 0.10.87→0.11.2 is empty. | Workarounds 1, 2, 3, 4 and 7 (eventbus/OTel/web-proxy/post-run network policy holes and the hardcoded NATS Service) are unchanged upstream and **stay**. |
| 8 | **The `web-endpoint` SkillPack still hardcodes `web-proxy:latest`.** | `files/skills/web-endpoint.yaml` line 84 unchanged; `webProxy.image` values exist but do not reach the SkillPack body. | Core's kustomize pin of the sidecar to `web-proxy:v{{ $sympozium_version }}` stays, and it now resolves to `v0.11.3` — gated on finding 1's 404. |
| 9 | **Hook `timeout` semantics changed; a postRun hook now bounds the Job.** | `sympozium.ai_agents.yaml` / `_ensembles` / `_agentruns`: postRun hook timeouts are summed into the Job deadline, never less than 10 minutes; not yet honoured on preRun hooks. | This fleet runs one postRun hook with no explicit `timeout`, so the change is documentation for us — but `MEMORY.md` must record it and the hook must be re-read, not assumed unchanged. |
| 10 | **The postRun hook's injected env is documented for only two of the vars `deliver-slack.py` reads.** | MEMORY.md, "the CRD documents only the first two" (`AGENT_RESULT`, `AGENT_EXIT_CODE`); the hook also reads `AGENT_RUN_ID` and `AGENT_NAMESPACE`. | `[UNVERIFIED]` for the target release. Re-read a live hook pod's environment before trusting the run-id line in the failure verdict. |
| 11 | **The built-in policy set changed in exactly one character.** | `templates/default-policies.yaml` diff: the restrictive policy's `execute_command` rule moves `ask` → `deny`. `permissive` and `network-isolated` are unchanged. | No fleet behaviour change from the built-ins, because the personas resolve `permissive`. Recorded so the next reader does not re-derive it. |
| 12 | **`SympoziumPolicy` was previously declarative-only for `toolGating`; that is now false.** | PR #631: the `MutatingWebhookConfiguration` that would have applied gating was never registered, so `deny`/`defaultAction` did nothing on a run without its own list; `0.11.0` applies the policy while building the pod, on both Job and sandbox paths. | `MEMORY.md`'s "probably moot rather than merely settled" note about `policyRef` is now wrong and must be corrected. The enforcement is schema-registration plus dispatch for the run's own list; the deny list joins the run's, and `defaultAction: deny` leaves only rule-allowed tools. |

## 1. Architecture — what moves, what does not

1. **The control plane is a core release; the fleet is a `datahub-local-ai`
   one.** The bump is applied in core. Nothing in this repo deploys the
   controller, apiserver or webhook.
2. **The MCP boundary is unchanged.** The `MCPServer` CRD is byte-identical
   across the bump; the four servers, their `toolsPrefix`, their mounted config
   and the read-only ClusterRole are untouched. `toolsAllow` remains the context
   budget and the server-side boundary.
3. **The delivery split is unchanged.** Hook for scheduled reporters, reply for
   the oracle, no `send_channel_message` on any persona. `lifecycle.postRun` is
   the same mechanism; only its timeout semantics are documented differently.
4. **Absence, no-clock and no-arithmetic survive.** No CRD in the bump adds a
   clock, a timezone field or a derived-value field. The report contract holds.

## 2. Core design

### 2.1 The pin and its gate

`values/_version.yaml` names `sympozium` at the target version; everything else
derives from it. `releases/automation/values/_kustomize.yaml.gotmpl` already
reads the pin back (`readFile "../../../values/_version.yaml"`) to build the
`web-proxy` tag, so the kustomize half follows the bump without an edit — which
is also why a pin pointing at an unpublished release fails at image pull, not at
render. The apply order is therefore:

1. write the pin;
2. `helmfile template` the automation release and confirm the `web-proxy` tag
   resolved to the target;
3. confirm the three images are pullable (finding 1);
4. apply, then read each workload back.

### 2.2 Workarounds: keep or drop, one row each

Each row stays a workaround unless its template changed. "Unchanged" is the
render diff, not the release notes.

| # | Workaround | Template at target | Decision |
|---|------------|--------------------|----------|
| 1 | `agent-allow-eventbus` omits shared memory and MCPServer | `network-policies.yaml` unchanged | keep |
| 2 | controller injects hardcoded `nats.sympozium-system.svc` | `controller-deployment.yaml` unchanged | keep |
| 3 | `allow-otel` selects `part-of=sympozium` | `network-policies.yaml` unchanged | keep |
| 4 | `web-proxy-allow-ingress` selects `component=web-proxy` | `network-policies.yaml` unchanged | keep |
| 5 | no `AgentRun` retention | CRD `agentruns` unchanged in this respect | keep |
| 6 | `AgentRun` default `toolPolicy` | Agent CRD still has no `toolPolicy` (finding 6) | keep |
| 7 | post-run hook egress | `network-policies.yaml` unchanged | keep |

The honest reading: **the whole file stays**. The file was written to be dropped
"as a group once fixed"; the target chart did not fix any of the seven in the
templates this fleet patches. The tasks re-run the diff rather than assume it.

### 2.3 Policies

- The enum is `allow`/`deny`; any `ask` fails admission. Core's
  `-hardened-agent-sandbox` and `-permissive-agent-sandbox` already comply and
  are re-validated by a server-side dry-run.
- `policyRef: permissive` resolves to the chart's built-in policy, which is
  `defaultAction: allow`, no rules → the reporter surface is unchanged. The
  fleet does **not** move to `restrictive` here: it denies `execute_command`
  *and* `read_file`-adjacent tools the reporters rely on, and the read-only
  posture is already enforced per-persona in `agents/sympozium/projects/`.
- `skillPolicy.allowSecretAccess` stays **off** (the default). No persona mounts
  a SkillPack; if one is ever mounted, this field is the decision point the new
  admission policy (finding 4) created, and it must be argued in `MEMORY.md`.

### 2.4 Kustomize patches

- NATS `Recreate` — unrelated to the bump; keep.
- `web-proxy` sidecar pin — keep; now resolves to the target tag (finding 8).
- `k8s-ops` read-only `clusterRBAC`/`rbac` — unrelated to the bump; keep. Note
  finding 4's default already removes `secrets`, `pods/exec` and `pods/attach`
  from skill RBAC, which is a second wall behind this one.

## 3. Here design

### 3.1 One key per Agent or Ensemble

Finding 2 forces the shape. The fleet needs one model route, so the options are:

- **Per-Ensemble Secret** (one `litellm-auth-credentials` per ensemble, e.g.
  `litellm-auth-credentials-homelab-ops`, `…-responder`, `…-reviewer`), copied
  from the one source Secret. Each is owned by exactly the members of its
  Ensemble; the secret value is injected from core's `_security` values, not
  committed here.
- **One key, one owner, four consumers** — only works if the target's
  `model-key-owner` check is satisfied by a single Ensemble, which it is not,
  because `pi-render` is a fourth, separate Agent.
- **A shared `ModelConnection`** rather than per-Agent `authRefs` — a larger
  change to the provisioning path; out of scope unless the per-Ensemble Secret
  is refused.

The default decision is the per-Ensemble Secret, because it is the least change
and it matches the owner semantics ("the members of one Ensemble"). The exact
Secret names are written by the apply, injected through core's security values;
this repository names them and never carries a value.

`pi-render`'s Agent is not a member of an Ensemble, so it takes its **own**
Secret and its own owner. The `AgentRuntime`'s `authSecretRef` and the Agent's
`authRefs` must point at the same new Secret.

### 3.2 The re-verification list

`MEMORY.md` has accumulated "re-check after a control-plane bump" items. They are
tasks, not prose, and each closes with what was measured:

| Item | Where | What to read |
|------|-------|--------------|
| CRD-defaulted fields | `MEMORY.md` §"Ensemble-level decisions" | `kubectl get crd ensembles.sympozium.ai -o json \| jq '.. \| objects \| select(has("default"))'`; write any new default out in source. |
| postRun hook env | `MEMORY.md` §"Every report arrived five times" | a live `<run>-postrun-*` pod's environment; confirm `AGENT_RUN_ID` and `AGENT_NAMESPACE` (finding 10). |
| Provider-key env names | `MEMORY.md` §"The oracle runs on OpenRouter" | `API_KEY`/`OPENAI_API_KEY` versus `PROVIDER_API_KEY`; the two lists disagreed at `v0.10.48`. |
| MCPServer tool counts | `MEMORY.md` §"Verify names against the running system" | `kubectl logs <run-pod> -c mcp-discover` — **18** and **5** today; a whole server failing is silent. |
| `policyRef` is now enforced | `MEMORY.md` §"`SympoziumPolicy.toolGating` looks like the fix" | this note is stale (finding 12); correct it. |
| Agent Sandbox propagation | `MEMORY.md` §"the Agent Sandbox gate" | schedule- and channel-created runs still take the Job backend under `permissive`; re-confirm from a pod, not the `Agent`. |
| Delivery hook | `agents/sympozium/tests/test_deliver_slack.py` | the hook tests, offline; then one hand-applied `AgentRun` streamed live. |

## 4. Risks

| Risk | Mitigation |
|------|------------|
| Pin lands before the images exist → every run fails image pull | The gate in §2.1; `0.11.2` fallback; the pin is one line to revert. |
| The one-key change is applied in the wrong direction (four Secrets, or none) | §3.1 decides per-Ensemble; a hand-applied `AgentRun` per ensemble proves the route before any schedule runs. |
| `toolGating` enforcement quietly removes a tool a reporter uses | `policyRef: permissive` does not gate; the per-persona `toolPolicy`/`toolsAllow` mirror is re-diffed and the render gate already fails the allowlist half. |
| Skill secret admission breaks a future SkillPack mount | `skillPolicy.allowSecretAccess` named as the deliberate gate; no mount in this change. |
| A CRD default is written into the live object and shows as permanent ArgoCD drift | Re-derive the defaulting list (§3.2) and write every value out; `kubectl diff` cannot see this class. |
| Editing personas while the bump lands hides which change broke what | The bump is applied first, verified with a hand-applied run, and persona edits are a separate, reviewable step. |

## 5. Open questions

- Does the target release accept one fleet-wide key when the Agents are
  provisioned through `authRefs` rather than Celln mediation, or is
  `model-key-owner` enforced for this path too? This decides between "four
  Secrets" and "no change" and is the first task to run.
- Is `0.11.3` published (chart and images) before this work starts, or does the
  pin land at `0.11.2` and follow to `0.11.3` when it does? Determined by
  finding 1 at apply time.
- Does the enforced gating change what `toolsAllow` can narrow, or only what
  `policyRef` denies? The two mechanisms are adjacent; the render gate and a
  probe run answer it.
- Whether spec 004's **AI-12** (delegation) should be revisited now that
  `delegate_to_persona` is subject to policy gating — deliberately not in this
  change, since the responder still has no second persona.

## 6. Definition of done

- The pin in core names a release whose chart and images are published; the
  `web-proxy` kustomize tag resolves to it.
- Every workaround in `sympozium_upstream_fixes.yaml` is either kept with a
  render-diff reason or dropped with one.
- No model-key Secret is shared across Ensemble boundaries; each ensemble and
  `pi-render` runs one hand-applied `AgentRun` on its own route.
- `helmfile template` renders (both repos), `openspec validate` passes, and the
  sympozium hook tests and `ruff` pass.
- `MEMORY.md` carries the bump entry, the corrected `policyRef` note, the hook
  timeout change and every closed re-check item with what was measured.
- `docs/specs/` is gone and every live pointer resolves into `openspec/`.
