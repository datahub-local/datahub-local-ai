# Proposal

## Why

Every visual this repository generates — infographics, diagrams, animated
GIF/WebP, animated SVG, video, and the raster hero images — invents its own
palette, type and composition. `image_motifs.json` and `diagram_visual_styles.json`
each carry their own colour vocabulary; the render service's shell and layouts
hard-code a near-black theme; the prompts ask a model to pick "an accent" with no
brand behind it. Nothing ties the output to the site the work is published on
(`https://datahub-local.alvsanand.com/`), whose design is an explicit, named
brand: the **MOSS** palette, Space Grotesk + JetBrains Mono, flat cards with thin
moss borders and no shadows.

So the same project reads as several different products depending on which flow
rendered the asset, and the gap widens with every new type. The site already
encodes the brand in one place (`datahub-local/datahub-local`: `mkdocs.yml` and
`stylesheets/extra.css`); this change makes every generation flow in this repo
derive from a single committed copy of those tokens.

## What Changes

- **Add one vendored brand token source.** A committed `brand.json` under
  `agents/n8n/datasets/` carries the MOSS palette, the two typefaces, the
  radii/border/alpha idioms, and the dark and light schemes, extracted from the
  site repo. A documented, repeatable extraction step regenerates it, so a
  re-sync is a reviewable diff rather than a silent drift. It is the only copy of
  the brand in this repo.
- **Every px-generating surface reads those tokens.** The render service's shell
  (`scene.mjs`), its hand-written layouts and its catalog-block accent defaults;
  the `infographic.html` and `infographic.svg` templates; and the
  `visual_types.json` type defaults.
- **Every prompt that describes a look states the brand.** `visual_spec.md`,
  `visual_raster.md`, `linkedin_image_prompt.md`, and `diagram_generator.md` stop
  leaving colour and type to the model and instead describe the MOSS palette and
  the two typefaces, sourced from `brand.json`.
- **The raster/diagram art-direction datasets are reconciled with it.**
  `image_motifs.json`, `diagram_color_presets.json` and
  `diagram_visual_styles.json` stop offering palettes that contradict the brand;
  a model choosing among them still lands inside the brand.
- **Two aesthetics, chosen by kind, not by surface.** Diagrams, infographics,
  cards and spec-driven animation follow the flat moss UI language. Hero and
  cover imagery follows the site's photographic art direction (dark studio, matte
  subjects, moss light). The choice is a property of the asset kind.
- **The agent-authored path carries the same brand.** The `pi-render` brief
  includes the brand tokens so an authored composition matches the deterministic
  one, rather than being the one flow that ignores it.

## Capabilities

### New Capabilities

- `visual-brand`: one committed source of brand tokens (palette, typography,
  layout idioms, two schemes) extracted from the site repository, which every
  visual-generation flow consumes, and the rule that a generated visual matches
  the brand for its kind.

### Modified Capabilities

- `visual-studio`: rendered assets are required to follow the brand for their
  kind — deterministic markup always, raster prompts by art-direction text.
- `agent-authored-compositions`: an authored composition is required to follow
  the same brand tokens as the deterministic path.

## Impact

- New: `agents/n8n/datasets/brand.json`, its extraction script/doc, and a
  brand-idempotency test.
- `agents/n8n/render/`: `src/scene.mjs` (shell), `src/layouts/*.mjs`,
  `src/blocks/adapter.mjs` (accent default), and the render test suite.
- `agents/n8n/templates/infographic.html`, `infographic.svg`.
- `agents/n8n/prompts/`: `visual_spec.md`, `visual_raster.md`,
  `linkedin_image_prompt.md`, `diagram_generator.md`.
- `agents/n8n/datasets/`: `image_motifs.json`, `diagram_color_presets.json`,
  `diagram_visual_styles.json`, and `visual_types.json` defaults.
- `agents/n8n/workflows/visual_studio.workflow.json` (the `pi-render` brief) and
  `agents/adapters/pi-render/`.
- Cross-repo: the canonical tokens live in `datahub-local/datahub-local`
  (`mkdocs.yml`, `stylesheets/extra.css`). This change reads them; it does not
  modify that repository.

## Non-goals

- **No logo, wordmark or icon baked into generated assets.** The brand reaches
  through palette and typography only, so an asset stays reusable and cannot be
  mis-cropped (user decision).
- **No change to the site or its CSS.** The site is the reference; this repo
  consumes a copy of its tokens.
- **No new asset types and no change to the HTTP/parameter contract.** The
  registry's ids, the render service's request shape and the workflow's triggers
  are unchanged.
- **Not pixel-matching a site page.** Generated visuals share the brand's
  vocabulary, not a page's DOM.
- **Not Superset dashboards or dbt/semantic charts.** Those are a data-viz
  tooling concern with their own theme; "visual generation" here means assets the
  workflows and agents produce.
- **No per-asset restyle of vendored catalog blocks** beyond their declared
  colour variables — that stays the `migrate-render-layouts-to-catalog-blocks`
  decision (light touch, upstream divergence kept minimal).
