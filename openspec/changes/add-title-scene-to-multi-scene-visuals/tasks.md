# Tasks

## 1. Brief

- [x] 1.1 In `build_author_brief`, extend `sceneLine` so a declared count greater than one asks for an opening title scene naming the subject and the clip carries the declared count plus the title; leave a count of one and a blank count unchanged (both copies of the export)

## 2. Test

- [x] 2.1 Add `test_a_multi_scene_request_opens_on_a_title_scene` to `agents/n8n/scripts/test_visual_studio_graph.py`, asserting the `scenes > 1` guard, the title-scene line and the `scenes + 1` total in both copies; run it and `ruff check`

## 3. Apply

- [x] 3.1 Apply `build_author_brief` live with `scripts/apply_workflow_changes.py --require-edge`, re-read and diff the export against live
- [x] 3.2 Reconciled an unapplied change found while previewing: the live `build_author_brief` and `parse_registry` lacked commit `88537ba`'s per-scene duration floor (`SCENE_SECONDS`, `secondsPerScene`) and the deck-era `sceneLine` in the deck branch, in the draft *and* in `activeVersion`, so the schedule ran the old code. Applied both nodes as the export's text; live's nodes, settings, connections, `name` and `activeVersion` now equal the export ([UNVERIFIED] on why 88537ba never reached the cluster)

## 4. Acceptance

- [ ] 4.1 [UNVERIFIED] Run a multi-scene request (e.g. `SCENES=4`) through the studio and confirm the authored visual opens on a title scene and carries five scenes
