# Tasks

Cross-repo: `CORE-*` are `datahub-local-core`; `HERE-*` are this repository.
`DOC-*` is the `retire-docs-specs` change. `blocked by` links are real — do not
start a blocked task.

## 1. Gate the target (before anything else)

- [ ] 1.1 (`CORE`) Confirm the target release is deployable in full: the chart
  is in `helm search repo sympozium/sympozium -l` and
  `ghcr.io/sympozium-ai/sympozium/{controller,apiserver,web-proxy}:v<target>`
  each answer **200**. If any is missing, land the pin at the newest deployable
  release (`0.11.2` at time of writing) and open a follow-up for the target.
  Records the answer in `MEMORY.md`.
- [ ] 1.2 (`HERE`) Decide the model-key shape from finding 2 by reading the
  target's `modelkey` enforcement: does the path provisioned through `authRefs`
  (non-Celln) enforce `sympozium.ai/model-key-owner`? Write the answer, and
  whether per-Ensemble Secrets are required, into `MEMORY.md`. **This is the
  first task and it gates §3.**

## 2. Core: the pin, the workarounds, the policies (blocked by 1.1)

- [ ] 2.1 (`CORE`) Pin `sympozium` in `values/_version.yaml` to the target
  decided in 1.1. Verify `helmfile template` resolves
  `.../web-proxy:v<target>` in the rendered `SkillPack/web-endpoint`.
- [ ] 2.2 (`CORE`) Re-run the chart diff (`helm pull` target, diff
  `templates/network-policies.yaml`, `templates/controller-deployment.yaml`,
  `crds/*` against `0.10.87`) and record, per workaround 1–7, whether the target
  changed the template it patches. Keep each unchanged workaround; drop only a
  fixed one, with the diff quoted in the commit message.
- [ ] 2.3 (`CORE`) Server-side dry-run `releases/automation/templates/sympozium_policies.yaml`
  against the target CRD; confirm no `ask` remains and the enum validates.
  Record which `policyRef` each ensemble resolves and that the built-in
  `permissive` is still `defaultAction: allow`.
- [ ] 2.4 (`CORE`) Re-verify the kustomize patches under the new
  `$sympozium_version`: NATS `Recreate`, the `web-proxy` pin, the `k8s-ops`
  read-only RBAC. Note that finding 4 removes `secrets`/`pods/exec`/`pods/attach`
  from skill RBAC by default, so the `k8s-ops` patch is now a second wall.
- [ ] 2.5 (`CORE`) If the target chart renders anything new into `automation`,
  enumerate it from a `helm template` diff and confirm it is intended (the
  bundled PostgreSQL renders only with Celln mediation, which is off).

## 3. Here: one key per Ensemble (blocked by 1.2)

- [ ] 3.1 (`HERE`) If 1.2 finds cross-Ensemble sharing is refused, name one
  model-key Secret per ensemble in `agents/sympozium/values/default.yaml.gotmpl`
  (`authRefs[].secret`) and one for `pi-render` in
  `agents/sympozium/templates/pi-render-session.yaml`; keep every value in core's
  security values, never in this repository.
- [ ] 3.2 (`HERE`) If 1.2 finds the `authRefs` path is not gated, change nothing
  and record why, with the enforcement location read from the target.
- [ ] 3.3 (`HERE`) Point the `pi-render` `AgentRuntime.spec.model.authSecretRef`
  and the Agent's `authRefs[].secret` at the same Secret; verify both paths.
- [ ] 3.4 (`HERE`) Provision the per-ensemble Secrets in core's security values
  so an apply creates them with the same value as today's single Secret.

## 4. Here: re-verify the fleet against the pinned CRDs (blocked by 2.1)

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
- [ ] 4.5 (`HERE`) Correct the stale `policyRef` note in `MEMORY.md`: gating is
  enforced now (finding 12); state what `permissive` leaves reachable.
- [ ] 4.6 (`HERE`) Run the hook tests and `ruff`; hand-apply one `AgentRun` per
  ensemble and stream its log live (not read after the pod is gone).
- [ ] 4.7 (`HERE`) Update `MEMORY.md` with the bump entry: the target, the
  workarounds' disposition, the key decision, and each closed re-check item with
  what was measured.

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

- [ ] 6.1 `helmfile template` renders both repos at the pin.
- [ ] 6.2 `openspec validate --all` passes.
- [ ] 6.3 `agents/sympozium/tests/` and `ruff` pass; the render gate fails on an
  injected `toolsAllow`/`toolPolicy.allow` mismatch (negative test).
- [ ] 6.4 Each ensemble and `pi-render` has run once on its own model route.
