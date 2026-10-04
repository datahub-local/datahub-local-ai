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

| Change | Why |
| ------ | --- |
| `chromium`, `ffmpeg`, `ffprobe` | the engine renders by seeking a real browser and encodes with FFmpeg; neither is in the upstream image |
| HyperFrames, pinned and vendored | `lint` and `render` are the agent's own gate; installed at build time so a run needs no network |
| a vendored GSAP | the composition must render offline; a CDN reference would fail in-cluster |
| the bundled HyperFrames skills | the agent authors against the engine's own contract instead of guessing |
| `--no-tools` **dropped** | so the agent can write the composition and run the engine |
| `--no-skills` **dropped** | so the agent can read the skills that ship in the image |

Everything else is upstream's, unchanged: the contract check, the credential
checks, the provider config, the `v1alpha1` result protocol, the bounded output and
the `/ipc/control/skip` handling.

## Verified

Built and exercised on 2026-10-04, under the platform's own constraints — **UID
1000, read-only root filesystem, `--network none`**:

| Check | Result |
| ----- | ------ |
| Toolchain present as UID 1000, read-only rootfs | node, jq, git, chromium, ffmpeg, ffprobe, hyperframes, pi — **all found** |
| A render succeeds **offline** | the known-good sample rendered 1080×1350, **270 frames, 9.000 s** — identical to the host render |
| `lint` runs as the agent's gate | `0 error(s), 1 warning(s)` on the sample |
| Pi runs with tools available | `pi 0.84.4`, described as "AI coding assistant with read, bash, edit, write tools"; `--no-tools` is not passed |

**Not yet verified:** a full run driven by the model — an `AgentRun` in the cluster
where Pi itself writes the composition, reads lint, corrects and renders. That is
the spike's remaining question, and it is the one that decides whether Pi's
coding-agent loop suits authoring. Everything up to the model call is proven.

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
  stated inline in the prompt instead of relying on a file that is not there.
