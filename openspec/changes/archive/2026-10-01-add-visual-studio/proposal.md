# Proposal

## Why

An article's value often lives in one idea that reads best as a visual — an infographic, a flow, a before/after — and a still cannot show that. The pieces to do better are already in the n8n environment — a headless Chromium, GraphicsMagick with GIF and WebP delegates, and a Puppeteer node that can run custom scripts — so a single parameterized visual workflow can produce a *set* of assets, static and animated, from one source text. This change adds that workflow as a **generic, reusable service**: any caller — the article pipeline planned in `add-content-writer-agent`, an HTTP client, or a human filling in a form — supplies parameters and receives visual assets.

## What Changes

- Add a **Visual Studio** workflow: generic and stateless between runs, with one parameter contract on **three trigger surfaces** — a sub-workflow call (`executeWorkflowTrigger`), an HTTP API (`POST /webhook/visual-studio`) and an n8n form — taking `CONTENT` (required), `ASSET_TYPES`, `FEEDBACK` and an optional frozen `SPEC_JSON`.
- Define v1 artifact types in a **registry**:
  - `hero_static` — static raster hero (PNG/JPG).
  - `infographic_static` — static raster infographic (PNG), the existing image-model mode.
  - `diagram_animated` — animated **WebP** (GIF fallback) rendered from HTML/CSS.
  - `animated_svg` — a self-contained animated SVG returned as text.
  - `motion_clip` (WebM/MP4) — **declared but not producible in v1**: n8n has no `ffmpeg`, so a requested `motion_clip` is reported unavailable rather than silently skipped.
- Author every infographic in **two stages**: the model emits a typed **content spec** (JSON: title, blocks, labels, values, accent, motion, duration) and deterministic code turns that spec into HTML/CSS or SVG. The model never writes the markup.
- Render animation deterministically: a browser renders the markup, a Puppeteer **custom script** seeks the timeline (`document.getAnimations()` / `Animation.currentTime`) and captures frames, and libwebp's **`img2webp`** assembles them into an animated WebP (GraphicsMagick GIF as the fallback).
- Record **one run row per execution** in a `visual_studio_table` DataTable (`RUN_ID` = execution id, request and full result as JSON), so any run's outcome — content included — can be fetched over HTTP after the fact; the synchronous response carries the same asset set.
- Keep the workflow **content-only**: it returns assets with their content and format and never a path, a filename, a Slack message or a commit. Review gates, per-asset review state, retry-with-feedback and the single multi-asset commit belong to the caller (`add-content-writer-agent`), which re-renders a rejected variant by passing the frozen spec back as `SPEC_JSON`.
- **No Sympozium, no MCP server, and no `ffmpeg`.** Everything is n8n, the existing browserless Chromium, libwebp/GraphicsMagick for frame assembly, the LiteLLM image models and one DataTable. Two `datahub-local-core` prerequisites are already landed: `NODES_EXCLUDE=[]` (enable `ExecuteCommand`) and `custom.extra_modules: webp-converter` (`img2webp`).

## Capabilities

### New Capabilities
- `visual-studio`: a parameterized, trigger-agnostic n8n workflow that turns one source text into a set of static and animated visual assets via a declared type registry, with two-stage authoring, browser-rendered animation, a run record for later HTTP retrieval, and content-only results.

### Modified Capabilities
<!-- None. openspec/specs/ is empty; add-content-writer-agent's content-writer capability is not yet archived, so this change is additive and shares the pipeline without changing that capability's requirements. -->

## Impact

- **`agents/n8n/workflows/visual_studio.workflow.json`**: the Visual Studio workflow; the animated renderer branch is the first use of Puppeteer `runCustomScript` and `img2webp` assembly in this repo. Created live with `scripts/apply_workflow_changes.py --create` (D10), never assumed from the export.
- **`agents/n8n/scripts/setup_data_tables.py`**: provisions `visual_studio_table` (idempotent by name) — a documented setup step, like the DataTables in `add-content-writer-agent`.
- **`agents/n8n/prompts/`** and **`agents/n8n/datasets/`**: per-type prompt templates and the type registry file, fetched through `DownloadTemplate` like `datasets/image_motifs.json`; they follow the repo's AI prompt policy (short, literal, no copied data). New files must be committed and pushed — `DownloadTemplate` reads GitHub `main`.
- **`add-content-writer-agent`** (this repository, related change): the article pipeline is one caller. It passes the article text as `CONTENT`, requests `hero_static` first in `ASSET_TYPES`, re-presents a rejected variant by passing the frozen spec back, and owns every Slack gate, the per-asset review state and the single multi-asset commit.
- **`datahub-local-core`** (cross-repo): two prerequisites, both landed — `NODES_EXCLUDE=[]` to re-enable the `ExecuteCommand` node n8n v2 disables by default, and `custom.extra_modules: webp-converter` so the libwebp CLIs (`img2webp`) are installed at boot. No MCP server or Sympozium change. True video stays out of scope until `ffmpeg` is deliberately added.
