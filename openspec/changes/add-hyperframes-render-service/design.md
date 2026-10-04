# Design

## Context

See `proposal.md` for motivation and `specs/` for the behavior contracts. This records the
constraints that shape the build; the cluster-facing ones were read live, the render ones
from a local spike of HyperFrames 0.8.114.

- **The studio's spec is flat and the workflow cannot render video.** `merge_assets` fills
  a two-column row template; `capture_frames` seeks CSS animations and `img2webp`/`gm`
  assemble WebP/GIF. `motion_clip` is declared unavailable *because the n8n image has no
  FFmpeg*, and the n8n image is not a place to add Node 22 + Chrome + FFmpeg.
- **HyperFrames is the same architecture, matured** (verified by spike): headless Chrome
  `beginFrame` capture, chunked FFmpeg encoding, parallel workers, static-frame dedup. Its
  composition contract is HTML with `data-composition-id` / `data-start` / `data-duration` /
  `data-width` / `data-height`, `.clip` elements with `data-track-index`, and a seekable
  animation registered as `window.__timelines["<id>"]` (GSAP; also CSS/WAAPI/Lottie/Three
  adapters).
- **Spike measurements** (this box: 6-core, software GPU, 5 workers): an 8 s 1080×1350
  30 fps composition rendered in **4.6 s to a 565 KB MP4**; the same at 15 fps GIF was
  2.0 MB in 9 s. Requirements observed: Node ≥22 (ran on v26), **FFmpeg and FFprobe on
  PATH**, and Chrome headless shell (~114 MB). The scaffold loads GSAP from a CDN, so a
  real deployment must vendor it.
- **Two callers, two protocols.** n8n is deterministic and its only MCP node is an
  AI-agent tool, so it reaches in-cluster services by HTTP (`...svc.cluster.local`).
  Sympozium agents speak MCP. `datahub-local-ai-mcp` is a Python 3.13 platform whose
  Dockerfile states one image per server is *"a COPY difference and not a dependency
  difference"* over four packages — a Node/FFmpeg/Chrome server breaks that invariant.
- **Deployment homes.** Images publish from this repo as
  `ghcr.io/datahub-local/datahub-local-ai-*:main` (dbt/dlt pattern, multi-arch, path-filtered
  workflow). Core's `releases/automation/` holds n8n and the Chromium service. This repo's
  Sympozium chart declares its MCP servers via `sympozium_mcp_servers` values, and the agent
  egress policy opens **8080 only** to pods labeled `app.kubernetes.io/name: mcpserver`.

## Goals / Non-Goals

**Goals:**

- Add an MP4/video path with HyperFrames-class output, without disturbing the WebP/GIF
  path or its callers.
- Keep composition authoring deterministic and offline; keep model output as data.
- Give both n8n and Sympozium agents the same render capability through front doors that
  fit each.

**Non-Goals:**

- Model-authored HTML compositions, the HyperFrames catalog, audio, shader transitions and
  agent skills. Those are the "rich authoring" path and need an isolation boundary this
  repo does not have.
- Migrating the WebP/GIF types to the service (a follow-up; it removes the duplication).
- Changing the trigger contract, the run record, the LinkedIn pipeline, or the animation
  budget.

## Decisions

### D1. One engine, two front doors

A render engine exposes an HTTP API; n8n calls it directly, and a thin pure-Python `render`
MCP server in `datahub-local-ai-mcp` proxies it for agents. This is the only shape that
serves a deterministic workflow and an MCP-agent fleet without putting a Node/Chrome
toolchain into a Python MCP image or hand-rolling MCP JSON-RPC inside n8n.

*Alternatives considered:* MCP-only — rejected; n8n would have to speak the MCP wire
protocol from an `httpRequest` node, which is brittle and has no deterministic client node.
Everything in ai-mcp — rejected; it is the one server that breaks that repo's shared-image
and dependency-set invariant.

### D2. The engine takes a typed spec, never HTML

The service accepts a validated content spec and authors the composition itself from
versioned templates. It rejects requests carrying markup or script. This preserves the
existing rule that model output is data, keeps renders reproducible, and avoids executing
untrusted HTML. The n8n workflow already validates the spec (`parse_spec`) and sends only
that; the MCP tool exposes a spec argument, not a scene.

*Alternatives considered:* letting the model author HyperFrames HTML via their skills —
richest output and the reason HyperFrames exists, but it is executable model output and
needs a sandbox this repo does not have; deferred, recorded here. Accepting HTML from
trusted callers only — rejected for now; two trust levels for one endpoint is more surface
than the value.

### D3. Video is a new opt-in type; WebP/GIF does not move

The registry gains a video type; the workflow routes it to the service and returns the MP4
as an asset. Nothing about the existing animated WebP/GIF types, their spec, the LinkedIn
GIF cap or its `--require-edge` graph changes. This is the smallest blast radius and keeps
`add-linkedin-animated-post-media` valid.

*Alternatives considered:* replace WebP/GIF with MP4 — rejected; it changes a frozen
caller contract and the LinkedIn format. Add MP4 **and** switch LinkedIn to video in the
same change — rejected as scope creep; video posts are their own caller change.

*Known cost:* the service has composition builders while `merge_assets` keeps its markup
builders, so the same spec is rendered by two pieces of code until the follow-up migration.
The spec is the single contract, and both are tested against it.

### D4. Image here, deploy in core, proxy in ai-mcp

