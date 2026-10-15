# Tasks

## 1. Fix the graph

- [x] 1.1 Point `if_raster` output 1 at `ready_pass` input `0` in both copies of `agents/n8n/workflows/visual_studio.workflow.json` (top level and `activeVersion`)

## 2. Test

- [x] 2.1 Add `test_no_edge_targets_an_input_the_node_does_not_have` to `agents/n8n/scripts/test_workflow_invariants.py`, asserting a `main` edge onto input index > 0 targets a multi-input node type; verified it fails against the pre-change export with `if_raster -> ready_pass (n8n-nodes-base.noOp) index=2`
- [x] 2.2 `uv run -- pytest agents/n8n/scripts/ -q` (366 passed) and `ruff check` pass
- [x] 2.3 `summarize_main` in `agents/n8n/scripts/apply_workflow_changes.py` prints a target's input index when it is not 0, pinned by `test_an_index_only_connection_change_shows_in_the_plan`: the plan clipped the index, so this fix's dry run read as an already-applied no-op

## 3. Apply

- [x] 3.1 Applied live 2026-10-15 with `scripts/apply_workflow_changes.py --changes --require-edge` (`if_raster>ready_pass`, `if_agent>if_raster`): live `if_raster` output 1 now targets `ready_pass` index 0, in the draft and in `activeVersion`; re-read and diffed — 29 nodes, parameters, settings and `activeVersion` equal to the export, `active: True`. The only remaining live-vs-export delta is two empty `"main": []` arrays the export carries on `ai_model` and `ai_model_fallback` and live omits, which no part of this change touches (the export is a backup, so the next run regenerates it)

## 4. Docs

- [x] 4.1 Recorded in `AGENTS.md`'s `test_workflow_invariants.py` paragraph: the new check, the `if_raster` bite, and why an edge onto an input a node does not have is silent — n8n pads the missing inputs with `[]`, so the node runs, reads input 0 and emits nothing, taking its whole chain with it. The requirement the branch is supposed to satisfy is stated in the `visual-studio` spec delta

## 5. Acceptance

- [ ] 5.1 [UNVERIFIED] Re-run the forced-failure probe (`ASSET_TYPES=bogus` on `LinkedIn Post Sharing`'s `execute_visual_studio`) and confirm the studio now answers with one `UNKNOWN` asset and the run falls back to the image path; this is also `animate-all-post-media`'s task 5.3
