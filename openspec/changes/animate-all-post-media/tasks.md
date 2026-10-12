# Tasks

## 1. Registry and prompt

- [x] 1.1 Remove `motion` from every hook's `visual` in `agents/n8n/datasets/hook_types.json` and update `_comment_visual`
- [x] 1.2 Remove the `visual.motion` field and the `"motion": false` output example from `agents/n8n/prompts/curator_judge.md`

## 2. Curator graph

- [x] 2.1 `parse_judge` (both copies): drop `visual_motion` and the motion read; keep `visual_form`/`visual_scenes`
- [x] 2.2 `parse_judge_backfill` (both copies): drop the motion read; write `POST_MEDIA: 'ANIMATED'`
- [x] 2.3 `admit_to_backlog` (both copies): write `POST_MEDIA: 'ANIMATED'` unconditionally

## 3. Test

- [x] 3.1 Replace the registry motion assertions in `agents/n8n/scripts/test_hook_registry.py` with `test_every_admitted_row_is_animated`, asserting the curator, the registry and the judge prompt carry no motion flag and that `ANIMATED` is written unconditionally (fails against the pre-change export)
- [x] 3.2 `uv run -- pytest agents/n8n/scripts/ -q` and `ruff check agents/n8n/scripts/test_hook_registry.py` pass

## 4. Apply

- [x] 4.1 Apply `parse_judge`, `parse_judge_backfill` and `admit_to_backlog` live with `scripts/apply_workflow_changes.py --require-edge`, re-read and diff the export against live (applied 2026-10-12; live now equals the export on all 49 nodes, connections and settings, `active: True`)

## 5. Acceptance

- [ ] 5.1 [UNVERIFIED] Run the curator once and confirm every appended row carries `POST_MEDIA=ANIMATED`
- [ ] 5.2 [UNVERIFIED] Confirm a live `LinkedIn Post Sharing` run requests the animated type and that a forced animation failure still falls back to the image path