The engine sub-project (`agents/n8n/render/`) and its publish workflow live here, beside
the composition templates that are its source. Core's automation release deploys it with
the `app-template` chart next to n8n, exactly as it deploys n8n-chromium, so the
NetworkPolicy that matters is local. The `render` MCP server is a plain Python package in
`datahub-local-ai-mcp` with a required `RENDER_URL` (the `PROMETHEUS_URL` pattern — a
guessed address must fail, not report empty renders).

*Alternatives considered:* everything in core — rejected; the composition templates are
this repo's concern and would be duplicated across repos. Everything here — rejected; it
bypasses core's release and network structure.

### D5. Offline by construction, pinned

GSAP is vendored into the image (the spike's scaffold fetched it from a CDN), Chrome and
fonts are bundled, and the service renders with no network. The HyperFrames version and the
Chrome build are pinned so an upgrade is a deliberate image change; HyperFrames pins Chrome
for the same reproducibility reason.

*Alternatives considered:* allow the CDN — rejected; it fails in-cluster and makes renders
non-reproducible. CSS/WAAPI only — rejected; the composition model and any future catalog
blocks assume a timeline adapter, and GSAP is small and vendorable.

### D6. One builder per layout, in the engine

The composition vocabulary (bounded `layout` = `stats`/`flow`/`timeline`/`comparison`/`bars`,
per-item icons from an offline registry, bounded theme, structural motion) lives in the
engine's templates, one deterministic builder per layout emitting a HyperFrames composition.
This absorbs the superseded `add-visual-studio-diagram-layouts` change and puts the MP4
builders where the render happens instead of also in n8n.

*Alternatives considered:* build HyperFrames compositions in `merge_assets` and POST the
HTML — rejected; it is the "engine takes HTML" shape D2 excludes and duplicates layout
logic across the two renderers.

### D7. Bounds on both fronts

The service declares a duration, resolution and type cap, a render timeout, and resource
limits; the MCP proxy's timeout must exceed a render; the studio keeps its per-request type
cap. The engine can run several capture workers (the spike used 5), so worker count is a
deployment knob, not a fixed constant.

### D8. The engine can hand an asset off by reference

An MP4 is hundreds of KB, but the MCP runner clamps every answer to a few KB
(`Registry.call`), so the MCP tool cannot return the bytes — it would be a truncated,
unplayable file. The engine therefore can persist a render under a content-addressed id and
return `{id, url, …}`; a `GET /files/<id>.mp4` serves it for a retention window. n8n keeps
taking the bytes inline because it can. This is the one addition implementation forced
beyond "return a rendered MP4": the two callers have different transport limits, and the
bounded one needs a handle rather than the file.

*Alternatives considered:* have the MCP tool return the bytes anyway — rejected; the clamp
truncates them. A shared volume between the engine and the agent — rejected; agents are
sandboxed with no shared mount. Metadata only, no URL — rejected; the caller would have to
know the store's path convention, which is the URL by another name.

## Risks / Trade-offs

- **Cross-repo ordering blocks everything.** No video until the image is published, core
  deploys it and the policies allow the calls. → tasks are sequenced and marked `blocked
  by`; the n8n type is added only after a direct HTTP probe succeeds.
- **A missing NetworkPolicy looks like a silent feature gap.** Agent egress opens 8080 only
  to `name=mcpserver`; the proxy needs egress to the engine and n8n needs egress to it
  (n8n's own policy is `[UNVERIFIED]` here). → explicit policies in core; verify with a
  probe from each caller, not from a laptop.
- **Engine cost.** Each render launches Chrome and FFmpeg and may use several workers. →
  resource requests/limits, a bounded concurrency, and the request cap; measure in the probe.
- **Duplicated layout builders drift.** → one spec contract, tests on both; the WebP/GIF
  migration is the lasting fix.
- **Vendored runtime and version drift.** HyperFrames is 0.8.x and moves quickly; a pinned
  version protects renders but must be bumped deliberately with a re-render check. →
  pin, vendor GSAP, record both in the image.
- **The MCP tool could be asked for arbitrary scenes.** → spec-only, bounded, same caps as
  HTTP; no HTML argument.

## Migration Plan

1. Land the engine: Dockerfile (Node 22 + FFmpeg + Chrome + vendored GSAP + pinned
   HyperFrames), HTTP server, composition templates, and the publish workflow; verify a
   local container renders a spec to MP4 with the network disconnected.
2. Deploy: core adds the Deployment/Service and the two NetworkPolicies, and the image tag.
   Verify an in-cluster `POST /render` from a throwaway pod returns an MP4.
3. n8n: add the video type to `visual_types.json` and the render branch to
   `visual_studio.workflow.json`, applied live with `--require-edge`; verify with
   `Visual Studio Test` that the video asset is an MP4 and the other types are unchanged.
4. ai-mcp: add `servers/render/` plus the `RENDER_URL` env wiring in this repo's Sympozium
   chart; verify the tool lists and one render through an agent probe.
5. Rollback: remove the type from the registry (the path is opt-in) and detach the service;
   WebP/GIF and every existing caller are untouched.

## Open Questions

- Whether to migrate the WebP/GIF types onto the service and delete the n8n builders. This
  is a follow-up, not part of this change, and does not alter the approach.
- Engine replica and worker sizing. Measured in the deploy probe; a deployment knob.
- Whether agents should later get richer authoring (their own compositions) behind an
  isolation boundary. Deferred with D2; needs its own design.
