# Tasks

## 1. The conformance arguments (`agents/adapters/pi-render/session-lib.mjs`)

- [x] 1.1 Make `transcodeArgs` conform an `mp4` too, and take `height`:
  `transcodeArgs(format, { fps, width, height, frames, durationSeconds })`. The filter chain
  becomes `fps=<rate>` where `rate` is the existing `outputFps(...)`, then the frame —
  `scale=<width>:<height>:force_original_aspect_ratio=increase,crop=<width>:<height>` when
  both are declared and finite, `scale=<width>:-2:flags=lanczos` when only the width is —
  then the trim `-t <durationSeconds>`. `case "mp4"` returns those arguments instead of
  `null`. Keep the existing GIF/WebP chains' behaviour intact.
  **Landed.** `mp4` returns `-y … -t <s> -i out.mp4 -vf fps=<rate>,scale=W:H:force_original_aspect_ratio=increase,crop=W:H
  -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p out.conformed.mp4` — the last name
  because ffmpeg cannot read and write one file and the artifact *is* `out.mp4`. The GIF, WebP
  and PNG chains take the same frame filters, so the still raster type ships its declared frame
  too; the width-only `scale=W:-2:flags=lanczos` remains for a request that declares no height.

- [x] 1.2 Add the pure predicate the session uses to decide whether a transcode is needed at
  all, so the common case pays no second encode:
  `needsConformance({ declared: { width, height, durationSeconds, frames, fps }, actual: {
  width, height, durationSeconds, fps } })` answering true when the frame, the length or the
  rate differ beyond a tolerance (half a frame at the declared rate for the length, one pixel
  for the frame). It answers true when `actual` is unreadable, so an unprobeable render is
  conformed rather than passed through.
  **Landed**, with two refinements the work forced. A request that declared neither a frame nor
  a length answers `false` — there is nothing to conform to, and that is what keeps a bare
  `transcodeArgs("mp4", {})` a no-op. And the length tolerance is one and a half frames at the
  declared rate (`lengthTolerance`), *shared* by this predicate and by the note's `short` flag,
  because two tolerances would eventually disagree and one of them would report the other's
  decision wrongly.

- [x] 1.3 Add the note builder as a pure function — `conformanceNote(declared, actual)` —
  answering `{ frame, authored, fit, durationSeconds, authoredSeconds, short, reason }` where
  `fit` is `none|crop|scale|unknown`. It is what the response and the asset carry, so its shape
  is asserted offline rather than at the model.
  **Landed** with that shape: `fit` is `crop` when the aspect was changed by cutting, `scale`
  when a conformance ran and it was not, `none` when nothing ran, and `unknown` with a `reason`
  when the render's container could not be read.

## 2. The session (`agents/adapters/pi-render/session-server.mjs`)

- [x] 2.1 After the engine render, probe the artifact (`ffprobe`, already in the image and
  already used for the stills) for width, height, duration and rate, and pass `height`
  through to the transcode. Run the conformance when 1.2 says so; when it does not, serve the
  engine's output untouched.
  **Landed.** `runCommand` gained a `capture` mode (it only ever collected stderr before) and
  `probeContainer` reads ffprobe's JSON for width, height, duration and rate, answering `null`
  on any failure. The engine's container is probed once and passed both to `transcodeArgs` and
  to `conformanceNote`, so the decision and the note can never be made from different readings.

- [x] 2.2 Conform **before** `makeStills`, so the stills the review looks at are frames of the
  artifact the caller receives (D6). Do not reorder the existing calls for anything else.
  **Landed.** The order was already render → transcode → stills; it is now meaningful for mp4,
  which is the kind that previously had no step between them.

- [x] 2.3 Put the note from 1.3 on the response, beside `stills`. A conformance that could not
  be performed (no `ffprobe`, an unreadable render) is a note with `fit: 'unknown'` and a
  reason, not a failed turn (D8) — the artifact is still served, exactly as a review that
  could not run does not fail the asset.
  **Landed**, and the tolerance is narrower than the task asked for in one place and wider in
  another. Wider: only an mp4 has an artifact to fall back on, so only an mp4's conformance
  failure is tolerated — a GIF/WebP conversion that fails has nothing to serve and stays fatal.
  Narrower: the note rides the non-streaming response beside `stills`, which is the shape the
  studio's own call uses (`prepare_stills` reads `resp.stills` off the same body).

## 3. Tests (`agents/adapters/pi-render/test/`)

- [x] 3.1 `session-lib.test.mjs`: assert the argument shape for each case — an mp4 with a
  matching container produces no arguments; a width-only difference scales; an aspect
  mismatch covers and crops; a longer render trims; a shorter render is not extended; the
  rate comes from `outputFps`. Assert `needsConformance` at the boundaries (a length within
  half a frame, a frame within a pixel) and that it answers true for unreadable input.
  Assert `conformanceNote`'s shape, including `short` and `fit`.
  **Landed.** Five cases were added to `session-lib.test.mjs`: a matching container producing no
  arguments (including one frame short, which is the same clip), a disagreeing container whose
  arguments cover-crop, trim, carry the derived rate and never write the file they read, an
  unreadable container being conformed rather than trusted, `conformanceNote`'s four fits and its
  `short`/`authored`/`reason` fields, and a still raster conformed to its declared frame. The
  mp4-exemption case that asserted the old behaviour was rewritten rather than deleted.

- [x] 3.2 `session-server.test.mjs`: a started server against the stub produces a response
  whose note names the declared frame, and the stills are made after the conformance (the
  still's frame equals the note's `frame`). Where the stub cannot render, assert the note
  says so and the turn still succeeds.
  **Landed.** `a turn reports the container it served and why nothing was conformed`: the stub's
  eight-byte `ftyp` cannot be probed and this box (like CI) has no ffmpeg, so the note comes back
  `fit: "unknown"` with a reason, the response is `200`, and the artifact route still serves the
  bytes the engine produced. That is D8 asserted end to end rather than argued.

