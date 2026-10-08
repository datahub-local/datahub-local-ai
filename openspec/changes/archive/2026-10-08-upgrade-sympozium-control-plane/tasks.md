# Tasks

Cross-repo: `CORE-*` are `datahub-local-core`; `SEC-*` are
`datahub-local-secrets`; `HERE-*` are this repository; `DOC-*` is the
`retire-docs-specs` change. `blocked by` links are real — do not start a blocked
task.

**Progress 2026-10-08:** landed at `0.11.2` and **applied live** (controller,
apiserver and webhook all at `v0.11.2`; ensembles Ready). The one-key fix is in
three repos and every owner has run once on its own Secret. All tasks closed; the
`0.11.3` follow-up is the only thing left, and it is gated on that release's chart
and images publishing.

## 1. Gate the target (before anything else)

- [x] 1.1 (`CORE`) Confirm the target release is deployable in full. Result:
  `0.11.3` is **not** — the chart repo tops out at `0.11.2` and
  `ghcr.io/sympozium-ai/sympozium/{controller,apiserver,webhook,web-proxy}:v0.11.3`
  each answer 404 against `v0.11.2`'s 200. The pin landed at `0.11.2`; `0.11.3`
  is the follow-up. Recorded in `MEMORY.md`.
- [x] 1.2 (`HERE`) Read the target's `internal/modelkey/modelkey.go`: the
  `authRefs` path IS gated. `Owner` is `Ensemble/<name>` for an ensemble member,
  else `Agent/<name>`; a second owner gets `ConflictError`, an ungranted Secret
  gets `NotGrantedError`. So per-owner Secrets are required. Recorded in
  `MEMORY.md`.

## 2. Core: the pin, the workarounds, the policies (blocked by 1.1)

- [x] 2.1 (`CORE`) Pinned `sympozium` at `0.11.2` in `values/_version.yaml`.
  `helmfile template` resolves `ghcr.io/sympozium-ai/sympozium/web-proxy:v0.11.2`
  in the rendered `SkillPack/web-endpoint`, and `controller`/`apiserver`/`webhook`
  also render at `v0.11.2`.
- [x] 2.2 (`CORE`) Chart diff 0.10.87→0.11.2: `templates/network-policies.yaml`
  and `templates/controller-deployment.yaml` are byte-identical; the Agent CRD
  still has no `toolPolicy`. All seven workarounds stay — no edit.
- [x] 2.3 (`CORE`) `sympozium_policies.yaml` uses only `allow`/`deny`, which is
  the target enum; no change needed. The personas resolve `policyRef: permissive`
  (`defaultAction: allow`, no rules), so their surface is unchanged. (`--dry-run=server`
  against the target CRD deferred with the live apply.)
- [x] 2.4 (`CORE`) Kustomize patches re-verified at the new `$sympozium_version`:
  the NATS `Recreate` and `k8s-ops` RBAC are version-independent; the `web-proxy`
  pin now reads `v0.11.2`.
- [x] 2.5 (`CORE`) The only new chart object in `automation` is the
  capability-gated skill-secret `ValidatingAdmissionPolicy` (finding 13); the
  bundled PostgreSQL does not render (Celln mediation off).

## 3. One key per owner (blocked by 1.2)

- [x] 3.1 (`HERE`) Named one model-key Secret per ensemble in
  `agents/sympozium/values/default.yaml.gotmpl` (`authRefs[].secret`) and one for
  `pi-render` (`sympozium_pi_render.model.authSecret`). No value is in this repo.
- [x] 3.2 (`HERE`) N/A — the `authRefs` path IS gated (1.2), so the change was
  required, not skipped.
- [x] 3.3 (`HERE`) `templates/pi-render-session.yaml` reads
  `$s.model.authSecret` for both `AgentRuntime.spec.model.authSecretRef` and the
  Agent's `authRefs[].secret`; both now resolve to
  `litellm-auth-credentials-pi-render`. `agents/adapters/pi-render/deploy/session.yaml`
  updated the same way.
- [x] 3.4 (`SEC`) Provisioned the four Secrets in
  `datahub-local-secrets/release/values/default.yaml.gotmpl`, each fanning to
  `automation` only, from the same `litellm-root` master key. Additive: the
  shared `litellm-auth-credentials` keeps its `automation` fan-out (unused) until
  the bump is verified, then narrows to `data`. (Corrected location: the Secrets
  live in `datahub-local-secrets`, not core.)

## 4. Here: re-verify the fleet against the pinned CRDs (blocked by the apply)

