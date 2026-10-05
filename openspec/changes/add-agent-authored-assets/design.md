# Design

## Context

See [proposal.md](proposal.md) — Why. The facts that shape the approach, read from
the cluster and the code:

- **Visual Studio** (n8n) authors one asset per requested type from
  `agents/n8n/datasets/visual_types.json`. Today the authors are `raster`,
  `spec_raster`, `spec_markup` and `spec_service`; a `render: video` type POSTs a
  spec to the render service at `$env.RENDER_URL` and takes the MP4 back as a file
  (`render_video`, `responseFormat: file`). Branch selection is `if_raster`
  (`AUTHOR`) and `if_video` (`RENDER_MODE`). It returns asset **content**, never a
  URL (visual-studio spec).
- **The pi-render agent** is a Sympozium `HarnessSession` (`v1alpha2`): the
  controller makes a Deployment and a ClusterIP Service, the pod runs
  `session-server.mjs`, which offers `GET /healthz` and
  `POST /v1/chat/completions` (OpenAI-shaped, SSE optional) and returns **Pi's
  stdout text**, bounded at 2 MB. Turns are serialized because Pi's session file is
  shared. The rendered file lands on the session PVC — the pi-authored run wrote
  `/tmp/aivideo/out.mp4`; `/workspace` is read-only in a session container.
- **The session is walled off and hand-sized.** Its NetworkPolicy admits only the
  Sympozium apiserver on 8080; egress is `{53,443,8080,9473}` plus our additive
  port-4000 policy for LiteLLM. The controller creates the PVC at a fixed `1Gi`
  (974 MiB) — 50 MiB below the engine's `checkDisk()` gate of 1024 MiB, so a fresh
  session cannot render. The claim is named after the session and, once present, is
  not resized. `spec.idleTimeout` stops the workload after inactivity and removes
  the Service, preserving the PVC and the CR; `desiredState` defaults to `running`
  and `idleTimeout` has no default.
- **The current session is a spike** (`sympozium.ai/spike: "true"`, `deploy/`), not
  a deployed, reproducible object.

## Goals / Non-Goals

**Goals:**

- One `agent` author kind in Visual Studio, selectable by type id like any other.
- A session contract that returns an artifact a workflow can fetch, isolated per
  run.
- A production session that is reachable, correctly sized and available when a
  workflow calls it.
- The deterministic media paths untouched; an agent failure costs one asset, not
  the post.

**Non-Goals:**

- A core-owned authoring service, or removing the Sympozium dependency.
- Making authoring deterministic, cheap or fast; it is a model run.
- Changing the render service, the Visual Studio trigger contract, the run table,
  or any existing type's meaning.
- LinkedIn video uploads (`shareMediaCategory: VIDEO`); the publish node keeps
  taking an image.

## Decisions

### D1. The `agent` author lives in Visual Studio, not a second API

The registry gains `author: agent`; a branch beside `if_raster`/`if_video` sends the
request's `CONTENT` to the session and returns the fetched file as the asset's
content. `LinkedIn Post Sharing` and any future doc workflow keep calling Visual
Studio with `ASSET_TYPES`; they learn nothing new.

*Alternatives considered:* have each workflow call the session directly — rejected;
it repeats the session URL, the artifact fetch and the failure handling in every
caller, which is the plumbing Visual Studio exists to hold. A new standalone
authoring API — rejected for the same reason, plus it would duplicate the registry.

### D2. The session returns the artifact over HTTP, isolated per run

A caller supplies a run-scoped `session_id`. The session server runs Pi in a
per-run directory under the session PVC (not `/workspace`, which is read-only in a
session), names that directory in the prompt so the agent writes `out.mp4` there,
and serves it back at `GET /artifacts/<session_id>/<file>` after validating both
segments against a fixed pattern and an allowlist of names. The authoring call
stays `POST /v1/chat/completions` — the contract whose activity the controller
tracks — and its response stays Pi's report; the artifact is a second, separate
request.

*Alternatives considered:* return the file base64 inside the chat response —
rejected; it collides with the 2 MB output bound and conflates the OpenAI contract
with a file API. Write to a fixed shared path — rejected; sequential turns would
overwrite one another. A shared object store — rejected as an extra component when
the PVC already holds the file; revisit if artifacts must outlive the session.

### D3. The output kind is part of the request, and the session produces it

The authoring request carries the kind the caller needs. The workflow's type
declares a format (LinkedIn needs an animated **GIF** because the publish node is
`shareMediaCategory: IMAGE`), and the session produces that format after the
engine's render — the adapter image derives from the render image and already has
`ffmpeg`, so an MP4→GIF step at the type's declared fps/frames/size is deterministic
post-processing, not a model decision. A future doc workflow can ask for `mp4` (or
another) without a new path.

*Alternatives considered:* ship only MP4 and switch LinkedIn to a video post —
rejected; it changes the publish API and the approval flow, a separate change.
Rely on the composition itself being a GIF — rejected; HyperFrames renders video,
and format conversion belongs with the encoder we already have.

