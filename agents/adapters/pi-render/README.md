# Pi render adapter

A Sympozium harness adapter that lets an agent **author a HyperFrames composition
and render it** inside a run. Built on `node:22-bookworm-slim` with a browser, an
encoder and a vendored HyperFrames baked in, and Pi's tools enabled.

See `openspec/changes/add-agent-authored-compositions/` and its
`pi-harness-findings.md` for why this exists.

## Why a fork

The maintained Pi and Hermes adapters **disable tools and skills by design** —
their own documentation says so, and it is the right behaviour for a chat harness.
An authoring run needs the opposite: write a file, run the engine, read its
findings, correct, render. Tool use is the *adapter image's* business ("the harness
brings its own, or none"), so this is the documented bring-your-own path.

The cost is stated plainly: **this image tracks Pi's release cadence for the adapter
itself.** Upstream does not maintain it. It is anchored to the upstream adapter's
Dockerfile so the diff is small and reviewable.

## What it adds to the upstream adapter

It **owns its own toolchain**, and this is the point:

- Upstream's Pi image is `node:22-alpine` + `jq` + `git` + `pi-coding-agent`. What it
  does **not** have is a browser or an encoder, which authoring needs.
- This image is `node:22-bookworm-slim` + Debian's `chromium` and `ffmpeg` + a
  vendored HyperFrames and GSAP, with the read-only-rootfs and `HOME` problems
  already found and fixed. It used to derive FROM the visual render service's image,
  but that service is retired, so the toolchain is built here directly.

So: **one toolchain, built once — this image's.** It adds only the agent loop and
the adapter contract on top.

| Change                                              | Why                                                                                                   |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `jq`                                                | the adapter contract builds the result payload with it; the Debian base does not carry it             |
| `@earendil-works/pi-coding-agent@0.84.4`            | the agent loop, pinned and installed with lifecycle scripts disabled, exactly as upstream installs it |
| the engine moved to `/opt/hyperframes`              | so the prompt and the entrypoint do not depend on the base image's `WORKDIR`                          |
| `prompts/authoring.md` at `/opt/pi-render/prompts/` | the instruction is a file, read at run time, not inlined in shell                                     |
| `--no-tools` **dropped**                            | so the agent can write the composition and run the engine                                             |
| `--no-skills` **dropped**                           | so the agent can read the skills that ship in the image                                               |

Deliberately **not** carried over: `git`. Upstream's Pi image has it because Pi offers
a repo-cloning tool; nothing in this adapter or the authoring loop calls it, and a
tool nothing uses is a surface to keep patched for no reason.

Everything else is upstream's, unchanged: the contract check, the credential
checks, the provider config, the `v1alpha1` result protocol, the bounded output and
the `/ipc/control/skip` handling.

## Verified

Built and exercised on 2026-10-04, under the platform's own constraints — **UID
1000, read-only root filesystem, `--network none`**:

| Check                                           | Result                                                                                                         |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Toolchain present as UID 1000, read-only rootfs | node, jq, chromium, ffmpeg, ffprobe, hyperframes, pi — **all found**                                           |
| A render succeeds **offline**                   | the known-good sample rendered 1080×1350, **270 frames, 9.000 s**                                              |
| `lint` runs as the agent's gate                 | `0 error(s), 1 warning(s)` on the sample                                                                       |
| The prompt file is readable by UID 1000         | `/opt/pi-render/prompts/authoring.md`, 1742 bytes                                                              |
| Pi runs with tools available                    | `pi 0.84.4`, described as "AI coding assistant with read, bash, edit, write tools"; `--no-tools` is not passed |

Two defects were found and fixed by this test, which is why it is not a formality:
the Debian base has no `jq` (every run would have failed on the result payload), and
the prompt file was unreadable by UID 1000 because it was copied before the `chown`.

**Not yet verified:** a full run driven by the model — an `AgentRun` in the cluster
where Pi itself writes the composition, reads lint, corrects and renders. That is the
remaining question, and it is the one that decides whether Pi's coding-agent loop
suits authoring. Everything up to the model call is proven.

## Cost

**This image carries a browser and an encoder.** That is the price of authoring
offline, and it is one toolchain kept in one place: the render service that used to
provide it is retired, so this image is now the only thing that builds HyperFrames,
Chromium and FFmpeg for the fleet.

**Upstream drift is ours.** No upstream conformance run covers this image.

## Resources: the 1Gi default, and the two constraints on the session path

**The agent container's 1Gi default OOMKills a render**, and eight runs died that way
— exit 137, between 70 s and 10 minutes, always before an `out.mp4` existed. Pi, a
Chromium instance and a multi-worker render share one container, and the render warns
in advance: *"5 capture workers may exceed this process's V8 heap"*.

