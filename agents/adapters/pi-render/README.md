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

## Publishing

`.github/workflows/publish-pi-render-adapter-image.yaml` publishes it, digest-pinned
and multi-arch, from `agents/adapters/pi-render`. It also rebuilds when the render
image's sources change, because the base moving is a change to this image.

It is in the rebuild/prune matrix in `.github/workflows/rebuild-and-prune-images.yaml`,
so it receives a weekly base-image rebuild and is held to the five-version retention
rule along with every other image.

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
