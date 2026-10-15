# Proposal

## Why

A request for a type the registry cannot resolve returns **no assets at all**, so the
caller cannot see the failure. `parse_registry` gives such a type `AUTHOR: null` — an id
the registry does not declare (`STATUS: UNKNOWN`) or one marked `available: false`
(`STATUS: UNAVAILABLE`) — which routes it to `if_agent[1]` → `if_raster[1]` → `ready_pass`
→ `merge_branches` **input 2**.

That edge names an input the target does not have: `ready_pass` is a one-input `noOp`.
n8n pads the inputs a node was not given with `[]`, so the node executes, reads input 0,
finds nothing and emits nothing. `merge_branches` input 2 therefore never fires,
`set_result` never runs and the sub-workflow answers with zero items.

The consequence is silence rather than a report, verified on 2026-10-15:
`execute_visual_studio` in `LinkedIn Post Sharing` emitted 0 items, so
`check_animation_result` never ran, the graph stopped there and the run reported
`success` — 12 nodes, no fallback notice, no error, the row left `IN_PROGRESS`
(executions 13456 and 13464). The guard written for exactly this case would have
answered `ASSET_STATUS: MISSING` / `ERROR: animated media unavailable: no asset
returned` and driven the still-image fallback; an empty result is not a result.

Production never met it because the LinkedIn branch always asks for
`animation_linkedin_video`, which the registry declares and marks available. But
`available: false` is the registry's mechanism for withdrawing a type, and withdrawing
one today would stop every animated post after the text approval instead of falling
back to a still.

## What Changes

- The `if_raster` output-1 edge SHALL target `ready_pass` input `0`, in both copies of
  `agents/n8n/workflows/visual_studio.workflow.json`, so the unresolvable-type branch
  reaches `set_result` and the caller sees the reason.
- `agents/n8n/scripts/test_workflow_invariants.py` SHALL assert that no `main` edge
  targets an input index above 0 on a node type that does not take more than one input,
  which is what let this pass review.
- The fix SHALL be applied live with `scripts/apply_workflow_changes.py`, guarded by
  `--require-edge`, and the live graph re-read and diffed against the export.

## Capabilities

### Modified Capabilities

- `visual-studio`: a type the registry cannot resolve is reported with a reason, and a
  run whose every requested type is unresolvable still answers with those assets.

## Impact

- **`agents/n8n/workflows/visual_studio.workflow.json`**: one connection index, both
  copies (top level and `activeVersion`).
- **`agents/n8n/scripts/test_workflow_invariants.py`**: one added test.
- **`agents/n8n/scripts/apply_workflow_changes.py`**: `summarize_main` names a target's
  input index when it is not 0. An index-only change is the shape this fix takes, and
  without the index the plan for it read as an already-applied no-op.
- No change to `visual_types.json`, to `parse_registry`, to `LinkedIn Post Sharing`, or
  to any node's parameters: the reported reason was always produced, it just never left
  the sub-workflow.

## Non-goals

- Changing what the caller does with a failed asset. `check_animation_result` and the
  fallback branch are already written for it and are untouched.
- The `UNKNOWN`/`UNAVAILABLE` distinction. Both are reported as an asset with a reason;
  whether the two deserve different handling is not decided here.
