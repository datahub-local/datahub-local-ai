# Pi harness gate — findings (task 2.1/2.2)

Probe date: 2026-10-04. Runtime `pi-session-v0-84-4`
(`ghcr.io/sympozium-ai/harness-adapters/pi@sha256:8c8f0df071dc5307b3b557e0233a70757d8a4be17cb688c1ca725cb41001bbd5`),
contract `v1alpha2`.

**Corrected 2026-10-04 after reading the official Sympozium documentation**
([Harness Mode](https://deploy.sympozium.ai/docs/modes/harness/),
[AgentHarness](https://deploy.sympozium.ai/docs/guides/agentharness/),
[Writing a Harness Adapter](https://deploy.sympozium.ai/docs/modes/harness-adapters/)).
The probe's **observations stand**; one **inference was wrong** and is corrected
below. Read
[the correction](#correction-tool-use-is-the-adapters-business-not-harness-modes)
before acting on the conclusion.

## The blocker: Pi is session-only, and needs a model credential it cannot get

Three findings, in the order the admission path enforces them.

### 1. Pi cannot host a one-shot `AgentRun` at all

```
admission webhook "vagentpod.sympozium.ai" denied the request:
harness: runtime "pi-session-v0-84-4" is session-only (v1alpha2);
start it as a HarnessSession instead of an AgentRun
```

Every persona in this repository runs as an `AgentRun` (a Kubernetes Job, `mode:
task`). Pi runs only as a **`HarnessSession`** — a long-running session pod. Both
cluster runtimes are `v1alpha2` and therefore session-only: `pi-session-v0-84-4`
and `hermes-session-v0-20-6`.

This is not a config toggle. Adopting Pi means changing *how a persona is run*, not
just adding `runtimeRef`.

### 2. A `HarnessSession` has nowhere to put a model

A `HarnessSession` spec accepts exactly four fields: `agentRef`, `runtimeRef`,
`idleTimeout`, `desiredState`. There is no model field. The runtime itself declares
`spec.model: null`, so the model must come from the Agent, and the webhook says so:

```
Ready=False: AgentRuntime "pi-session-v0-84-4" needs spec.model.provider/model,
or an Agent with exactly one provider credential and a default model
```

Supplying that (an `Agent` with `authRefs` + a default model) moved the session from
`Failed` to `Pending` and the pod started.

### 3. The harness demands a credential key this cluster's secret does not carry

The session pod then crash-looped:

```
sympozium pi session: OPENAI_API_KEY is required
```

The raw session pod spec shows the controller injects **many** provider key names,
every one `optional: true`:

```
OPENAI_API_KEY, ANTHROPIC_API_KEY, AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT,
OLLAMA_HOST, GOOGLE_API_KEY, MISTRAL_API_KEY, GROQ_API_KEY, DEEPSEEK_API_KEY,
OPENROUTER_API_KEY, API_KEY   ← all from secret litellm-auth-credentials
```

But that secret holds only `API_KEY`, `api_key` and `endpoint` — so `OPENAI_API_KEY`
is absent, and the Pi harness **requires that exact name**. The harness reads
`OPENAI_API_KEY` regardless of `MODEL_PROVIDER=openrouter` being set correctly
alongside it.

## What this means

| Check | Result |
| ----- | ------ |
| Pi runtime is Ready and bindable | **Yes** |
| Pi can run one of our persona `AgentRun`s | **No** — session-only |
| A `HarnessSession` can be created against Pi | **Yes** |
| The session starts | **No** — `OPENAI_API_KEY` required and not present |
| File write / shell / toolchain checked | **Not reached** — the pod never served |

The three capability checks the probe was built to answer (write a file, run a
command, reach Node/Chrome/FFmpeg) **were not reached**, because the session never
started. They remain **unverified**.

## Result: the Pi harness cannot author a composition

The credential fix worked and the session started cleanly — `phase=Ready`, pod
`1/1`, zero restarts, `sympozium pi session listening on 8080`. So the gate ran to
completion and produced a definite answer:

```
1. FILE WRITE   PASS   (echo ok > probe.txt; cat probe.txt  ->  ok)
2. SHELL        PASS   (sh is present)
3. TOOLCHAIN    FAIL   node v22.19.0 present; chromium, ffmpeg, ffprobe absent;
                        no python3, no hyperframes package
```

The toolchain half was answered by inspection rather than inference, and the real
blocker is deeper than a missing binary — it is the harness's own contract. Both
adapter paths spawn Pi with **every capability switched off**:

```js
pi --print --no-skills --no-prompt-templates --no-tools --provider sympozium --model …
```

(`/usr/local/bin/sympozium-pi-adapter` for v1alpha1; the same argument list in
`sympozium-pi-session` for v1alpha2.)

**`--no-tools` means no file write, no shell, no edit and no workspace access.**
`--no-skills` means it cannot read the HyperFrames authoring skills either. The Pi
harness is a **text-in/text-out completion endpoint**: it answers a prompt while the
session pod holds it. Tool use is not something it can be configured into — it is
excluded by the command line the adapter builds.

So the capability checks resolve as:

| Capability the work needs | Pi harness |
| ------------------------- | ---------- |
| Write a composition file | **No** — `--no-tools` |
| Run `lint` / `render` | **No** — `--no-tools` |
| Reach the toolchain | **No** — no Chrome, FFmpeg; and it could not invoke them anyway |
| Read the HyperFrames skills | **No** — `--no-skills` |

This is not a credential or configuration gap **in the maintained Pi adapter**.
`--no-tools` is passed unconditionally by the adapter that Sympozium ships, and the
official documentation states it as deliberate behaviour:

> "Both continue to **disable tools and skills**. Treat a session as a bounded
> interactive workspace, not durable platform Agent memory or a general exposed
> OpenAI gateway." — *AgentHarness guide*

> "Current session adapters deliberately provide no MCP/SkillPack tools, native
> tools, persona mapping, subagents, or trusted usage metrics." — *AgentHarness guide*

### What follows

**Pi cannot author a composition, so an authoring persona must not be built on it.**
The proven path stays what it is: author and render where tool use and the toolchain
already exist — the render image — as `agents/render-samples/agent-flow/` shows.

A Pi persona remains a reasonable thing for **text** work — a prompt answered, a
report or a spec drafted — because that is precisely what it is built for.

## Correction: tool use is the adapter's business, not harness mode's

The sentence I first wrote here — *"even a harness image with Node, Chrome and FFmpeg
baked in would still be unable to call them"* — **is wrong, and the official docs say
so plainly.** It generalised from the maintained Pi adapter to harness mode itself.
The correct position:

> "**`agent-runner`'s tool loop.** The harness brings its own, or none." — *Harness Mode*

> "Harness mode changes the agent loop, not the platform boundary around the run."

> "**BYO means a contract-compatible adapter image, not an arbitrary upstream harness
> image.** Sympozium ships the seam, not the harnesses." — *Harness Mode*

Tool use is a property of **the image**, not of the mode. The Pi and Hermes adapters
choose to disable it; another adapter need not. And the platform supplies what a
tool-using adapter requires, per the adapter contract:

| Provided to every adapter | Why it matters for authoring |
| ------------------------- | ---------------------------- |
| `/workspace` — the run's PVC, and the container's working directory | the composition is written here and survives the run |
| `$HOME` = `/home/agent`, an `emptyDir` | the only writable path besides `/workspace`, `/ipc/output`, `/tmp`; enough for a Chrome profile, which is the exact constraint the render image's `HOME` fix addressed |
| `/tmp`, writable, against a read-only rootfs | a render's scratch space |
| UID 1000, non-root, `readOnlyRootFilesystem`, `drop: [ALL]`, RuntimeDefault seccomp | the render image already runs under this |
| its own `ENTRYPOINT` — Sympozium imposes no command | the image can carry Node, Chrome and FFmpeg and drive them |

So a **hyperframes harness adapter is a supported, documented path**, not a dead end.
It is a normal container image that: reads `TASK`, runs the HyperFrames toolchain over
it, and emits the result on `$SYMPOZIUM_RESULT_PATH` plus the `__SYMPOZIUM_RESULT__`
marker. The official docs give [a minimal adapter](https://deploy.sympozium.ai/docs/modes/harness-adapters/#a-minimal-adapter)
(~30 lines of bash) and the full contract, including that it must be digest-pinned,
must declare its `capabilities` honestly, and must fit the pod security context.

### Built: `agents/adapters/pi-render/`

The extended-Pi route was taken (the user's choice), and the image is built and
verified on 2026-10-04. It is the upstream Pi adapter's base image —
`node:22.19.0-alpine3.21` + `jq` + `git` + `@earendil-works/pi-coding-agent@0.84.4`
— plus the render toolchain, with `--no-tools` and `--no-skills` dropped. Alpine
carries both `chromium` and `ffmpeg`, so the base stays upstream's and the diff is
small.

Verified **under the platform's own constraints** (UID 1000, read-only root
filesystem, `--network none`):

| Check | Result |
| ----- | ------ |
| Toolchain as UID 1000, read-only rootfs | node, jq, git, chromium, ffmpeg, ffprobe, hyperframes, pi — all found |
| Offline render of the known-good sample | 1080×1350, **270 frames, 9.000 s** — identical to the host render |
| `lint` runs | `0 error(s), 1 warning(s)` |
| Pi's tools available | `pi 0.84.4`, "AI coding assistant with read, bash, edit, write tools"; `--no-tools` absent |

**Still unverified, and it is the decisive question:** a full `AgentRun` in the
cluster where Pi writes the composition, reads lint's findings, corrects and
renders. Everything up to the model call is proven; whether Pi's coding-agent loop
suits authoring is not.

The cost is stated in the adapter's README: this tracks Pi's release cadence for the
adapter, upstream does not maintain it, and no conformance suite has been run
against it.

### Note for anyone revisiting this

The `--no-tools` flag is the reason to read the **adapter image**, not the CRD, when
asking what a harness can do — the runtime's `capabilities: null` ("claims nothing")
is accurate but says nothing about what the adapter *could* declare. The maintainer
program for the Pi/Hermes adapters lives at
[sympozium-ai/harness-adapters](https://github.com/sympozium-ai/harness-adapters),
and its conformance report is the thing to read before enabling one.
