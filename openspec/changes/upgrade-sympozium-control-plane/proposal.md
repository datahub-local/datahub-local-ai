# Proposal

## Why

The Sympozium control plane is pinned in **core**, not here:
`datahub-local-core/values/_version.yaml` names `sympozium/sympozium` at
`0.10.87` (released 2026-09-20). Upstream has since shipped **0.11.0, 0.11.1,
0.11.2 and 0.11.3**; `0.11.0` is a **breaking** release on three axes that reach
this repository's personas directly:

- **One model key per Agent.** A model-key Secret's owner is recorded in
  `sympozium.ai/model-key-owner` — one Agent, or the members of one Ensemble —
  and enforced in the controller, the webhook, the gateway and the console/API.
  All three ensembles **and** the `pi-render` Agent currently name the same
  Secret, `litellm-auth-credentials`, which is exactly the cross-Ensemble sharing
  the release refuses.
- **`SympoziumPolicy.toolGating` is now enforced**, and `ask` is removed (the
  action enum is `allow`/`deny`). Until 0.11.0 the gating did nothing; from
  `0.11.0` a policy's `deny` rules and `defaultAction` reach every run the
  controller builds. The chart's built-in `permissive` policy still allows
  everything, so the reporters are not gated by it — but a policy that had been
  read as inert is now live, and a policy carrying `ask` fails admission.
- **Skill sidecars lose Secret reach by default**, and a new chart
  `ValidatingAdmissionPolicy` (`skill-secret-references`) refuses any
  `sympozium-run-*` account that creates a workload mounting or reading a
  Secret. This is a new chart template that `0.10.87` did not render.

The fleet's own configuration lives **here** (`agents/sympozium/`): three
ensembles, seven personas, the MCP catalog config and the delivery hook. The
control-plane pin and the upstream workarounds live in **core**. A version bump
is therefore one change across two repositories, and neither half is safe alone:
core can bump the pin while the ensembles keep sharing one key, and here can fix
`authRefs` while the pin still points at a control plane that ignores it.

## What Changes

- **Core pins the control plane to `0.11.2`**, the newest deployable release, in
  `values/_version.yaml`. `0.11.3` is tracked as the follow-up: its chart and its
  `controller`/`apiserver`/`webhook`/`web-proxy` images are still unpublished, so
  a pin at `0.11.3` would fail at image pull (verified 2026-10-07).
- **Core re-reviews `sympozium_upstream_fixes.yaml`.** Each of the seven
  workarounds is kept or dropped on evidence from the target chart render, not
  on a reading of the release notes.
- **Core adapts `sympozium_policies.yaml`** to the enforced, `ask`-free gating
  enum, and states which policy each persona actually resolves.
- **Core keeps the `_kustomize` patches** that the target chart still needs
  (NATS `Recreate`, the `web-proxy` image pin, the read-only `k8s-ops` RBAC) and
  re-verifies each against the bumped `$sympozium_version`.
- **Here gives each Ensemble its own model key** (or proves that a single
  fleet-wide key is still accepted for this provisioning path), so no Secret is
  shared across ensemble boundaries.
- **Here re-verifies the fleet against the pinned CRDs** — the `re-check after a
  control-plane bump` list accumulated in `agents/sympozium/MEMORY.md`, the
  render gate, the delivery hook and the evals.
- **`docs/specs/` is retired** into `openspec/` (a separate archived change,
  `retire-docs-specs`), with live pointers repointed; the sympozium design record
  `004-agents-hosted-model.md` moves with it.

## Capabilities

### New Capabilities

- `homelab-agent-fleet`: the fleet runs on a pinned, deployable Sympozium
  release; model keys are owned by one Agent or one Ensemble; policy gating is
  enforced and uses only `allow`/`deny`; upstream workarounds are retired only
  with evidence; and every persona is re-verified after a control-plane bump.

### Modified Capabilities

None. No `openspec/specs/` capability describes the fleet today; the sympozium
decisions have lived in `docs/specs/004-agents-hosted-model.md` and
`agents/sympozium/MEMORY.md`, both of which this change moves and re-points.

## Impact

- **core** (`datahub-local-core`): `values/_version.yaml` (0.10.87 → 0.11.2),
  `releases/automation/values/sympozium.yaml.gotmpl`, `releases/automation/values/_kustomize.yaml.gotmpl`
  (the `web-proxy` tag follows the pin), and the two templates under
  `releases/automation/templates/` — no change needed in them, kept as-is.
- **datahub-local-secrets**: `release/values/default.yaml.gotmpl` — one
  model-key Secret per owner (`…-homelab-ops`, `…-homelab-responder`,
  `…-homelab-reviewer`, `…-pi-render`) into `automation`; the shared
  `litellm-auth-credentials` is kept fanned to `automation` (unused) until the
  bump is verified, then narrowed to `data` in a follow-up.
- **here**: `agents/sympozium/values/default.yaml.gotmpl` (`authRefs` per
  ensemble, `sympozium_pi_render.model.authSecret`),
  `agents/sympozium/templates/pi-render-session.yaml` (its `authRefs` and
  `AgentRuntime.authSecretRef` read that same value),
  `agents/adapters/pi-render/deploy/session.yaml`, `agents/sympozium/README.md`
  and `MEMORY.md`.
- **docs**: `docs/specs/004-agents-hosted-model.md` →
  `openspec/changes/archive/2026-10-07-retire-docs-specs/designs/` (the
  `retire-docs-specs` change); live references to `docs/specs/` in
  `agents/sympozium/MEMORY.md`, the dbt semantic registry and the dlt finance
  provider are repointed.

## Non-goals

- **No Celln mediation or Celln fleet.** `celln.mediation` stays off; the
  bundled PostgreSQL and the mediated key path are not adopted by this change.
  They are the reason the one-key-per-Agent rule exists, not a feature this
  fleet turns on.
- **No persona redesign, no prompt rewrite, no model change.** The fleet stays
  on `opencode-go/deepseek-v4.1-flash` through LiteLLM. Only what the new control
  plane forces changes.
- **No MCP catalog change.** The `mcp-homelab-facts`, `semantic`,
  `semantic-finance` and `render` servers and their mounted config are untouched;
  their images are pinned independently in `datahub-local-ai-mcp`.
- **No `workflowType: delegation`.** Spec 004's AI-12 stays held for the same
  reason: the responder has no second persona to delegate to.
- **No docs/specs content rewrite.** The retirement moves the five design
  records verbatim; it does not re-edit them.
