# homelab-agent-fleet Specification

## Purpose
Run the homelab's Sympozium personas — three ensembles, seven read-only reporters
and one inbound answerer — on a pinned, deployable control plane, with the
configuration split between `datahub-local-core` (the control plane, its
workarounds and policies) and this repository (the ensembles, personas, delivery
and mounted MCP config). The fleet is the unit: a persona is a YAML file and a
prompt, not a service.

## Requirements

### Requirement: The control plane is pinned to a deployable release

The fleet SHALL run on a Sympozium release pinned in
`datahub-local-core/values/_version.yaml`, and the pin SHALL name a release whose
chart is published to the chart repository **and** whose `controller`,
`apiserver` and `web-proxy` images are published to the registry. A version bump
MUST NOT be applied while any of those artifacts is missing.

#### Scenario: Pin names a published release
- **WHEN** the pin is set to a release
- **THEN** the rendered `SkillPack/web-endpoint` carries
  `web-proxy:v<release>`
- **AND** each of the three images pulls successfully

#### Scenario: Pin names an unpublished release
- **WHEN** the target release's chart or any of its three images is not yet
  published
- **THEN** the apply is blocked and the pin lands on the newest deployable
  release instead
- **AND** a follow-up tracks the target

### Requirement: One model key per Agent or Ensemble

No model-key Secret SHALL be shared across Ensemble boundaries. Where the
provisioning path records a Secret's owner, the owner MUST be exactly one Agent
or the members of exactly one Ensemble.

#### Scenario: Two ensembles name the same Secret
- **WHEN** two ensembles resolve the same model-key Secret
- **THEN** each ensemble is given its own Secret

#### Scenario: An Agent outside any ensemble
- **WHEN** a non-ensemble Agent (the `pi-render` session) needs a model key
- **THEN** it takes its own Secret, and its `AgentRuntime` `authSecretRef` and
  the Agent's `authRefs` name the same one

### Requirement: Policy gating is enforced and uses only allow or deny

Every `SympoziumPolicy` the fleet declares SHALL use only the `allow` and `deny`
actions, and its `sandboxPolicy` and `toolGating` MUST describe the posture
actually wanted, because the control plane now applies them.

#### Scenario: A policy carries ask
- **WHEN** a policy rule or `defaultAction` is `ask`
- **THEN** it fails admission and is corrected to `allow` or `deny`

#### Scenario: A persona resolves a policy that allows everything
- **WHEN** a persona declares `policyRef: permissive`
- **THEN** its tool surface is unchanged, because the built-in policy is
  `defaultAction: allow` with no rules

### Requirement: Upstream workarounds are retired only with a render-diff reason

Each entry in `datahub-local-core/releases/automation/templates/sympozium_upstream_fixes.yaml`
SHALL be kept until the target chart changes the template it patches, or dropped
with the fixing diff quoted. A release note is not evidence; the render diff is.

#### Scenario: The patched template is unchanged
- **WHEN** the target chart's `network-policies.yaml` or
  `controller-deployment.yaml` is byte-identical to the pinned version's
- **THEN** the workaround that patches it is kept

#### Scenario: The patched template changed
- **WHEN** the target fixes the upstream defect
- **THEN** the workaround is deleted and the fixing diff is recorded

### Requirement: Every persona is re-verified after a control-plane bump

After the pin moves, the fleet's CRD defaults, injected hook environment, MCP
tool counts, delivery path and (`policyRef`) enforcement SHALL be re-read from the
running system, and each finding written into `agents/sympozium/MEMORY.md` with
what was measured.

#### Scenario: A CRD default is added
- **WHEN** the pinned `Ensemble` CRD carries a default the source omits
- **THEN** the value is written out in source so ArgoCD reports no drift

#### Scenario: An injected variable changed
- **WHEN** a variable the delivery hook reads is no longer injected
- **THEN** the hook is corrected before the bump is considered done
