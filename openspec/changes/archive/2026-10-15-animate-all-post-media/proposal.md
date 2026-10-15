# Proposal

## Why

Every hook already declares `motion: true`, so animation was already the intent, but
the judge could still return `motion: false` per article and the curator turned that
into `POST_MEDIA=STATIC`. The judge prompt's own output example showed
`"motion": false`, which biased the model toward the still path. The result was that a
still image was a *classification outcome*, not a fallback — and the still path is the
weaker deliverable for this author.

## What Changes

- The curator SHALL write `POST_MEDIA=ANIMATED` for every row it admits and for every
  row it backfills; the media is no longer a per-article decision.
- `motion` is removed from the judge's `visual` contract and from
  `datasets/hook_types.json` (it is now dead data — nothing reads it).
- A still image becomes solely the fallback when the visual author fails: the existing
  `if_animation_ok` → `notify_animation_fallback` → image-creator branch in
  `linked_in_post_sharing.workflow.json` is unchanged.
- A manually declared `POST_MEDIA` value on a row still overrides, so the still path
  stays reachable by hand and the failure fallback is not the only way to a still.

## Capabilities

### Modified Capabilities

- `post-hook-taxonomy`: a hook's declared visual intent carries a form and a scene
  count, and SHALL NOT carry a motion flag.
- `linkedin-post-publishing`: an admitted row's media SHALL be animated; the still
  image is the fallback when the animated asset cannot be produced.

## Impact

- **`agents/n8n/datasets/hook_types.json`**: `motion` removed from every hook's
  `visual` and from `_comment_visual`.
- **`agents/n8n/prompts/curator_judge.md`**: the `visual.motion` field and the
  `"motion": false` output example removed.
- **`agents/n8n/workflows/content_feed_curator.workflow.json`**: `parse_judge`,
  `parse_judge_backfill` and `admit_to_backlog` (both copies) force `ANIMATED`.
  Applied live with `scripts/apply_workflow_changes.py`, guarded by `--require-edge`.
- **`agents/n8n/scripts/test_hook_registry.py`**: the motion assertions replaced by
  one test that every admitted row is animated.
- No change to `linked_in_post_sharing.workflow.json`, `visual_types.json`, the sheet
  columns, or any other workflow. The static fallback already exists.

## Non-goals

- Removing the still-image path. It stays as the failure fallback and the manual
  override.
- Changing which animated type the LinkedIn branch requests
  (`animation_linkedin_video`).
