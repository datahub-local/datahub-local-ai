# Visual render service

A typed content spec in, an MP4 motion graphic out.

```
POST /render   {"spec": {...}, "options": {"width":1080,"height":1350,"fps":30}}
               -> 200 video/mp4  (X-HF-Duration-Ms, X-HF-Frames, X-HF-Width, X-HF-Height, ...)
GET  /healthz  -> 200 {"status":"ok"}   (never renders)
```

## Why it exists

The studio's in-workflow renderer seeks CSS animations in headless Chromium and
assembles WebP/GIF with `img2webp`/GraphicsMagick. The n8n image has no FFmpeg,
so it cannot produce video. This service carries the pieces the n8n pod
deliberately does not — Node 22, FFmpeg, Chrome — behind one HTTP endpoint, and
points the Visual Studio workflow's video type at it.

## The trust boundary

The service **accepts a content spec and nothing else**. It authors the
composition itself from versioned templates and rejects any request carrying
HTML, CSS or script, so the repository's "model output is data" rule holds at
the service edge. It renders with **no network**: the browser, the two brand
typefaces and the animation runtime (a vendored GSAP) are all in the image.

## Layouts

`layout` is optional and defaults to `stats` (the studio's original label/value
list). The others are `flow` (connected nodes with drawn connectors and a
travelled arrow), `timeline`, `comparison`, `bars`, and the catalog block
`bar-chart-race`. An item may name an icon from `src/icons.json`, and the theme
is `accent` plus an optional `accent2` and `background`. The accent is mapped
onto the brand's ramp and a `background` stays the caller's only if it is a
valid hex; see [Brand](#brand).

The five names from `stats` to `bars` are hand-written builders
(`src/layouts/*.mjs`); `bar-chart-race` comes from the HyperFrames catalog. The
registry (`src/blocks/registry.mjs`) is the closed set a caller may name, and
`src/spec.mjs` validates against it, so a caller never names a file.

## Brand

`datasets/brand.json` is the only copy of the project's palette and typefaces.
The shell, every layout and the block adapter read it through `src/scene.mjs`,
which exposes colour **roles** (`ink`, `surface`, `accent`) rather than hex
values, so a layout asks for a role and never spells a colour. The image ships
the two OFL typefaces from `vendor/fonts/` and loads them with `@font-face`, so
the render stays offline. Both schemes — the brand's dark default and its light
scheme — are available to a caller through the `scheme` render option.

A caller's `accent` is mapped onto the scheme's ramp (nearest role, or the
scheme's default when it is not a colour), so an out-of-brand value is never
rendered as given and a legacy frozen spec still renders; a brand value is kept
as the brand spells it. `src/spec.mjs` rejects an unknown scheme by name.

The document is extracted from the site repository that owns the brand; see
[`../README.md`](../README.md) for the sync command. `agents/n8n/scripts/test_brand.py`
fails any surface that spells its own colour or typeface, and
`test/brand.test.mjs` asserts the composition uses the declared scheme throughout.

The build context is `agents/n8n`, not this directory: the image mirrors the
repository so `render/src/scene.mjs` can read `datasets/brand.json` by the same
relative path in the image as in a checkout. Build with
`docker build -f agents/n8n/render/Dockerfile agents/n8n`.

## Catalog blocks

A catalog block is a HyperFrames-designed, variable-declaring template. We do
not write its markup; we pass it values. Blocks are vendored into
`vendor/blocks/` at image-build time by `scripts/vendor-blocks.mjs`, run against
the HyperFrames version pinned in `package.json`, and **committed** — so the
image builds and renders offline, and a re-vendor is a reviewable diff rather
than a silent overwrite. `vendor/blocks/lock.json` records each block's upstream
hash. The vendoring step rewrites a block's GSAP CDN reference to the vendored
`vendor/gsap.min.js` and **hard-fails** on any other remote `src`/`href`; the
offline render is the gate.

`src/blocks/adapter.mjs` binds a spec to a block. It reads the block's declared
variables from `data-composition-variables`, maps spec fields onto them through a
per-block table, coerces each to its declared type (and clamps a declared range),
and drops anything the block does not declare so the block's own default applies.
It includes the block by `data-composition-src` and hands this mount's values on
the include element's `data-variable-values` — the block is referenced, never
pasted, and its markup is never rewritten.

Only **variable-declaring** blocks are adopted. A catalog *component* (markup +
CSS with hardcoded content and no declared variables) would have to have its
content substituted, which is the hand-written markup this path exists to avoid.

Adopted blocks are listed in `blocks.json`; a block is reachable by its own name
and, once a layout name is switched over to it, by that layout name.

### Adding a block

1. Add its name to `blocks.json` and run `node scripts/vendor-blocks.mjs`; commit
   the vendored file and the updated `lock.json`.
2. Add its spec mapping to `VARIABLE_MAPPINGS` in `src/blocks/adapter.mjs` (and a
   helper if the shape needs one), mapping only variables the block declares.
3. Add the name to `BLOCK_NAMES` (or point a layout name at it in
   `BLOCK_LAYOUTS`) in `src/blocks/registry.mjs`, and to `LAYOUTS` in
   `src/spec.mjs`.
4. Add an adapter unit test and a container render smoke asserting the produced
   MP4's duration and frame count.

The image contacts the registry **only** when vendoring, never at render time: a
block already committed in `vendor/blocks/` renders from disk.

## Development

```
npm install
PATH=<ffmpeg bin>:$PATH node src/server.mjs
node --test 'test/*.test.mjs'   # offline composition tests, no Chrome needed
```

The render itself needs FFmpeg, FFprobe and a browser; the image apt-installs
Debian's `chromium` and points HyperFrames at it with
`HYPERFRAMES_BROWSER_PATH`, so both architectures use one path and no browser is
downloaded at runtime.

The container smoke test is separate because it needs a live service. Build and
run the image from the repository root (the build context is `agents/n8n`), then
run it against the fixture:

```
docker build -f agents/n8n/render/Dockerfile -t datahub-local-ai-render:local agents/n8n
docker run -d --name render \
  --read-only --cap-drop ALL --security-opt no-new-privileges \
  --shm-size=1g --tmpfs /tmp \
  -p 18080:8080 datahub-local-ai-render:local
RENDER_URL=http://127.0.0.1:18080 RENDER_CONTAINER=render node test/smoke.mjs
docker rm -f render
```

The `docker run` flags mirror the core deployment's security context
(read-only root, capabilities dropped, `/tmp` an emptyDir): the image's `HOME`
is `/tmp` so Chrome can create its user data directory under that read-only
root. Running it here without those flags would hide that requirement.

It asserts the file's real duration and frame count (read back with the image's
own ffprobe) against literals kept in step with `test/fixture.json`; CI runs it
in `render-image`, gated on a change under `agents/n8n/render/`.

## What this service is not

It answers **one shape of demand**: a typed spec in, a deterministic video out. It
is the right thing for a scheduled workflow producing a repeatable asset type,
because the same spec always yields the same composition and a caller cannot inject
markup.

It is the **wrong** thing for a bespoke, one-off visual: "show how a team of AI
agents collaborates to build a project" has no layout and no catalog block. That is
a different path — an agent authors a whole HyperFrames composition from the brief,
with HyperFrames' own skills as the contract and this image's toolchain as the
engine. See `agents/render-samples/` and
`openspec/changes/add-agent-authored-compositions/`.

Do not reach for this service for the second case, and do not let it accept markup to
cover it.

## Where it is wired

- `agents/n8n/workflows/visual_studio.workflow.json` calls it for the video type.
- `datahub-local-core` deploys it in the `automation` namespace beside n8n and
  owns the NetworkPolicies. See `openspec/changes/add-hyperframes-render-service/`.