### The limit is hardcoded on the Job path

A sweep of **every Sympozium CRD** found no field that reaches a Job's agent container:

| Placement                                        | Result                                                                                              |
| ------------------------------------------------ | --------------------------------------------------------------------------------------------------- |
| `Agent.spec.resources`                           | ❌ **rejected**: `unknown field "spec.resources"`                                                    |
| `AgentRun.spec.resources`                        | ❌ **rejected**: `unknown field "spec.resources"`                                                    |
| `AgentRun.spec.sandbox.resources`                | accepted, but creates a **separate third container** (`sandbox: 512Mi`); the agent stays 1Gi        |
| `Agent.spec.agents.default.resources`            | ❌ **rejected**: `unknown field`                                                                     |
| `AgentRuntime.spec.resources`                    | ✅ exists and says *"the primary container's requests/limits"* — **but is not read on the Job path** |
| `SympoziumSchedule.spec`, `SympoziumPolicy.spec` | no such field                                                                                       |

The value is **hardcoded** in `internal/controller/agentrun_controller.go`:

```go
Resources: corev1.ResourceRequirements{
    Requests: { ResourceCPU: "250m", ResourceMemory: "512Mi" },
    Limits:   { ResourceCPU: "1",    ResourceMemory: "1Gi"  },
},
```

Nothing reads a field to fill it. Docs, and three separate external sources, all name
a field that does not exist in this version.

### The session path honours it — with two constraints

`internal/controller/harnesssession_controller.go` **does** apply the field:

```go
Resources: corev1.ResourceRequirements{},
...
if runtime.Spec.Resources != nil {
    container.Resources = *runtime.Spec.Resources
}
```

So a `v1alpha2` `AgentRuntime` behind a `HarnessSession` runs as a Deployment whose
memory is ours to set. Verified: `harness: limit=6Gi request=2Gi`, `session=Ready`.

**But the session's NetworkPolicy is ingress-only to the apiserver and hardcodes its
egress allowlist** (`harnesssession_controller.go`):

```go
Egress: []networkingv1.NetworkPolicyEgressRule{
    {Ports: {53/UDP, 53/TCP}},                          // DNS
    // "HTTPS covers public providers; 8080 and 9473 preserve standard
    //  cluster-local/node-proxy model routes. NATS (4222) is absent."
    {Ports: {443, 8080, 9473}},
},
```

**This cluster's LiteLLM gateway listens on 4000, which is not in that list**, so a
session cannot reach an in-cluster model without widening it. There is no field to
extend it. NetworkPolicies are **additive**, so a second policy permitting that port
is the fix, and it was required to make a session work here:

```yaml
kind: NetworkPolicy
spec:
  podSelector: {matchLabels: {app.kubernetes.io/name: harness-session}}
  policyTypes: [Egress]
  egress:
    - to: [{namespaceSelector: {matchLabels: {kubernetes.io/metadata.name: data}}}]
      ports: [{port: 4000, protocol: TCP}]
```

Two constraints, then, and both are upstream gaps rather than misconfiguration: the
Job path cannot raise memory, and the session path cannot reach a model that listens
on any port outside `{443, 8080, 9473}`.

### Partial workaround that still holds

`AgentRun.spec.env` is appended to the agent container **last**, so it reaches the
process:

```yaml
spec:
  env:
    NODE_OPTIONS: "--max-old-space-size=512"
```

Verified: `NODE_OPTIONS` on the container and a **524 MB heap cap** inside it. With
that plus `--low-memory-mode --workers 1`, the best Job run got further than any other
— it wrote `index.html` and `index.motion.json` and **actually started a render**,
surviving four minutes — but still OOMed. Capping the heap makes V8 collect; it does
not make a render fit in 1Gi. The image now sets the cap itself, so neither path
depends on the caller.

**The working fix is the render's own flag, and it is in the prompt.** HyperFrames
offers `--low-memory-mode`, which *"pins to 1 worker, uses screenshot capture, and
skips auto-worker calibration to avoid memory thrash on constrained machines"*.
`prompts/authoring.md` now requires it, and tells the agent to treat
`hyperframes check --samples` as optional rather than routine — that command launches
its own Chrome and is the most memory-hungry one available.

**Measured, not assumed.** The known-good sample rendered to completion under a hard
`--memory 1g --memory-swap 1g` cap with that flag:

```
575.8 KB · 9.0s video · rendered in 12.2s
screenshot capture · software gpu · capture 11.6s
out.mp4: 1080x1350, 270 frames, 9.000000 s
```

