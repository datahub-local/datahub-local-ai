# Proposal

## Why

A "motion design" look — a generative pattern field, in the shape of a Truchet/Smith
arc tiling: a square grid of tiles each carrying two quarter-circle arcs, rotated among
four orientations by a seeded walk, so the strokes join into S-curves and circles, under
a technical HUD frame naming the pattern, its tile count and its seed — is expressible
today only as `EXTRA_PROMPT`. That is the one channel the composer takes verbatim, and
the automated lane does not carry it: `linked_in_post_sharing`'s `execute_visual_studio`
sends exactly `CONTENT`, `ASSET_TYPES`, `FEEDBACK`, `FORCE`, `SCENES` and `SESSION_ID`
(read from the export), and `Visual Studio Test` carries no `EXTRA_PROMPT` node at all.
The row's own `EXTRA_PROMPT` reaches the post generator (`execute_post_creator`), not
the studio. So on the only lane that publishes unattended, a generative-pattern visual
cannot be asked for — not per row, and not at all.

The form vocabulary has no entry that means "generate the field", either: its twelve
forms are `diagram`, `story`, `data`, `chart`, `code`, `timeline`, `quote`, `poster`,
`ui`, `manga`, `retro` and `launch`, and nothing in that list asks for a tiled or
parametric pattern. `retro` is the nearest, and it means a 16-bit console screen.

## What Changes

- Add one form to the single committed vocabulary, `prompts/visual_forms.md`: `tiles`,
  which asks the composer to fill the field — a regular grid of tiles each carrying an
  arc or corner motif completed by a seeded walk, under a technical HUD frame naming the
  pattern and its seed.
- Add `'tiles'` to the **three** copies of that vocabulary in the graph — the studio's
  `normalize_input` (`const FORCES`) and the curator's `parse_judge` and
  `parse_judge_backfill` (`const FORMS`) — because an unknown `FORCE` is rejected loudly
  and the curator may not write a value the studio will refuse.
- Add two types to the registry, `tiles` (4:5, mp4, the feed's frame) and `tiles_wide`
  (16:9), each pinning `form: tiles`, so the look is also reachable as an asset type.
- Correct the `visual-studio` spec's type list, which still omits `image_wide` and
  `svg_wide` — a documentation drift left by the change that added the wide pair — and
  add the requirement the registry already implements and the spec never stated: a type
  may pin the form it means.
- Extend the registry test: the exact-ordered id list, and a case that both tiling types
  declare a known form, a positive duration, `frames == duration × fps`, no per-scene
  floor and no frozen hold.

## Capabilities

### New Capabilities

<!-- None. -->

### Modified Capabilities

- `visual-studio`: the type registry gains the tiling pair; the trigger contract's
  `FORCE` enum gains `tiles`; and the specification states, for the first time, that a
  type may pin the form it means (behaviour the registry already carries for `svg_wide`).

## Impact

- **`agents/n8n/prompts/visual_forms.md`**: one added line. Read from GitHub `main` by the
  studio (into the brief) and by the curator (into the judge prompt as `{{ FORMS }}`), so
  the definition is live on push.
- **`agents/n8n/workflows/visual_studio.workflow.json`** and
  **`agents/n8n/workflows/content_feed_curator.workflow.json`**: one array literal each
  (the curator's in two code nodes). Per the repo rule these exports are the backup's
  output, so the change is live only once applied with
  `scripts/apply_workflow_changes.py` — staged first, read back, and diffed afterwards.
- **`agents/n8n/datasets/visual_types.json`**: two entries. A registry change only; no
  node, and no rendering branch, is added.
- **`agents/n8n/scripts/test_visual_studio_registry.py`**: the exact id list and one new
  case. `test_hook_registry.py` and `test_visual_studio_graph.py` already assert the
  three vocabulary copies agree, so they cover the graph half of this change as soon as
  the arrays are edited.
- **Not changed**: `linked_in_post_sharing`'s `ASSET_TYPES` and
  `check_animation_result` (the feed keeps `animation_linkedin_video` and takes the look
  from the row's `VISUAL_FORM`), the composer image, the brand, the hook registry, the
  motion rules, and `datahub-local-core`. No OpenDesign or `html-video` dependency: their
  motion-template gallery is a discovery surface, and this change adds no third-party
  asset.
