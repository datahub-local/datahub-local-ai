# Design

## Context

The media decision runs: judge returns `visual: {form, motion, scenes}` → `parse_judge`
carries it onto the finalist as `visual_form` / `visual_motion` / `visual_scenes` →
`admit_to_backlog` writes `VISUAL_FORM`, `POST_MEDIA` (`ANIMATED`/`STATIC`) and `SCENES`
→ `linked_in_post_sharing`'s `switch_post_media` routes `ANIMATED`/`AGENT` to the
studio and anything else to the image creator.

`hook_types.json` declared `motion: true` on all nineteen hooks and the judge prompt
instructed the model to use the hook's default "unless the article warrants otherwise",
so a still was always available and the example output showed `false`.

## Gate findings

- The failure fallback already exists and is asserted:
  `test_a_failed_animation_falls_back_to_the_image_and_says_so` walks
  `if_animation_ok` output 1 → `notify_animation_fallback` → `execute_image_creator`.
  No graph change is needed to make static the fallback.
- `POST_MEDIA` is read by `switch_post_media` in `linked_in_post_sharing` only; nothing
  else consumes `visual_motion`. Removing the field is therefore local to the curator.
- The judge's `{{ HOOKS }}` block carries only `id` and `when` per hook
  (`parse_hook_registry`), so removing `motion` from the registry does not change what
  the model is shown beyond the removed field instruction.

## Decisions

- **Enforce in code, not prose.** `admit_to_backlog` writes `POST_MEDIA: 'ANIMATED'`
  and `parse_judge_backfill` writes the same; a model that still emits a motion flag
  cannot flip a row to static. This is the "put deterministic logic in code" rule — a
  prompt instruction would leave the outcome to the model.
- **Drop the field rather than pin it.** With the media always animated, `visual_motion`
  and the registry's `motion` are dead data; leaving them is a second copy of a
  decision that drifts. Removed from the registry, the judge contract and the parse
  nodes.
- **Keep `POST_MEDIA` as a column.** It is the manual override and the value the
  fallback path is expressed against; the media switch still reads it.

## Risks

- A reviewer wanting a still for one article can no longer get it from the judge; they
  edit the row's `POST_MEDIA` cell, which is the documented override.
- The judge prompt still names `image` as a possible `form`. That is the authoring
  form, not the media kind: the LinkedIn branch always requests the
  `animation_linkedin_video` type, so a `form: image` is rendered as a video by the
  composer. No hook defaults to `form: image`, so this is only reachable by an explicit
  judge override.

## Open questions

- None.

## Definition of done

- `parse_judge`, `parse_judge_backfill` and `admit_to_backlog` carry no motion flag and
  write `ANIMATED`; both export copies agree.
- `hook_types.json` and `curator_judge.md` carry no motion flag.
- `test_every_admitted_row_is_animated` fails against the pre-change export.
- `pytest agents/n8n/scripts/` and `ruff check` pass.
- Applied live, re-read and diffed against the export.
