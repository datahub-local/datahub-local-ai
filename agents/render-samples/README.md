# Agent-authored composition samples

A composition **written by an agent**, not by a template in the render service. It
exists to show the difference: the render service's typed spec can express five
layouts, while a composition authored against HyperFrames' own skills can express
anything the brief asks for.

## `agent-flow/`

The brief was one sentence: *"a smooth, modern animation showing how a team of AI
agents collaborates to build a project."*

| File | What |
| ---- | ---- |
| `index.html` | The composition — authored by an agent following the `hyperframes-core` skill contract |
| `agent-flow.mp4` | The render: 1080×1350, 270 frames, 9.0 s, H.264 |
| `agent-flow.gif` | A 10 fps preview |

It draws a work graph — User Request → Planner → two parallel Coders → QA →
Deployment — with a pulse travelling each connector before the next node lands.
Nothing here is a variable of a service template; the layout, palette, type and
motion were all chosen for this brief.

## How it was made, and how to remake it

The loop is the agent's, and HyperFrames' own tooling is the gate:

```
brief ──▶ agent + hyperframes skills ──▶ index.html ──▶ lint/check ──▶ render ──▶ mp4
                                          (the artifact)    (the gate)    (the engine)
```

1. The agent reads the HyperFrames skill (`hyperframes-core` for the composition
   contract, `hyperframes-animation` for motion) — installed by
   `hyperframes skills`, which is what makes this reproducible rather than ad hoc.
2. It writes `index.html`: one paused timeline registered at
   `window.__timelines["main"]`, timing on `data-*` attributes, `class="clip"` on
   timed elements.
3. `hyperframes lint` is run and **fixes are made from its findings**. On this
   sample lint caught two real bugs — a GSAP tween on `top` (which snaps to
   integer pixels and stutters under frame-stepping; must be a transform) and a
   timed element with no `id` (no stable Studio edit target).
4. `hyperframes render` produces the MP4.

The render uses the same toolchain the render service ships (Node 22, Chrome,
FFmpeg, a vendored GSAP). `index.html` references `./vendor/gsap.min.js`, never a
CDN, so it renders offline:

```
mkdir -p vendor && cp <render service>/vendor/gsap.min.js vendor/
docker run --rm -v "$PWD:/work" -w /work <render-image> \
  sh -c 'hyperframes lint && hyperframes render -o out.mp4 -f 30'
```

## Relationship to the render service

These are two different products and both are wanted:

- **The render service** (`agents/n8n/render/`) takes a *typed spec* and returns a
  video deterministically. It is what a scheduled workflow should call, because the
  same input always yields the same output and the caller cannot inject markup.
- **An agent-authored composition** (this directory) is what a one-off, bespoke
  brief wants, where no template fits.

Neither replaces the other. See
`openspec/changes/add-agent-authored-compositions/`.
