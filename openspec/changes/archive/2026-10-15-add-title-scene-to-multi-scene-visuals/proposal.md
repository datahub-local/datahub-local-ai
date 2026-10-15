# Proposal

## Why

A declared scene plan renders as N items and nothing introduces them, so a
multi-scene clip opens cold on the first item: the viewer meets a detail before
the subject. The composer plans its own storyboard and the brief carries no cue
that a sequence wants a title.

## What Changes

- `build_author_brief` in `visual_studio.workflow.json` asks for an opening title
  scene naming the subject whenever the request declares a scene count greater than
  one; the clip then carries the declared count plus the title.
- A declared count of one and a blank count are unchanged.

## Capabilities

### Modified Capabilities

- `visual-studio`: a declared scene count greater than one SHALL add an opening
  title scene to the brief.

## Impact

- **`agents/n8n/workflows/visual_studio.workflow.json`**: `build_author_brief`
  (both copies). Applied live with `scripts/apply_workflow_changes.py`, guarded by
  `--require-edge` and re-read afterwards. The apply also reconciled `parse_registry`
  and the rest of `build_author_brief`, which the live instance lacked from commit
  `88537ba` (the per-scene duration floor); live now equals the export.
- **`agents/n8n/scripts/test_visual_studio_graph.py`**: a test for the title line.
- No dataset, prompt, type registry, sheet or other workflow changes.
