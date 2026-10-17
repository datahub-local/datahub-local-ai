# Proposal

## Why

Nothing in the pipeline **looks at** an authored visual. The composer authors a
composition, the framework's `lint`/`check` gate covers clipping and motion, the brief
carries craft rules — and the first reader of the finished artifact is a human in Slack.
The gate cannot see what a reader sees: on 2026-10-17 a live article asset reached review
(and was approved) with `04 / IDENTITY` printed **on top of** its own heading, three
strike-through rules crossing the glyphs they mark, and the right-hand column compressed
against its box edges. Every one of those is a defect the composer authored, `check`
passed, and only an eye caught.

The same is true of a raster: the Gemini image is handed to review unseen, so a
composition for the wrong frame, lettering that the raster prompt forbids, or a subject
that does not read as the brief asked for is caught by the reviewer or not at all.

Both halves have the pieces already: the session pod carries the artifact, Chromium
rasterises an SVG and `ffmpeg` samples a clip, and the gateway serves vision models — a
probe from inside the session pod on 2026-10-17 answered `"Red"` for a 2x2 red PNG from
both `opencode-go/deepseek-v4.1-flash` and `opencode-go/glm-5.3-flash`.

## What Changes

- **The authoring turn reviews its own render before answering.** After the engine
  renders, the adapter makes one still of the artifact (Chromium for an SVG or an HTML
  deck, `ffmpeg` frames for a clip, the file itself for a still PNG), asks a **different**
  vision model on the gateway to critique it against the brief's own contract, and — when
  the critic reports findings and budget remains — takes another authoring turn **in the
  same session** with those findings as the reviewer's correction, then re-renders and
  re-critiques. Bounded at two cycles by default.
- **The raster branch does the same in the studio.** A Gemini asset is critiqued from the
  bytes n8n already holds (a raster's bytes are made inside n8n; nothing is fetched back),
  and on findings the image prompt is rewritten with them appended and the image
  regenerated, bounded the same way.
- **The review prompts are committed files**, fetched from GitHub `main` by the studio and
  carried in the request body, so the grammar a critic applies is a prompt push rather
  than an image rebuild. One per medium: a composition is fixed by editing it, a raster by
  rewriting its prompt.
- **The findings are recorded on the asset** — cycles run, what the critic said, what was
  fixed — so the human approval names what the critic reported instead of arriving with a
  silent artifact.

## Capabilities

- `visual-studio` (modified): an authored asset is inspected and corrected before it is
  offered for review; the review budget is bounded; the review's outcome is part of the
  asset's record.

## Impact

- `agents/adapters/pi-render/`: `session-lib.mjs` (the still-sampling argument lists, the
  critic request, the cycle settings — all pure and testable), `session-server.mjs` (the
  loop after the render), `test/` (assertions that fail without them).
- `agents/n8n/prompts/`: two new committed prompts, one per medium.
- `agents/n8n/workflows/visual_studio.workflow.json`: the raster half of the loop, the
  review prompt fetch, and the report on the asset.
- A longer authoring turn: roughly the render plus one vision call plus another authoring
  turn per cycle. Both callers carry `executionTimeout: 3600`, so two cycles fit, but the
  studio's own bound is re-measured rather than assumed.

## Non-Goals

- **Replacing the human approval.** The loop removes a class of defect before review; the
  reviewer still decides.
- **Letting the composer see images while it authors.** The critique is a separate call
  after the render, so the authoring brief stays prose and the sandbox guide does not
  regain a method section.
- **A critic for the LinkedIn-only types as a separate path.** Every type is covered by one
  of the two halves; the platform frames differ only in their declared `aspect`.
