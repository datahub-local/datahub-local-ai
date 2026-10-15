# Tasks

## 1. Brief

- [x] 1.1 In `build_author_brief`, extend `sceneLine` so a declared count greater than one asks for an opening title scene naming the subject and the clip carries the declared count plus the title; leave a count of one and a blank count unchanged (both copies of the export)

## 2. Test

- [x] 2.1 Add `test_a_multi_scene_request_opens_on_a_title_scene` to `agents/n8n/scripts/test_visual_studio_graph.py`, asserting the `scenes > 1` guard, the title-scene line and the `scenes + 1` total in both copies; run it and `ruff check`

## 3. Apply

- [x] 3.1 Apply `build_author_brief` live with `scripts/apply_workflow_changes.py --require-edge`, re-read and diff the export against live
- [x] 3.2 Reconciled an unapplied change found while previewing: the live `build_author_brief` and `parse_registry` lacked commit `88537ba`'s per-scene duration floor (`SCENE_SECONDS`, `secondsPerScene`) and the deck-era `sceneLine` in the deck branch, in the draft *and* in `activeVersion`, so the schedule ran the old code. Applied both nodes as the export's text; live's nodes, settings, connections, `name` and `activeVersion` now equal the export ([UNVERIFIED] on why 88537ba never reached the cluster)

## 4. Acceptance

- [x] 4.1 Verified live 2026-10-15 via `POST /webhook/visual-studio` with `ASSET_TYPES=animation&SCENES=4`: studio run 13443 (`COMPLETE`, `RENDERED`, mp4 1280x720, 40.0s / 1200 frames) whose `STORYBOARD` opens on scene 0 `Title - "The data platform loop"` and carries five scenes, the declared four plus the title. The request went to the studio's own webhook because `Visual Studio Test`'s `params` and `call_studio` nodes carry no `SCENES`, so `/webhook/visual-studio-test` cannot pass one
