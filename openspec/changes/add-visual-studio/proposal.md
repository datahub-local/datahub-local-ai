# Proposal

## Why

The article pipeline being planned in `add-content-writer-agent` produces exactly one visual per article: a static hero image. But an article's value often lives in one idea that reads best as an infographic, and a still cannot show a flow, a before/after, or a sequence. The pieces to do better are already in the n8n environment — a headless Chromium, GraphicsMagick with GIF and WebP delegates, and a Puppeteer node that can run custom scripts — so a single parameterized visual workflow can produce a *set* of assets, static and animated, from the same content, instead of one image. This change adds that workflow and reuses the article pipeline's review and publish.

## What Changes

- Add a new **Visual Studio** sub-workflow: one workflow, parameterized by an **artifact-type registry**, that produces multiple visual assets for one article.
- Define v1 artifact types:
  - `hero_static` — static raster hero (PNG/JPG), placed as the article's first image (the image platforms preview, since the blog emits no `og:image`).
  - `infographic_static` — static raster infographic (PNG), the existing image-model mode.
  - `diagram_animated` — animated **WebP** (GIF fallback) rendered from HTML/CSS.
  - `animated_svg` — a self-contained animated SVG committed as text.
  - `motion_clip` (WebM/MP4) — **declared but not producible in v1**: n8n has no `ffmpeg`, so a requested `motion_clip` is reported unavailable rather than silently skipped.
- Author every infographic in **two stages**: the model emits a typed **content spec** (JSON: title, blocks, labels, values, accent, motion, duration) and deterministic code turns that spec into HTML/CSS or SVG. The model never writes the markup.
- Render animation deterministically: a browser renders the markup, a Puppeteer **custom script** seeks the timeline (`document.getAnimations()` / `Animation.currentTime`) and captures frames, and GraphicsMagick assembles them into an animated image.
- Add a child **`article_assets`** page to `content_planner` (one row per artifact: type, state, feedback, prompt/spec, path, format) so each asset is reviewed and retried on its own; `add-content-writer-agent`'s singular `IMAGE_*` columns no longer suffice for a set.
- Review each asset in Slack as the existing flows do (double approval, retry-with-feedback), reusing the article pipeline's publish step so an approved set is committed with the article in one commit.
- **No Sympozium, no MCP server, no cluster change, and no `ffmpeg`.** Everything is n8n, the existing browserless Chromium, GraphicsMagick, the LiteLLM image models, Google Sheets and the GitHub API.

## Capabilities

### New Capabilities
- `visual-studio`: a parameterized n8n workflow that turns one article's content into a set of static and animated visual assets via a declared type registry, with two-stage authoring, browser-rendered animation, per-asset Slack review, and commit to the blog repository.

### Modified Capabilities
<!-- None. openspec/specs/ is empty; add-content-writer-agent's content-writer capability is not yet archived, so this change is additive and shares the pipeline without changing that capability's requirements. -->

## Impact

- **`agents/n8n/workflows/`**: new Visual Studio sub-workflow and its error path; the animated renderer branch is the first use of Puppeteer `runCustomScript` and GraphicsMagick assembly in this repo. Applied live with `scripts/apply_workflow_changes.py`, never assumed from the export.
- **`agents/n8n/prompts/`** and **`agents/n8n/datasets/`**: per-type prompt templates and a type registry file, fetched through `DownloadTemplate` like `datasets/image_motifs.json`; they follow the repo's AI prompt policy (short, literal, no copied data).
- **`content_planner` sheet**: new `article_assets` child page; the article pipeline's review and publish must read it.
- **`add-content-writer-agent`** (this repository, related change): the Visual Studio workflow is meant to be called by that article pipeline; the two changes meet at the asset set, so they should land together or the studio first.
- **`alvsanand`** (cross-repo): assets commit to `docs/img/` and are referenced from the post; the static hero remains the article's first static image (the blog emits no `og:image`, so platforms preview page images), never an animated asset.
- **No change** to `datahub-local-core`, `datahub-local-ai-mcp`, or Sympozium. True video stays out of scope until `ffmpeg` is deliberately added.
