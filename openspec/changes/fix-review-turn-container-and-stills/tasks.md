# Tasks

## 1. The declared container survives the loop (`agents/n8n/`)

- [x] 1.1 `visual_studio.workflow.json`, node `agent_result`: add the request's own container to
  `base` — `ASPECT`, `VIEWPORT`, `FRAMES`, `DURATION_SECONDS` and the derived rate (`FPS`) — so
  every item built from an asset carries the declaration the run was asked for. Both copies of the
  graph in the export.
  **Measured reason (run 13785, turns 1 and 2):** the correction turn's brief declared
  1080×1350 / 3 s / 24 frames / 8 fps for a `tiles_wide` request whose registry entry says 16:9 /
  1280 / 12 s / 360 / 30.
  Done: the five fields are read off `build_author_brief`'s item and ride on `base` beside
  `WIDTH`/`HEIGHT`/`FRAME_COUNT`/`DURATION_MS`.

- [x] 1.2 `build_author_brief`: stop inventing a container. A turn whose item carries no
  `ASPECT`/`VIEWPORT`/`FRAMES`/`DURATION_SECONDS` throws and names the missing field, instead of
  `Number(a.VIEWPORT) || 1080`, `a.ASPECT || '4:5'`, `Number(a.FRAMES) || 24` and
  `Number(a.FPS) || 8`. Both graph copies.
  **Read first, then edit:** the four fallbacks and their four defaults are in that node's
  `jsCode` today; `parse_registry` always fills these fields for a real type, so the throw is
  reachable only by a path that lost them.
  Done, with one correction to the premise: `parse_registry` did **not** always fill
  `DURATION_SECONDS` — `Number(t.durationSeconds || 0)` is `0` for the launch card, which declares
  no length, so the throw would have broken that type. `parse_registry` now completes the container
  from the type's own budget (`frames / fps`) when the type declares no length, so the brief's
  requirement is satisfiable by every real type; the derived value equals the old silent fallback,
  so the launch card is unchanged.

- [x] 1.3 Tests in `scripts/test_visual_studio_graph.py`, parametrized over both graph copies:
  the asset carries the declared container; a correction turn's item reaches `build_author_brief`
  with `ASPECT`/`VIEWPORT`/`FRAMES`/`DURATION_SECONDS` intact, so the next brief declares the
  type's frame and length rather than the defaults; `build_author_brief`'s container is not built
  from a literal default (the node's `jsCode` no longer contains `|| 1080`, `|| '4:5'`, `|| 24`
  and `|| 8` as container fallbacks); the raster path's frame still comes from `if_raster`.
  Prove each fails without 1.1/1.2 and record the counts.
  Done. Two textual tests per copy (the asset carries the five fields, the loop spreads the asset,
  the defaults are gone, `parse_registry` completes the container) plus a behavioural harness that
  runs the two Code nodes under `node` with n8n's own scope: `agent_result` builds the asset, that
  asset is fed to `build_author_brief`, and the correction turn declares 1280×720 / 360 / 12 / 30
  rather than 1080×1350 / 24 / 3 / 8; a missing `ASPECT`/`VIEWPORT`/`FRAMES`/`DURATION_SECONDS`
  each throws naming the field. **Without 1.1/1.2: 9 failed, 2 passed** in
  `-k container` (the two that pass assert other container facts).

- [x] 1.4 Run the offline gates from the repository root and record the result:
  `uv run -- pytest agents/n8n/scripts/ -q`.
  Done: **515 passed, 1 skipped**.

## 2. The settled-frame still, and a still that was not made (`agents/adapters/pi-render/`)

