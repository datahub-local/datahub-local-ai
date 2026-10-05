# Design

## Context

Two products exist and must not be conflated (see proposal.md — Why):

- **The render service** (`agents/n8n/render/`) takes a typed spec and authors the
  composition itself. Its flexibility is its layouts and its vendored catalog
  blocks; it rejects caller markup by construction, and that rejection is
  deliberate (design D2 in `add-hyperframes-render-service`, D4 in
  `migrate-render-layouts-to-catalog-blocks`).
- **An agent-authored composition** is a composition *written for one brief*.
  Nothing in the render service accepts it, and nothing should: the service's
  contract is that a caller cannot inject markup.

What changed on 2026-10-04 is that the second path was **proven to work**, not
merely imagined. A one-sentence brief produced a 9 s / 270-frame / 1080×1350
animation, authored against the `hyperframes-core` skill, with HyperFrames' own
`lint` catching two real defects (a GSAP tween on `top`, which snaps to integer
pixels and stutters under frame-stepping; and a timed element with no `id`).
Rendering used the render service's own image toolchain.

Cluster facts gathered the same day, read from the live CRDs:

- The `Agent` CRD has **`runtimeRef`** (a string naming an `AgentRuntime`): "replaces
  `agent-runner` as the primary process for this Agent's ordinary string-form runs.
  Those runs are dispatched through harness mode with this runtime and their
  original task as the prompt."
- Two `AgentRuntime`s are present in `automation` and both report `Ready: True`:
  `pi-session-v0-84-4` (`ghcr.io/sympozium-ai/harness-adapters/pi@sha256:8c8f0df0…`)
  and `hermes-session-v0-20-6` (`…/hermes@sha256:70c643b2…`). Both declare
  `session: {port: 8080, protocol: openai-chat}` and `capabilities: null`.
- **No persona in this repository sets `runtimeRef`** (grepped: zero hits), so
  adopting a harness is a chart change, not new infrastructure.
- `capabilities: null` means the runtime "claims nothing" — the schema's own words —
  so a Pi runtime's tool surface is **unverified**, and the spec deliberately makes
  that a gate rather than an assumption.

## Goals / Non-Goals

**Goals:**

- A declared, reviewable path for authoring a composition from a brief.
- The validation loop as a required step, since it is what makes authoring reliable.
- Offline rendering, enforced rather than hoped for.
- An evidence-based answer on running this in the Sympozium fleet, especially with Pi.

**Non-Goals:**

- Changing the render service's API, or letting it accept markup.
- Replacing the typed-spec path. Scheduled, repeatable asset types keep using it.
- Authoring in production before the Pi gate passes.
- Building a bespoke generator: the capability is HyperFrames' skills plus an agent,
  not new code in this repository.

## Decisions

### D1. The path is "agent + engine skills", not a new service

The agent authors the composition by following HyperFrames' own skill contract;
HyperFrames renders it. No new component in this repository does the authoring.

*Alternatives considered:* extend the render service to accept markup — rejected; it
breaks the one property that makes the service safe to expose to a workflow, and it
was already rejected twice. Build a template generator with a richer vocabulary —
rejected; it reproduces a worse version of what HyperFrames already ships.

### D2. The composition is committed; the render is derived

The authored `index.html` is the artifact of record and the MP4 is rebuilt from it.
This is what makes an authored composition reviewable — a reviewer reads the
composition, not just the video — and it is what makes a re-render deterministic
given the same engine version.

*Alternatives considered:* keep only the video — rejected; nothing can be re-rendered
or reviewed, and the brief's answer is unrecoverable.

### D3. The engine's validation is a gate, not advice

`lint` runs before `render`, and findings are corrected. This is not ceremony: on the
proven sample, `lint` caught two defects that would otherwise have shipped as visible
faults, and the skill documents a class of silent bugs (`gsap_css_transform_conflict`,
`gsap_animates_clip_element`, `font_family_without_font_face`) that a render does not
obviously reveal.

*Alternatives considered:* render and inspect frames — rejected as the primary gate;
it catches gross layout faults but not the determinism and lint classes, and it is
far slower per iteration.

### D4. Offline is enforced at the composition, not at render time

A composition referencing a remote script or font fails. The sample uses a vendored
GSAP; the check belongs in the authoring step so a bad composition is rejected before
a render is attempted.

