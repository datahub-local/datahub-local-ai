# Tasks

Cross-repo: `CORE-*` are `datahub-local-core`; `SEC-*` are
`datahub-local-secrets`; `HERE-*` are this repository; `DOC-*` is the
`retire-docs-specs` change. `blocked by` links are real — do not start a blocked
task.

**Progress 2026-10-07:** landed at `0.11.2` (source + render only; no live
apply), with the one-key fix in three repos. `4.*` and `6.4` need the cluster and
are open.

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

- [ ] 4.1 (`HERE`) Re-derive the CRD-defaulted fields
  (`kubectl get crd ensembles.sympozium.ai -o json | jq '.. | objects |
  select(has("default"))'`) and write any new default out in source; diff a
  `--dry-run=server` apply against the render, not `kubectl diff`.
- [ ] 4.2 (`HERE`) Read a live `postrun` pod's environment and confirm
  `AGENT_RUN_ID` and `AGENT_NAMESPACE` still reach `deliver-slack.py`; note the
  hook-`timeout` semantics change (postRun hooks bound the Job, ≥10 min).
- [ ] 4.3 (`HERE`) Re-read the provider-key env names in the runner and the
  controller allowlist (they disagreed at `v0.10.48`); confirm the responder's
  key name.
- [ ] 4.4 (`HERE`) After the apply, read `kubectl logs <run-pod> -c mcp-discover`
  for the per-server tool counts and confirm the expected numbers.
- [x] 4.5 (`HERE`) Corrected the stale `policyRef` note in `MEMORY.md`: gating is
  enforced now, and `permissive` leaves the reporter surface reachable.
- [ ] 4.6 (`HERE`) Hand-apply one `AgentRun` per ensemble and stream its log live
  (not read after the pod is gone). (`pytest` and `ruff` ran offline — 6.3.)
- [x] 4.7 (`HERE`) Added the bump entry to `MEMORY.md`: the target and why not
  `0.11.3`, the seven workarounds kept, the one-key change, the enforced gating,
  the hook-timeout change, and the open `[UNVERIFIED]` items.

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
- [ ] 6.4 Each ensemble and `pi-render` has run once on its own model route.