- [x] 2.1 `stillArgs`: take the frame rate the container reports and make the settled-frame seek at
  least one frame interval (`-sseof -<offset>` where `offset >= 1/fps`, `0.5` when the rate is
  unknown), instead of the fixed `-0.1`.
  **Measured boundary (run 13785's artifact, 1080×1350, 3.000 s, 8 fps, the server's own argument
  list and `spawn` path):** `-0.05`/`-0.1`/`-0.11`/`-0.12` write nothing; `-0.125`/`-0.13`/`-0.15`/
  `-0.2` write the frame; the same 3 s clip at 30 fps writes it at `-0.1`.
  Done as `settledFrameSeek(fps)`; the rate passed is the **declared** rate the conformance
  delivers, not the pre-conformance `probeContainer` (see design D3's *Implemented deviation*):
  the probe is read before the conformance and would seek `1/30` on an 8 fps artifact.

- [x] 2.2 `session-server.mjs`: pass the probed rate into `stillArgs`, and make `makeStills` treat
  a still as made only if its file exists and is non-empty — removing the target file before the
  capture, so a fixed name in a reused run directory can never serve an earlier turn's frame. The
  reported `stills` list stays the ones actually offered.
  Done: `makeStills` passes `outputFps({ frames, durationSeconds, fps })` and calls the new
  `captureStill({ dir, output, run })`, which removes the target, runs the capture and reports the
  still only when the file exists with bytes.

- [x] 2.3 Tests in `test/session-lib.test.mjs` and `test/session-server.test.mjs`: the
  settled-frame argument's offset is at least one frame interval at a sub-10 fps rate and at a
  high rate; a rate of zero or an unreadable container falls back rather than seeking `0`; a
  capture that writes nothing is not in the stills the server reports, and the previous file at
  that name is gone. Prove each fails without its change and record the counts; run
  `node --test test/` and record the total.
  Done: `settledFrameSeek` at 8/30/2/0.5 fps and 0/undefined/NaN/-1; `stillArgs`' `-sseof` at 8 fps
  (`-0.125`), 30 fps (≥ `1/30`) and with no rate (`-0.5`); `captureStill` for exit-0-writes-nothing
  (with a planted earlier file removed), a written file, a failed run and an empty file; and the
  server-level test that plants `review-final.jpg`, runs a turn whose capture cannot write, and
  asserts it is absent from `stills`, gone from disk and 404 from the artifact route. **Without
  2.1: 1 failed** (`stillArgs seeks the settled frame…`); **without 2.2: 1 failed** (the server
  test). `node --test 'agents/adapters/pi-render/test/*.test.mjs'`: **60 passed, 1 skipped**.

## 3. Apply and verify live

- [x] 3.1 Ask the owner before writing, per the repository rule: show the graph diff (live against
  the export) and the plan for 1.1/1.2 and get an explicit answer. The studio is published, so a
  `PUT` plus a `publish` is the apply.
  Done: the guarded dry run was shown and approved; live equalled the export on every other node,
  so the three `jsCode` fields were the whole diff.
- [x] 3.2 Apply with `scripts/apply_workflow_changes.py`, guarded by `--require-edge` for the
  edges `agent_result` and `build_author_brief` sit on (`agent_result > prepare_stills`,
  `store_paired_artifact > agent_result`, `if_agent > build_author_brief`,
  `review_feedback > build_author_brief`, `build_author_brief > execute_author`), dry run first.
  Re-read `activeVersion`, confirm `active`, and diff the export against live.
  Done (2026-10-17): all five edges `ok`; the three fields wrote with **0 MISMATCH**; `active: True
  -> True`; the published `activeVersion` moved `1860be1d…` → `25203539-1a61-46d2-9271-1cf0797462cf`
  (equal to `activeVersionId`, 45 nodes) and its three nodes equal the export byte-for-byte.
- [x] 3.3 Read the applied `agent_result` and `build_author_brief` back out of live and execute
  them under `node` with stubbed responses, the way this repository verifies a Code node: the
  asset carries the declared container, a correction turn's brief declares the type's frame and
  length, and an item with no container throws naming the field.
  Done against the live `activeVersion` bytes: the asset carries 16:9 / 1280 / 360 / 12 / 30; that
  asset's correction turn declares 1280×720 / 360 / 12 / 30 (`AUTHOR_BODY` agrees); each of
  `ASPECT`/`VIEWPORT`/`FRAMES`/`DURATION_SECONDS` missing throws naming that field.
- [ ] 3.4 Adapter image: publish through CI, confirm ArgoCD pinned the new digest and the session
  pod restarted onto it, then read `stillArgs`/`makeStills` back out of the running pod.
  **Blocked on the merge:** `publish-images.yaml` builds this image on `workflow_run` after
  `Test Agents` completes on `main` (or `workflow_dispatch` target `adapters`, or the Thursday
  schedule), and the digest is pinned by a follow-up commit. Not runnable from a branch.
- [ ] 3.5 Live: one reviewed asset whose request declares a type the composer does not author by
  default, and read back — the *last* turn's declared container is the type's (`WIDTH`/`HEIGHT`/
  `FRAME_COUNT`/`DURATION_MS` on the final asset), `ffprobe` of the served artifact agrees, the
  settled still's mtime is that turn's, and the stills the studio fetched are the ones the session
  reported. Record the run id, the turns and the cost.
- [ ] 3.6 Live: force the still path to fail (a rate whose seek the old code would have missed is
  the natural one) and confirm the review proceeds without the settled frame rather than judging
  an earlier turn's — the artifact is still reported and the missing still is visible.

## 4. Documentation and record

- [x] 4.1 `AGENTS.md`, the studio section: a correction turn keeps the request's declared
  container (and why: the review loop's item is asset-shaped and the declaration is carried, not
  re-derived), a turn with no declaration stops rather than defaulting, and the settled-frame seek
  is rate-derived with a still that was not written never offered. Carry the measured numbers from
  run 13785 as the reason.
  Done: a paragraph after the self-review section in `AGENTS.md`, with 13785's numbers, the
  overwritten-key consequence and the raster half's exemption.
- [x] 4.2 `agents/sympozium/MEMORY.md`'s composer section (or the adapter README where the render
  contract lives): the codec-level fact — `ffmpeg -sseof` shorter than one frame interval exits 0
  and writes nothing, so a "capture the last frame" step has to be rate-aware *and* verified by the
  file, not by the exit code.
  Done: a "The stills a review looks at" section in `agents/adapters/pi-render/README.md`, where the
  render contract lives, naming 13785 and why the rate is the declared one.
- [ ] 4.3 Leave every `[UNVERIFIED]` in `design.md` honest after §3: resolve the composer's frame
  stability across turns and the raster half's exposure where the run measured them, and keep
  marked what it did not.
  Partly done: D3's implemented deviation is recorded; the live questions (frame stability across
  turns, the raster review's exposure) stay `[UNVERIFIED]` until §3 runs.
- [ ] 4.4 Archive only when the export matches live, the adapter is live, and a reviewed asset has
  been authored at the type's container end to end:
  `openspec archive fix-review-turn-container-and-stills`.
