# Proposal

## Why

The studio's animated "diagram" renders a title over a list of label/value rows because
its content spec is flat and its one template only draws rows. A local spike of
[HyperFrames](https://github.com/heygen-com/hyperframes) — which makes the same
architectural bet as our `capture_frames` branch (seek frames in headless Chrome, encode)
but with a real composition/timeline model, a block catalog and FFmpeg — rendered an 8 s,
1080×1350 motion graphic from our own homelab text in 4.6 s (240 frames, 565 KB MP4):
kinetic title, drawn connectors with arrowheads, a spinning gear, counters and bars. That
is the class of output the studio cannot reach today.

The gap is not the browser renderer, which we already have. It is (a) a composition and
timeline authoring layer, and (b) FFmpeg/Chrome infrastructure that the n8n image
deliberately does not carry (the reason `motion_clip` is declared unavailable). Neither
belongs inside the n8n pod, so this change adds a dedicated render service and points the
studio at it.

## What Changes

- Add a **visual render service** (new sub-project in this repo): a container with a
  pinned HyperFrames version, FFmpeg and Chrome that accepts a **typed content spec** over
  HTTP and returns **MP4**, plus its own health and error surface. It authors the
  composition itself from versioned templates, so it never executes model-authored HTML.
- Add a **video asset type** to the Visual Studio registry, produced by calling the render
  service. The existing animated WebP/GIF types and their path are unchanged; video is
  opt-in per request.
- Fold the diagram-composition vocabulary into the service's templates: bounded `layout`
  (`stats`, `flow`, `timeline`, `comparison`, `bars`), per-item icons from an offline
  registry, bounded theme tokens, and structural motion (drawn connectors, travelled
  arrows, spinning icons). `layout` is optional and defaults to today's list.
- Add a thin **`render` MCP server** to `datahub-local-ai-mcp` that proxies the service, so
  Sympozium agents can request renders; n8n calls the service's HTTP API directly because a
  deterministic workflow is not an MCP client.
- Deploy the service in **core's automation release** beside n8n, with the ingress and
  egress policies the two callers need.

Not a breaking change for existing callers: the WebP/GIF types, their specs and the
LinkedIn animated-GIF path do not move.

## Capabilities

### New Capabilities

- `visual-render-service`: the HTTP render service — it accepts a typed content spec,
  renders an MP4 and reports bounded metadata, refuses arbitrary HTML, and renders fully
  offline.

### Modified Capabilities

- `visual-studio`: adds a video asset type produced by the render service, and the
  composition vocabulary (layout, icons, theme, structural motion) the service renders.

Archive order: archive `add-linkedin-animated-post-media` **before** this change. Both
MODIFY `Animation is rendered from a browser timeline`, and this change carries the union
(declared format selects the encoder **and** the video carve-out); archiving it first would
let the earlier change's narrower text replace the requirement and drop the carve-out.

## Impact

- **This repo**: new render sub-project (`agents/n8n/render/`) with Dockerfile, HTTP
  server and composition templates; a publish workflow mirroring dbt/dlt; a new type and a
  render branch in `agents/n8n/workflows/visual_studio.workflow.json`; the `render` MCP
  server declared in `agents/sympozium/values/default.yaml.gotmpl` with a `renderUrl` env in
  `templates/mcpservers.yaml`; tests.
- **datahub-local-core** (`blocked by`, cross-repo): the engine deployed with the
  `app-template` chart in `releases/automation/` (as n8n-chromium is), its image tag in
  `values/_version.yaml`, and its NetworkPolicy declared through the chart's own
  `networkpolicies:` key rather than a standalone template.
- **datahub-local-ai-mcp** (`blocked by`, cross-repo): `servers/render/` with a required
  `RENDER_URL`, its tools, tests, and the CI `expect_tools`/matrix entries.
- **Risk of duplication**: the service has its own composition builders while the n8n
  WebP/GIF path keeps its `merge_assets` builders. Migration of WebP/GIF to the service is
  an explicit follow-up, not part of this change.
