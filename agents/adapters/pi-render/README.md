# Pi render adapter

A Sympozium harness adapter that lets an agent **author a HyperFrames composition
and render it** inside a run. Built from the upstream Pi adapter's base image with
the render toolchain added and Pi's tools enabled.

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

It **derives from our own render image**, not from the upstream Pi adapter's image.
The reasoning is the point:

- Upstream's Pi image is `node:22-alpine` + `jq` + `git` + `pi-coding-agent`. What it
  does **not** have is a browser or an encoder, which authoring needs.
- Our render image already has both — plus a vendored HyperFrames and GSAP, with the
  read-only-rootfs and `HOME` problems already found and fixed.
- Deriving from the Pi image would mean re-adding what ours already carries, and
  inheriting a release cadence for a decision we are overriding.

So: **one toolchain, built once — ours.** This image adds only the agent loop and the
adapter contract on top.

| Change | Why |
| ------ | --- |
| `jq` | the adapter contract builds the result payload with it; the Debian base does not carry it |
| `@earendil-works/pi-coding-agent@0.84.4` | the agent loop, pinned and installed with lifecycle scripts disabled, exactly as upstream installs it |
| the engine moved to `/opt/hyperframes` | so the prompt and the entrypoint do not depend on the base image's `WORKDIR` |
| `prompts/authoring.md` at `/opt/pi-render/prompts/` | the instruction is a file, read at run time, not inlined in shell |
| `--no-tools` **dropped** | so the agent can write the composition and run the engine |
| `--no-skills` **dropped** | so the agent can read the skills that ship in the image |

Deliberately **not** carried over: `git`. Upstream's Pi image has it because Pi offers
a repo-cloning tool; nothing in this adapter or the authoring loop calls it, and a
tool nothing uses is a surface to keep patched for no reason.

Everything else is upstream's, unchanged: the contract check, the credential
checks, the provider config, the `v1alpha1` result protocol, the bounded output and
the `/ipc/control/skip` handling.

## Verified

Built and exercised on 2026-10-04, under the platform's own constraints — **UID
1000, read-only root filesystem, `--network none`**:

| Check | Result |
| ----- | ------ |
| Toolchain present as UID 1000, read-only rootfs | node, jq, chromium, ffmpeg, ffprobe, hyperframes, pi — **all found** |
| A render succeeds **offline** | the known-good sample rendered 1080×1350, **270 frames, 9.000 s** |
| `lint` runs as the agent's gate | `0 error(s), 1 warning(s)` on the sample |
| The prompt file is readable by UID 1000 | `/opt/pi-render/prompts/authoring.md`, 1742 bytes |
| Pi runs with tools available | `pi 0.84.4`, described as "AI coding assistant with read, bash, edit, write tools"; `--no-tools` is not passed |

Two defects were found and fixed by this test, which is why it is not a formality:
the Debian base has no `jq` (every run would have failed on the result payload), and
the prompt file was unreadable by UID 1000 because it was copied before the `chown`.

**Not yet verified:** a full run driven by the model — an `AgentRun` in the cluster
where Pi itself writes the composition, reads lint, corrects and renders. That is the
remaining question, and it is the one that decides whether Pi's coding-agent loop
suits authoring. Everything up to the model call is proven.

## Cost

**This image derives from a deployed artifact.** A render-service change flows into
this adapter's next build. That is either one toolchain kept in step (the intent) or
unwanted coupling, depending on your view — but it is one direction only: the render
image knows nothing about this adapter.

**Upstream drift is ours.** No upstream conformance run covers this image.

## Resources: the 1Gi default, and the one knob that works

**The agent container's 1Gi default OOMKills a default render**, and every run died
that way — exit 137, at 4–10 minutes, always mid-`check`, never reaching
`hyperframes render`. Pi, a Chromium instance and a multi-worker render share one
container; a normal render launches one Chrome per worker at ~256 MB each, so
`--workers=auto` cannot fit.

**It cannot be raised from anything this repository controls.** All four candidate
fields were tested against the live cluster on 2026-10-04:

| Where | Result |
| ----- | ------ |
| `AgentRuntime.spec.resources` | accepted, runtime reports `Ready` — and **the pod still shows 1Gi**. No effect. |
| `Agent.spec.agents.default.resources` | **rejected**: `unknown field "spec.agents.default.resources"` |
| `AgentRun.spec.sandbox.resources` | accepted, but creates a **separate third container** (`sandbox: 512Mi`); the agent stays 1Gi |
| `SympoziumPolicy` | has no resource field at all |

The Sympozium harness docs' operating note says *"Node-based harnesses sit close to
that memory limit; raise it on the Agent if one is OOM-killed."* **That is a
documentation/implementation mismatch in v0.10.87** — the Agent has no such field.
Worth reporting upstream.

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

| Run | Prompt | Brief | Lived | Wrote `index.html`? |
| --- | ------ | ----- | ----- | ------------------- |
| 1 | original | long | ~8 min | yes, 4 revisions |
| 2 | original | long | ~2.5 min | yes |
| 3, 4 | original | long | ~5 min | yes |
| 5 | **low-memory** | **one sentence** | **70 s** | **no** |
| 6 | **low-memory** | long | ~4 min | yes (t+150 s) |

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
one, the render image, dbt and dlt — because they share one build. Adding an image
is one entry in the workflow, not a new file.

- **On a source change**, after that image's tests pass: publish at merge.
- **Weekly, one image per weekday**: rebuild so base-image CVE fixes land without a
  commit here. This image also rebuilds when the render image's sources change,
  because its base moving is a change to it.
- **Retention: five versions per package**, with `main` never deleted.

## Deploying it

The platform requires, in order:

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