### D4. The workflow fetches the bytes; the studio still returns content

The agent branch is two HTTP requests: `POST` the brief, then `GET` the artifact
(`responseFormat: file`), exactly as `render_video` takes the MP4 as a file. The
asset then carries content + `CONTENT_TYPE`, satisfying the visual-studio spec's
"content, not a reference" requirement. The session URL is an n8n env var, like
`RENDER_URL`.

### D5. The production session is a declared object, kept available

The spike manifests become a production set — labels without `sympozium.ai/spike` —
with the four fixes a workflow depends on:

1. an **additive NetworkPolicy** admitting `app.kubernetes.io/name: n8n` on 8080
   (the controller's policy keeps its apiserver-only rule; NetworkPolicies add);
2. a **pre-created PVC named after the session at 8 GiB**, because the controller's
   fixed `1Gi` claim is structurally below the engine's gate and it sizes a claim
   only at creation, so an existing one is respected;
3. **resources** (2 GiB request / 6 GiB limit) — honoured on the session path via
   `AgentRuntime.spec.resources`;
4. **no idle stop** (`idleTimeout` omitted, since it has no default), so a scheduled
   call always finds a running Service. This is the cost of the choice: one 6 GiB
   pod stays up. `desiredState` already defaults to `running`.

The objects are declared in the `agents/sympozium/` chart, which ArgoCD already
reconciles and whose CI renders the chart, rather than the adapter's hand-applied
`deploy/`. A workflow now depends on this session being up, and a hand-applied
object is not a dependency anyone reconciles. The adapter's `deploy/` remains the
worked reference for a one-off session and points at the chart for the deployed one.

*Alternatives considered:* keep it in `deploy/` and apply by hand — rejected; the
dependency would rot silently. A core-owned service (the user's other option) —
rejected because the session path is where the memory is ours to set and the
controller already owns the lifecycle; a separate service would reimplement it.

### D6. LinkedIn opts in; the deterministic paths stay

`POST_MEDIA` gains a value (e.g. `AGENT`) that requests the agent-authored type. The
existing `ANIMATED` value keeps requesting `diagram_animated_linkedin`, and the
still-image fallback is unchanged, so the default behaviour of every existing row
does not move. If the agent asset fails, the existing `check_animation_result`
fallback carries the run into the still-image path with the reason announced.

*Alternatives considered:* repoint `ANIMATED` at the agent author — rejected as the
default; it would spend a model run and minutes on every animated post and make an
existing behaviour depend on an unproven path. It is a one-value switch if desired
later.

### D7. The markup boundary is explicit

The deterministic family keeps "the model MUST NOT author the markup". For an
`agent` type the markup is authored by the agent inside its sandbox and rendered
there; the workflow receives only a rendered artifact and never authors, receives or
executes that markup. The visual-studio spec delta states this so the two rules stop
looking like a contradiction.

## Risks / Trade-offs

- **A model run is minutes and non-deterministic, so a scheduled post can now be
  slow or different each time.** → Opt-in per row (D6); the deterministic type and
  the still-image fallback remain; a failure costs one asset.
- **A stopped session has no Service, so a call cannot wake it.** → D5 omits
  `idleTimeout`; if the cost matters, a wake-on-demand step is a follow-up.
- **The artifact fetch adds a path-handling surface.** → `session_id` and filename
  are validated against fixed patterns; only files under the run's directory are
  served.
- **The session PVC holds every run's artifact.** → Per-run directories; retention
  is a follow-up (the render service uses a TTL sweep; the PVC is not swept today).
- **A 6 GiB pod running continuously for a daily post is expensive.** → Accepted
  for now and stated; the alternative (core service) was rejected by the user.
- **The agent author is less tested than the deterministic path.** → The
  `add-agent-authored-compositions` change proved the authoring loop; a live
  LinkedIn run is the acceptance test.

## Migration Plan

1. Adapter: per-run directory, artifact endpoint and required output format; rebuild
   and publish by digest.
2. Session: production objects (policy, runtime, agent, session, PVC, n8n
   NetworkPolicy) in the chart; verify n8n can reach the session and that it renders.
3. Registry: add the agent-authored type.
4. Visual Studio: add the agent branch; apply live with `--require-edge` and diff
   the export against live.
5. `LinkedIn Post Sharing`: add the `POST_MEDIA` opt-in; apply live.
6. Offline tests, then a manual run of one opted-in row.

Rollback: remove the `POST_MEDIA` value / set the type `available: false`. The
deterministic types, the render service and the publish node are untouched.

## Open Questions

- Does the controller treat the artifact `GET` as activity for the idle timer? The
  authoring `POST` already resets it and the fetch follows within seconds, so it is
  not expected to matter; the session has no idle stop in D5 regardless.
- Whether LinkedIn's feed animates the GIF at the agent's rendered size is already
  open in `add-linkedin-animated-post-media` (5.6) and is answered by the same real
  post, not by this change.