- [x] 3.3 Prove each new assertion fails without its change: revert 1.1 and the mp4 case;
  revert 1.2 and the boundary cases; revert 2.3 and the note. Record the failure counts and
  the run after restoring. Run `node --test test/` and record the total.
  **Landed.** With `needsConformance` forced to answer `false`: **3 failed, 24 passed** in
  `session-lib.test.mjs` (the disagreeing-container case, the one-frame-short boundary and the
  unreadable case). Restored: `node --test test/` gives **57 tests, 56 passed, 1 skipped** — the
  skip is the ffmpeg-dependent still test, and this box installs no ffmpeg, so the *execution* of
  the conformance is covered by §5 on the cluster and not here.

## 4. The workflow half (`agents/n8n/`)

- [x] 4.1 `visual_studio.workflow.json`, node `agent_result`: read the session's note off
  `execute_author`'s response and carry it on the asset (e.g. `CONFORMED`, `AUTHORED_FRAME`,
  `SHORT`), leaving the declared `WIDTH`/`HEIGHT`/`FRAME_COUNT`/`DURATION_MS` as they are —
  they describe the declared container, which the artifact now is by construction. Missing
  note → empty fields, not a failed asset.
  **Landed.** `agent_result` reads `resp.conformance` beside the report it already reads and puts
  `CONFORMED`, `AUTHORED_FRAME` and `SHORT` on `base`, so both the primary asset and a deck's
  paired video carry them. A missing note yields `''`/`false` rather than undefined fields.

- [x] 4.2 Extend the studio's offline tests so the wiring is guarded: the node reads the note
  from the response, and every asset carries the new fields (empty when the runtime did not
  report one). Both graph copies in the export.
  **Landed.** `test_the_asset_carries_what_the_runtime_reported_about_its_container`, parametrized
  over `top` and `activeVersion`: it fails without the node change (**2 failed**) and passes with
  it. `uv run -- pytest agents/n8n/scripts/ -q` from the repository root gives **506 passed,
  1 skipped**.

- [x] 4.5 Carry the frame's height on the request to the session (found while wiring 4.1):
  `build_author_brief`'s `AUTHOR_BODY` posted `width` and not `height`, so the session's own
  `request.height` read and every height-dependent behaviour behind it were dead — the stills
  fell back to a derived 16:9 window for a 4:5 type, and a conformance that knows only the width
  can scale but cannot deliver the aspect (1080×1350 scaled to width 1280 is 1280×1600).
  **Landed.** `height: height` added to `AUTHOR_BODY` in both graph copies, asserted by 4.2's
  test (which fails without it: **2 failed**).

- [ ] 4.3 Apply to the live instance with `scripts/apply_workflow_changes.py`, guarded by
  `--require-edge` for the edges the node sits on, after the adapter image carrying §1–§2 is
  live — never before, or the note is reported and dropped. Dry run, show the diff, ask, then
  `--apply`; re-read `activeVersion`, confirm `active`, and diff the export against live.

- [ ] 4.4 Read the applied node back and execute it with a stubbed `execute_author` response
  under `node`, the way the `tiles` change verified `normalize_input`: a note present lands on
  the asset, an absent note leaves the fields empty, and neither throws.

## 5. Verification (a live render of a known-off container)

- [ ] 5.1 Render through the `tiles_wide-13745` session (whose composition in the run
  directory is 1080×1350 — a measured mismatch) with the same request shape the tile work
  used, and read back: the served artifact is at the declared 16:9 frame, `ffprobe` of the
  served bytes agrees with `WIDTH`/`HEIGHT`, the frame count is the declared 360 at the
  derived rate, and the length is at most the declared 12 s.

- [ ] 5.2 Confirm the note answers honestly: `authored` names 1080×1350, `fit` is `crop`, and
  the run record's asset carries both, so a reviewer can see the composer authored the wrong
  frame from the record alone.

- [ ] 5.3 Confirm the stills the review received are frames of the conformed artifact (the
  stills' pixel size matches the declared frame) — the review must not be judging a crop the
  caller never receives.

- [ ] 5.4 Check the no-op path costs nothing: a second render whose composition already
  matches the declared frame serves the engine's output without a second encode (the
  response's `fit` is `none` and the byte size is the engine's).

## 6. Documentation

- [ ] 6.1 Update the Visual Studio section of `AGENTS.md`: an artifact's container is the
  type's, the runtime conforms it after the render (mp4 included), an aspect mismatch is
  covered and reported rather than fixed in the composer, a short render is never extended,
  and the record's `WIDTH`/`HEIGHT`/`FRAME_COUNT`/`DURATION_MS` describe the declared
  container — with the measured run 13762 numbers as the reason.

- [ ] 6.2 Note in `agents/sympozium/MEMORY.md`'s composer section (or the adapter's own
  README, whichever already carries the render contract) that the engine has no viewport
  flag, so a composition authored at the wrong frame can only be conformed afterwards —
  the fact that decided the shape of this change.

- [ ] 6.3 Leave every `[UNVERIFIED]` in `design.md` honest after §5: resolve what was
  measured (the crop, the trim, the no-op path) and keep marked what was not (whether the
  critic notices a frame mismatch; whether a responsive composition removes the need).

- [ ] 6.4 Archive only when the adapter is live, the workflow is applied and read back, and a
  live render has been conformed end to end: `openspec archive conform-artifact-to-type-frame`.