**But that flag has not yet rescued a real run — and six runs have now died without
producing a video.**

| Run  | Prompt         | Brief            | Lived    | Wrote `index.html`? |
| ---- | -------------- | ---------------- | -------- | ------------------- |
| 1    | original       | long             | ~8 min   | yes, 4 revisions    |
| 2    | original       | long             | ~2.5 min | yes                 |
| 3, 4 | original       | long             | ~5 min   | yes                 |
| 5    | **low-memory** | **one sentence** | **70 s** | **no**              |
| 6    | **low-memory** | long             | ~4 min   | yes (t+150 s)       |

So this section's earlier conclusion — "the render is what exhausts the memory" — is
**not supported**, and neither is "low-memory mode fixes it". No run ever invoked
`hyperframes render`: no `screenshot capture` line appears in any log, and no
`ffmpeg` process was ever seen. The OOM lands between model startup and a render.

**Brief length shifts *when*, not *whether*.** Run 6 was run 5 with only the brief
changed: it survived past 70 s and got a composition on disk, where the one-sentence
brief died before writing anything. A longer brief keeps the model working long
enough to produce output; it does not make the run fit.

**What is established:** the limit is 1Gi, it cannot be raised from any object this
repository controls, and **six attempts produced no `out.mp4`**. The one proven render
of the sample came from *outside* the harness contract, under our own `--memory 1g`
cap — which is where `agents/render-samples/` was produced, and remains the reliable
way to author a composition today.

The earlier version of this section said to raise memory on the `AgentRuntime` and
showed a YAML block; that field is accepted and **ignored**, which is the trap — kept
here rather than deleted.

## Serving the agent as an API (the v1alpha2 session path)

One image serves both contracts, dispatched in `entrypoint.sh` on
`SYMPOZIUM_HARNESS_CONTRACT_VERSION`, exactly as the upstream Pi adapter does:

| Contract   | Shape                                             | Container | Resources                                    |
| ---------- | ------------------------------------------------- | --------- | -------------------------------------------- |
| `v1alpha1` | one-shot `AgentRun` (Job)                         | `agent`   | **hardcoded 1Gi**                            |
| `v1alpha2` | `HarnessSession` (Deployment + ClusterIP Service) | `harness` | **`AgentRuntime.spec.resources` is applied** |

A session is the reason this adapter can render at all: it is the only path where the
memory is ours to set. It also keeps Pi's transcript on the session PVC across turns,
and costs one pod instead of one per request.

**Two constraints came with it, both upstream gaps rather than misconfiguration** — a
Job cannot raise its 1Gi, and a session cannot reach a model outside a hardcoded egress
allowlist. Both are in the section above.

