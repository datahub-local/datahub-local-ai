# Proposal

## Why

An article's visuals are briefed and committed without a model of **where they sit**. Every
article asset is authored from the draft text and committed into the page, and nothing
states that the lead image is read at the top of the page while a section figure is read
inside a text column at 80% width — or that they must not say the same thing. The first
two-asset article (row 4, 2026-11-19) showed both consequences at once: the hero and the
figure came out near-identical (the section restated the article's thesis, so the two
visuals converged), and the commit chain collapsed two assets to one
(`asset_signed_url` read `$input.first()`), failing the commit with
"GitHub answered 1 blobs for 2 assets".

## What Changes

- **Each asset declares the placement it fills.** The article lane's asset plan carries
  `hero` or `figure_<k>` with the section it belongs to; the brief and the committed page
  use that placement.
- **A figure is its section's mechanics, never a second thesis.** The figure brief names
  the section and states that the page's lead image already carries the article's
  thesis — the figure shows the section's flow, step or comparison row.
- **The lead is the one moving asset; figures are still.** One animated lead per page,
  static figures inline, so the page never has two competing motions.
- **Every requested asset commits to its own path, in one commit.** The publish chain is
  per-item end to end: N assets in, N blobs, N committed files — the count assertion in
  the tree step stays and is what detects a regression.
- **A figure composes for inline reading**: wide and shallow (16:9), one idea, labels
  legible at the width it is rendered at, no dense code text.

## Capabilities

### Modified Capabilities

- `content-writer`: the asset plan carries each asset's placement and section; the
  committed page renders the lead full-width and each figure inline; the commit carries
  every requested asset.
- `visual-studio`: a type declares the frame it is authored at; the figure type's brief
  excludes the article's thesis and targets inline legibility.

## Impact

- `agents/n8n/workflows/article_content_writer.workflow.json` — `derive_asset_plan`
  (placement + section), the asset publish chain (per-item), `build_commit_files`
  (lead vs figure markup and paths).
- `agents/n8n/datasets/visual_types.json` — the `figure` type's frame and role.
- `agents/n8n/prompts/visual_motion_rules.md` — the stillness rule for still types
  (already true for `figure`; stated so it cannot regress).
- `docs/agent/n8n.md` — the article lane's asset section.

## Non-goals

- A new asset type or a new registry shape: `svg_wide` (lead) and `figure` (inline)
  already exist; this change states how they are placed, not what they are.
- User-chosen placement in the sheet: the writer's markers decide placement, the row
  decides the set.
- Layout beyond the two placements (no sidebars, no galleries).
