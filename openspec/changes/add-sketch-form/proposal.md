# Proposal

## Why

The visual vocabulary has a clean `diagram` — labelled nodes, boxes and arrows laid out so the
path reads at a glance — and nothing that means the other drawing register: ink on paper, wobbly
strokes, a diagram that looks **sketched** and draws itself on. Excalidraw is the reference a reader
recognises, and both lanes currently cannot ask for it. `FORCE` and `VISUAL_FORM` are enums that
refuse an unknown value loudly, and neither carries `sketch`; the registry has no type that pins it,
so even a caller that names it by hand is rejected before the brief is built. `EXTRA_PROMPT` is the
one free channel, and the automated article lane does not send it.

The look is also not free-handed prose: a sketched stroke has to be *constructed* — a seeded
imperfection on an authored path — and that is a definition the composer can follow repeatedly,
which is what a form is.

## What Changes

- Add one form to the single committed vocabulary, `prompts/visual_forms.md`: `sketch`, a labelled
  diagram on a wobbly ink stroke, the wobble from a seeded index-derived offset, the strokes drawing
  themselves on in reading order, no shading and no photographic fill.
- Add `'sketch'` to the **three** copies of that vocabulary in the graph — the studio's
  `normalize_input` (`const FORCES`) and the curator's `parse_judge` and `parse_judge_backfill`
  (`const FORMS`).
- Add two types to the registry, both pinning `form: sketch` and both at 16:9:
  - `sketch` — authored by the composer, `mp4`, 12 s at 30 fps / 360 frames / viewport 1280, for a
    feed or a player that takes a clip;
  - `sketch_svg` — authored by the composer, a self-contained animated `svg`, for an article body
    where the drawing must stay sharp at any width and cost a few kilobytes instead of megabytes.
- State in the `visual-studio` capability that the registry declares both, and that a sketch is one
  drawing rather than a sequence, so its type declares no per-scene floor and no intro scene.
- Update the Visual Studio section of `docs/agent/n8n.md`: the type list, the `FORCE` enum and the
  one non-obvious fact this change leans on — the wobble has no library behind it.

## Capabilities

### New Capabilities

<!-- None. -->

### Modified Capabilities

- `visual-studio`: the type registry gains the sketch pair; the trigger contract's `FORCE` enum
  gains `sketch`; the registry requirement states that a sketch animates one drawing and therefore
  carries no scene floor and no intro scene.

## Impact

- **`agents/n8n/prompts/visual_forms.md`**: one added line, live on push (the studio fetches it from
  GitHub `main` into the brief; the curator into the judge prompt as `{{ FORMS }}`).
- **`agents/n8n/workflows/visual_studio.workflow.json`** (2 graph copies) and
  **`agents/n8n/workflows/content_feed_curator.workflow.json`** (2 nodes x 2 copies): one array
  literal each. The exports are the backup's output, so the change is live only after
  `scripts/apply_workflow_changes.py` — and only after the owner says so.
- **`agents/n8n/datasets/visual_types.json`**: two entries. No node, no rendering branch.
- **`docs/agent/n8n.md`**: the Visual Studio section.
- **Not changed**: the composer image, `vendor/`, the `package.json` dependencies, `brand.json`, the
  motion rules, the hook registry, the feed lane's `ASSET_TYPES`, and `datahub-local-core`. No
  `rough.js`, no `Excalifont`, no `DrawSVGPlugin`, no new typeface and no new palette — the sketch is
  the brand's palette and typeface with roughened strokes.