*Alternatives considered:* allow a CDN and rely on network at render time — rejected;
the render image is built to run with no network, and a CDN reference would make the
output depend on a third party's uptime.

### D5. Authoring does not run on the maintained Pi/Hermes adapters

**Settled by the probe (2026-10-04), then corrected by the official documentation.**
The gate ran to completion once the credential was fixed, and the Pi harness cannot
author a composition. Two separate reasons, both verified:

1. **Pi is session-only** — the admission webhook refuses a one-shot `AgentRun`
   against it (`harness: runtime "pi-session-v0-84-4" is session-only (v1alpha2)`),
   and every persona here runs as an `AgentRun`.
2. **The maintained adapter disables tools.** Both adapter paths spawn Pi with
   `--print --no-skills --no-prompt-templates --no-tools`, so it has no file write,
   no shell and no edit, and cannot read the authoring skills. The official docs
   state this as deliberate: *"Both continue to disable tools and skills."*

**The correction matters, and the first draft of this decision got it wrong.** It
claimed a harness image could never invoke a toolchain. That generalised from the
Pi image to harness mode, and the docs refute it: *"The harness brings its own, or
none"*, and *"BYO means a contract-compatible adapter image, not an arbitrary
upstream harness image."* Tool use is a property of **the image**. The platform
supplies everything a tool-using adapter needs — the `/workspace` PVC, a writable
`$HOME` emptyDir, writable `/tmp` against a read-only rootfs, UID 1000, and its own
`ENTRYPOINT` the image chooses — which is exactly the environment the render image
already runs in.

So the decision is narrower than "out-of-fleet":

- **Do not build an authoring persona on Pi or Hermes.** That is what the evidence
  supports, and it is why section 3 of the tasks is dropped.
- **A hyperframes harness adapter is a supported, documented path** — a normal image
  that drives the toolchain and emits the result contract. Recorded as a follow-up
  in `pi-harness-findings.md`, deliberately **not built here**: it is real work
  (toolchain baked in, adapter state, conformance, an `AgentRuntime` registration)
  and the capability is already proven without it.

The proven loop stays the deliverable: author and render where tool use and the
toolchain already exist, as `agents/render-samples/agent-flow/` shows.

**Superseded detail, kept because it was the original premise.** `runtimeRef` was
expected to be a drop-in for a persona; the admission webhook refuted that first —
Pi is **session-only**, and both cluster runtimes are `v1alpha2`. A `HarnessSession`
also has nowhere to put a model (its spec is `agentRef`, `runtimeRef`, `idleTimeout`,
`desiredState`), so the model must come from the Agent with an `authRefs` provider
credential.

## Risks / Trade-offs

- **The Pi runtime's capability surface is unverified** (`capabilities: null`). → D5
  makes the probe the gate; do not set `runtimeRef` on a persona before it passes.
- **An authored composition can be arbitrary.** It is not restricted by a schema. →
  It is authored by our agent, committed, and reviewed; the render is sandboxed to a
  browser. This is a reviewed artifact, not an open endpoint, and the render service
  remains the only thing a workflow can call.
- **Non-determinism across engine versions.** A re-render can differ. → The engine
  version is pinned and recorded with the sample.
- **Two paths confuse callers.** → The spec requires them to be distinguishable, and
  the sample README states which product answers which need.
- **Cost**: authoring is a model-heavy loop with several validation iterations. → It
  is for one-off bespoke briefs, not for scheduled repeatable assets; those stay on
  the typed-spec path.

## Migration Plan

1. Commit the sample and its procedure (done with this change's first tasks).
2. Probe Pi with a hand-applied `AgentRun`; record the three capabilities.
3. If the probe passes, add a persona with `runtimeRef: pi-session-v0-84-4` and a
   task file that names the skill to follow and the validation gate.
4. If it fails, record the finding and keep the path out-of-fleet; do not add a
   persona.

Rollback for step 3 is removing `runtimeRef` from the persona — no other object
depends on it.

## Open Questions

- Does the Pi harness expose a shell and a file-write tool at all? This is exactly
  what D5's probe answers, and it is deliberately not guessed.
- Does the harness pod need the render toolchain baked in, or can it reach the
  deployed render image? Resolve from the probe's third check.