- [x] 4.1 (`HERE`) Re-derived the CRD-defaulted fields: the
  `ensembles.sympozium.ai` default paths and values are identical between the
  `0.10.87` and `0.11.2` chart tarballs (only hook-`timeout` doc text changed), so
  no new default was written out. The source already states the whole set that
  lands (`mcpServers[].timeout`, `schedule.firstTick`, `memory.maxSizeKB`,
  `sharedMemory.storageSize`, `lifecycle.gateDefault`); the ArgoCD app is Synced.
- [x] 4.2 (`HERE`) Read a live `<run>-postrun` Job pod's environment: it carries
  `AGENT_RUN_ID`, `AGENT_NAMESPACE`, `AGENT_EXIT_CODE`, `AGENT_RESULT` and
  `INSTANCE_NAME` as plain env values, so `deliver-slack.py`'s run-id line still
  resolves. The hook now runs as its own Job, not a container on the run pod.
  Recorded the hook-`timeout` semantics change (postRun hooks bound the Job, ≥10
  min) in `MEMORY.md`.
- [x] 4.3 (`HERE`) Re-read the provider-key env names at `v0.11.2`: unchanged. The
  controller still allowlists eleven names (including `API_KEY`,
  `OPENAI_API_KEY`) and the runner still resolves `firstNonEmpty(API_KEY,
  OPENAI_API_KEY, ANTHROPIC_API_KEY, AZURE_OPENAI_API_KEY, PROVIDER_API_KEY)`.
  Each per-owner Secret publishes `API_KEY` and `OPENAI_API_KEY`, so the
  responder's key name is `API_KEY`.
- [x] 4.4 (`HERE`) Read the MCP tool counts: `mcp-homelab-facts` exposes **18**
  tools and `semantic`/`semantic-finance` **5** each (live `tools/list`). A run's
  `mcp-discover` log reports the post-`toolsAllow` counts.
- [x] 4.5 (`HERE`) Corrected the stale `policyRef` note in `MEMORY.md`: gating is
  enforced now, and `permissive` leaves the reporter surface reachable.
- [x] 4.6 (`HERE`) Hand-applied an `AgentRun` per ensemble on its own route:
  `homelab-responder` and `homelab-reviewer` probes both `Succeeded` (result
  `ROUTE-OK`), each recording `sympozium.ai/model-key-owner` on its Secret with no
  `ConflictError`/`NotGrantedError`; `homelab-ops` and `pi-render` had already run
  post-bump. Streamed logs live.
- [x] 4.7 (`HERE`) Added the bump entry to `MEMORY.md`: the target and why not
  `0.11.3`, the seven workarounds kept, the one-key change, the enforced gating,
  the hook-timeout change, and the closed re-check list with what was measured.

## 5. Retire `docs/specs/` (done in the `retire-docs-specs` change)

- [x] 5.1 (`DOC`) Moved `docs/specs/001…005` verbatim into
  `openspec/changes/archive/2026-10-07-retire-docs-specs/designs/` and removed
  `docs/specs/`.
- [x] 5.2 (`DOC`) Repointed every live reference: `agents/sympozium/MEMORY.md`,
  `workflows/dbt/semantic/bodega.yaml`, `workflows/dbt/semantic/finance.yaml`,
  `workflows/dbt/semantic/README.md`, `workflows/dlt/projects/finance/*`, and
  the `AGENTS.md` "Design specs" section. Left archived changes untouched.
- [x] 5.3 (`HERE`) Spec 004 now resolves at its archived path.

## 6. Verify

- [x] 6.1 `helmfile template` renders: core's automation release at the pin
  (sympozium subchart and the parent with all seven workarounds), the secrets
  release (the five auth-credential ExternalSecrets in the right namespaces), and
  `agents/sympozium/` (render gate passes).
- [x] 6.2 `openspec validate --all` passes (12 passed).
- [x] 6.3 `pytest agents/sympozium/tests/` passes (49). `ruff` reports one
  **pre-existing** error in `scripts/reseed_memory.py` (`subprocess.run` without
  `check=False`), untouched by this change. The negative render-gate test was not
  run.
- [x] 6.4 Each ensemble and `pi-render` has run once on its own model route:
  `homelab-ops` on a scheduled run (`sre-sentinel-schedule-119`, `Succeeded`),
  `pi-render` on a Visual Studio turn (`verify-planfirst-20261008`, `out.mp4`
  written), and `homelab-responder`/`homelab-reviewer` on hand-applied probes
  (both `Succeeded`). Each Secret carries its own
  `sympozium.ai/model-key-owner`.