`session-server.mjs` is derived from the maintainer's reference for the contract. Three
deltas: Pi's **tools and skills are enabled** (that is the whole job here, and the
maintained adapters disable both), the toolchain is pointed at our vendored engine and
browser, and each turn gets the authoring method appended to the caller's brief. The
contract itself is upstream's shape — a `/healthz` readiness probe, `POST
/v1/chat/completions` with SSE framing, bounded request and output, serialized turns
because Pi's session file is shared, and client-disconnect cancellation.

### The artifact contract (a workflow caller)

The chat endpoint returns Pi's *report*, not the file — the render lands on the session
PVC. A caller that needs the artifact (an n8n workflow) sends two extra fields and makes
a second request:

1. `POST /v1/chat/completions` with `session_id` identifying the run and `format` naming
   the output kind (`mp4`, `gif`, `webp`, `png`). The output's shape is all request
   data: `width`, `frames` and `durationSeconds` (or `fps`). `frames`/`durationSeconds`
   are what make a long, slow clip possible — 24 frames over 18 s is 1.33 fps, so the
   composition is authored slowly and sampled sparsely, and a type is retuned from the
   registry without touching this image. The server runs Pi in
   `<workspace>/runs/<session_id>/`, tells it to write `out.mp4` there, then converts
   to the requested format in the same directory — `ffmpeg` is already in the image
   (MP4 → GIF at the declared rate/size, the LinkedIn case). The workspace defaults
   to `/tmp/aivideo` because a session container mounts the session PVC at `/tmp` and
   does **not** mount `/workspace`; `SYMPOZIUM_WORKSPACE` overrides it.
2. `GET /artifacts/<session_id>/out.<ext>` fetches it. Only the names the server writes,
   under that run's own directory, are reachable; `session_id` and the file name are both
   validated, and traversal is refused.

The per-run directory is the point: turns are serialized, but a later run must not
overwrite an earlier run's artifact before its caller has fetched it. `session-lib.mjs`
holds the path and format rules, unit-tested under `test/`.

### Deploying it

**The worked manifests are in [`deploy/`](deploy/) — start there.** It holds the
objects that produced the sample, plus the two things a fresh session needs: the PVC
expansion it cannot render without, and the egress policy for a gateway not on
443/8080/9473. The summary below is the shape; `deploy/README.md` is the procedure.

Four objects, and the ordering matters — the runtime must be `Ready` before a session
may reference it:

1. **`SympoziumPolicy`** — `harnessPolicy.enabled: true` plus the image's **full digest**
   in `imagePolicy.allowedRegistries` (matched by string prefix).
2. **`AgentRuntime`** — `contractVersion: v1alpha2`, a
   `session: {protocol: openai-chat, port: 8080}` block, its `capabilities`, and the
   `resources` this whole path exists for.
3. **`Agent`** — `policyRef`, `runtimeRef`, `authRefs`.
4. **`HarnessSession`** — `agentRef`, `runtimeRef`, `desiredState: running`.

Plus a **second NetworkPolicy** for model egress if the gateway does not listen on 443,
8080 or 9473 — see above.

The session's own NetworkPolicy admits **only the Sympozium apiserver** on 8080, which
is deliberate: the docs are explicit that *"the browser never receives a pod IP"*. So a
session is driven through the apiserver, or from inside its own pod for a test — a
`curl` from an unrelated pod fails even when everything is healthy.

## Watching a run

A run takes minutes. With the logging in `entrypoint.sh` the log states each stage,
and after Pi exits it lists the workspace and runs `ffprobe` on `out.mp4`, so the log
itself proves what was produced:

```
--- adapter starting ---
contract:  v1alpha1
engine:    /usr/local/bin/hyperframes (0.8.123)
pi:        /usr/local/bin/pi (0.84.4)
prompt:    /opt/pi-render/prompts/authoring.md (1742 bytes)
...
--- workspace after the run ---
--- out.mp4 ---
codec_name=h264
width=1080
height=1350
nb_frames=270
duration=9.000000
size=587550
```

Without it `kubectl logs` stays empty for the whole run, which is how the first
OOMKill had to be diagnosed from process state rather than from output.

## Publishing

`.github/workflows/publish-images.yaml` owns every image in this repository — this
one, dbt and dlt — because they share one build. Adding an image is one entry in
the workflow, not a new file.

- **On a source change**, after that image's tests pass: publish at merge.
- **Weekly, one image per weekday**: rebuild so base-image CVE fixes land without a
  commit here.
- **Retention: five versions per package**, with `main` never deleted.

## Deploying the one-shot path

For the `AgentRun` path, three objects in order. (The four-object session path above
is the one that can render, since only it can raise the memory.)

1. **A policy that enables harness mode and admits the image by digest.**
   `SympoziumPolicy.spec.harnessPolicy.enabled: true`, plus the full
   `imagePolicy.allowedRegistries` entry ending at a `/` or a complete digest.
   Note the list is matched by **string prefix**: `ghcr.io/datahub-local` without a
   trailing slash would also admit `ghcr.io/datahub-local-evil/…`.
2. **An `AgentRuntime`** pinning the image by digest, declaring
   `contractVersion: v1alpha1`, its `capabilities` and a support owner.
3. **An `Agent`** with `policyRef` and either `runtimeRef` or an explicit
   `task.mode: harness` run.

The image must be published by digest; a tag is rejected at admission and again in
the controller.

One admission quirk worth knowing: a harness run whose `spec.toolPolicy` is **absent**
is rejected with `task.mode "harness" does not support [toolFilter] … (mode supports:
[persona])`, even though nothing sets a tool policy — not the AgentRun, not the Agent,
not the policy, and the CRD defaults nothing. Passing an **explicit empty**
`toolPolicy: {allow: [], deny: []}` makes it pass. The adapter therefore declares
`persona` only: it maps `SYSTEM_PROMPT` onto Pi's prompt, and does **not** translate
`TOOL_POLICY_*`, so claiming `toolFilter` would be the silent-drop the capability
descriptor exists to catch.

## Honest limitations

- **Pi is a coding agent.** Its tool loop is built for codebases. Whether it suits
  composition authoring is an empirical question this image does not answer.
- **Upstream drift is ours.** A Pi release that changes flags or config shapes
  breaks this image, and there is no upstream conformance run for it.
- **No conformance suite has been run against it.** The upstream adapters pass one;
  this image has not, so treat it as experimental.
- **`hyperframes-core` is not bundled.** The pinned package ships three skills
  (`hyperframes`, `hyperframes-cli`, `media-use`); the composition contract is
  stated in `prompts/authoring.md` instead of relying on a file that is not there.
