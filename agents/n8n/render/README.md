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
the service edge. It renders with **no network**: the browser, the fonts and the
animation runtime (a vendored GSAP) are all in the image.

## Layouts

`layout` is optional and defaults to `stats` (the studio's original label/value
list). The others are `flow` (connected nodes with drawn connectors and a
travelled arrow), `timeline`, `comparison` and `bars`. An item may name an icon
from `src/icons.json`, and the theme is `accent` plus an optional `accent2` and
`background` — all validated hex.

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
run the image, then run it against the fixture:

```
docker build -t datahub-local-ai-render:local .
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

## Where it is wired

- `agents/n8n/workflows/visual_studio.workflow.json` calls it for the video type.
- `datahub-local-core` deploys it in the `automation` namespace beside n8n and
  owns the NetworkPolicies. See `openspec/changes/add-hyperframes-render-service/`.
