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
node --test test/          # offline composition tests, no Chrome needed
```

The render itself needs FFmpeg, FFprobe and a Chrome headless shell; in the
image those are baked in (`hyperframes browser ensure` runs at build time).

## Where it is wired

- `agents/n8n/workflows/visual_studio.workflow.json` calls it for the video type.
- `datahub-local-core` deploys it in the `automation` namespace beside n8n and
  owns the NetworkPolicies. See `openspec/changes/add-hyperframes-render-service/`.
