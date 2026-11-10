# Proposal

## Why

The article lane keys every visual by registry type: one marker per type, one file per type, one
asset row per type. That makes the number of images a function of how many distinct ids the registry
declares, not of what the article needs. A walk-through with five steps that each deserve a diagram
cannot ask for five; a short post gets the same fixed set. The two roles are also conflated: the
hero (the lead image after the opening) and a section figure are different placements and different
briefs, but today both are just "a type".

Row 3 (2026-11-10) showed the consequence: with `svg_wide` alone the published article had one
image; with `image_wide,svg_wide` the second was a paid raster that the weekly OpenRouter cap could
block.

## What Changes

- **Section figures become positional slots, not types.** The writer may place
  `<!-- asset:figure -->` zero to four times, each directly after the section it illustrates. The
  marker carries no index; the parser numbers them in document order, so a slot cannot be skipped or
  duplicated.
- **The writer decides the count, the row caps it.** `article_queue.MAX_FIGURES` (blank reads as 3,
  total ceiling 5 with the hero) bounds what the draft may place. The rule is "a figure only where a
  diagram carries a step, a comparison or a flow the prose cannot", so a short article can get zero.
- **The approved draft is the asset plan.** In the assets and publish phases the requested set is
  derived from the stored draft — the declared hero plus `figure_1…figure_N` — instead of only from
  the sheet's `ASSET_TYPES`, which does not know the draft.
- **Figures are authored from their section.** A new registry type `figure` (author `agent`,
  static, svg, 16:9, form `diagram`) is requested once per slot, with the heading and text of that
  section as the brief, so each figure illustrates its own section in the hero's visual language.
- **Storage and review stay per asset.** Rows are `figure_1…figure_N`; each has its own Slack
  approval and the existing all-approved publish gate.
- **The commit maps by position.** The k-th figure marker becomes
  `/img/<slug>-figure-<k>.svg`, alt taken from that section's heading.
- **The hero stays composer-authored by default.** `svg_wide` remains the default hero; a row that
  explicitly declares `image`/`image_wide` still gets that raster.

## Capabilities

### Modified Capabilities

- `content-writer`: the approved draft, not the type list, decides how many figures an article
  carries; the requested set includes positional figure slots.
- `visual-studio`: a `figure` type is declared and authored from the section a slot sits in.

## Impact

- `agents/adapters/pi-writer/prompts/article_task.md` and `writing.md` — the hero/figure contract and
  the cap.
- `agents/n8n/workflows/article_creator.workflow.json` — `parse_article` counts figures and enforces
  the cap; `build_article_request` passes `MAX_FIGURES`.
- `agents/n8n/workflows/article_content_writer.workflow.json` — the asset plan in
  `select_article_to_queue` for the assets/publish phases; `split_pending_types` fans out slots;
  `split_assets`/`store_assets` keep `figure_<k>`; `build_commit_files` maps markers by position;
  the publish gate reads the draft-derived set.
- `agents/n8n/datasets/visual_types.json` — the `figure` type.
- `agents/n8n/datasets/board_intake.json` — `MAX_FIGURES` default and the composer-only asset set.
- `agents/n8n/prompts/article_review.md` side of the gate: the figure count is code's, not a
  judgement.

## Non-goals

- Removing `image`/`image_wide` from the registry. An explicit raster row keeps working.
- Parallel authoring of figures. Slots are authored in order, one studio run each.
- A layout or caption contract for figures beyond 80% width and the heading as alt text.
- Choosing the count by sheet column instead of by the writer; `MAX_FIGURES` caps, it does not
  command.
