# A composition authored by the model, in-cluster

The same brief as `../agent-flow/` — *"make a short animated title card about AI
agents at work"* — but **nobody wrote this by hand**. A `pi` coding agent authored it
inside a Sympozium `HarnessSession`, ran HyperFrames' own lint and check, corrected
what they found, and rendered it.

| File | |
| ---- | - |
| `index.html` | the composition, as the model wrote it (9,159 bytes) |
| `demo.mp4` | the render: 1080×1350, **180 frames, 6.000 s**, h264, 700 KB |
| `preview.gif` | a 10 fps preview |

It produced more than the brief asked for: a kicker, a two-line title with an accent
second line, three role cards that take turns (Planner → Builder → Reviewer) with
CSS-drawn icons, numbered badges and captions, a progress pip that fills per role, a
pulsing "LIVE LOOP" dot and a footer naming the sequence. The brief said *"typography
and simple shapes only"*; the motion, the pips and the dot were its own design.

## The brief

```
Make a short animated title card that says "AI agents, at work" and shows three
agent roles taking turns: a planner, a builder and a reviewer.

1080x1350 portrait, about 6 seconds. No stock imagery - typography and simple
shapes only. Follow the method below exactly, including the lint gate.
```

That brief and the method in
[`../adapters/pi-render/prompts/authoring.md`](../../adapters/pi-render/prompts/authoring.md)
are the whole input. Everything else here is the model's work.

## What it did on its own

Reported by the run, and verifiable in the committed source:

- **`hyperframes lint` → 0 errors, 0 warnings.** It hit three
  `nested_structure_needs_subcomposition` warnings first, then **read the linter's
  source** (`hasNestedStructure`, `INLINE_TEXT_TAGS`, `OPAQUE_TAGS`) to restructure the
  clips correctly rather than guessing.
- **`hyperframes check --samples 9` → passed.** Runtime 0 errors, Layout 0 issues,
  Motion 0 warnings, **Contrast 37/37 WCAG AA**.
- It **caught its own 404**: an early check flagged the absolute
  `/opt/.../gsap.min.js` path, so it moved GSAP into `assets/` and re-ran.

That is the loop this capability exists for — a coding agent applying read/edit/run
habits to a composition, using the engine's own gate as the objective.

## How it ran, and the three platform limits it exposed

A `HarnessSession` — not an `AgentRun`. That choice is forced: a Job's agent container
is **hardcoded to 1 GiB** and no CRD field reaches it, while a session Deployment
honours `AgentRuntime.spec.resources`. Three limits had to be lifted, and all three are
upstream gaps rather than misconfiguration:

| Limit | Evidence | Resolution |
| ----- | -------- | ---------- |
| **Memory: 1 GiB, hardcoded** | `agentrun_controller.go` sets `Limits{Memory: "1Gi"}` with nothing feeding it; `Agent.spec.resources` and `AgentRun.spec.resources` are both **rejected** as unknown fields | the **session path**, where `harnesssession_controller.go` does `if runtime.Spec.Resources != nil { container.Resources = *runtime.Spec.Resources }` → **6 GiB** |
| **Model egress** | the session's NetworkPolicy hardcodes `{53, 443, 8080, 9473}`; this cluster's gateway listens on **4000** | an additive NetworkPolicy permitting port 4000 |
| **Disk: 974 MiB against a 1024 MiB gate** | `checkDisk()` in the engine: `if (freeMb < 1024)` → a hard error with no override. The session PVC is hardcoded `1Gi` = 974 MiB, so it can *never* pass | expanded the PVC to **8 GiB**. The controller sizes a claim only at creation, so it does not fight the change |

The disk one is worth stating plainly, because the model diagnosed it exactly: the
volume and the gate are both fixed, at 974 MiB and 1024 MiB — **50 MiB short,
structurally impossible to satisfy** until the volume grows.

## Reproducing it

The session objects are documented in
[`../adapters/pi-render/README.md`](../../adapters/pi-render/README.md). In outline:
a `SympoziumPolicy` admitting the image's digest, an `AgentRuntime` with
`contractVersion: v1alpha2` and a `session` block, an `Agent`, a `HarnessSession`, plus
the egress NetworkPolicy. Then POST the brief to the session's
`/v1/chat/completions` — through the Sympozium apiserver, or from inside the pod, since
the session's NetworkPolicy admits only the apiserver.

**Not reproducible as committed:** the session PVC is expanded by hand, and the
controller will create a fresh 1 GiB claim for any new session. A new session needs the
same expansion before it can render.

## What it is not

- **Not a template or a spec.** The render service's typed-spec path cannot express
  this; there is no `layout` for "three agent roles taking turns". This is the other
  capability, and the two are compared in
  [`../README.md`](../README.md).
- **Not deterministic.** Re-running the same brief produces a different composition.
  That is the trade: the render service gives you the same output from the same input,
  and cannot do this; this does this, and cannot give you the same output twice.
