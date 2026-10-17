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

- [x] 4.3 Apply to the live instance with `scripts/apply_workflow_changes.py`, guarded by
  `--require-edge` for the edges the node sits on, after the adapter image carrying §1–§2 is
  live — never before, or the note is reported and dropped. Dry run, show the diff, ask, then
  `--apply`; re-read `activeVersion`, confirm `active`, and diff the export against live.
  **Applied and verified 2026-10-17.** The image half was live first, checked rather than
  assumed: the running session pod's `/usr/local/bin/session-lib.mjs` carries `needsConformance`
  and `conformanceNote` (digest `3c6983cd…`, the pin from `d5ee84d`). The read diff against
  live was exactly this change and nothing else — `agent_result` gains the `conformance` read
  and `CONFORMED`/`AUTHORED_FRAME`/`SHORT`, `build_author_brief` gains `height: height` on
  `AUTHOR_BODY`, `normalize_input` and every connection identical, 45 nodes on both sides.
  Owner answered apply; the dry run held all six premises (`if_agent>build_author_brief`,
  `review_feedback>build_author_brief`, `build_author_brief>execute_author`,
  `if_deck>agent_result`, `store_paired_artifact>agent_result`, `agent_result>prepare_stills`)
  and `--apply` wrote both fields with no `MISMATCH`, `active: True -> True`, so no
  deactivate/activate cycle was needed. Read-back: `versionId == activeVersionId ==
  fd939b98…`, and **both** graph copies carry `CONFORMED:` in `agent_result` and
  `height: height` in `build_author_brief` — the published graph is the edited one, and live
  now matches the export node-for-node.

- [x] 4.4 Read the applied node back and execute it with a stubbed `execute_author` response
  under `node`, the way the `tiles` change verified `normalize_input`: a note present lands on
  the asset, an absent note leaves the fields empty, and neither throws.
  **Landed 2026-10-17, against the live read-back (not the export).** Both applied `jsCode`
  bodies were fetched out of live and executed under `node v26.12.0` with stubbed `$` nodes:
  14 assertions, all passing. A note of `fit: crop` / `authored: 1080x1350` lands as
  `CONFORMED: "crop"`, `AUTHORED_FRAME: "1080x1350"`, `SHORT: false` with `WIDTH`/`HEIGHT`/
  `FRAME_COUNT` still the declared ones; no note at all leaves `CONFORMED`/`AUTHORED_FRAME`
  as `""` and `SHORT` `false` with no `undefined` field and the asset still `RENDERED`; a
  non-object note (a bare string) is tolerated the same way; a `short: true` note is carried.
  `build_author_brief` posts `height` beside `width` (1280×720 for the 16:9 type, 1080×1350
  derived for a 4:5 one) and states the frame in the brief.

## 5. Verification (a live render of a known-off container)

- [x] 5.1 Render through the `tiles_wide-13745` session (whose composition in the run
  directory is 1080×1350 — a measured mismatch) with the same request shape the tile work
  used, and read back: the served artifact is at the declared 16:9 frame, `ffprobe` of the
  served bytes agrees with `WIDTH`/`HEIGHT`, the frame count is the declared 360 at the
  derived rate, and the length is at most the declared 12 s.
  **Verified 2026-10-17, run 13785** — a real `POST /webhook/visual-studio` (`ASSET_TYPES=tiles_wide`,
  `FORCE=tiles`, `STYLE=dark`, `SESSION_ID=tiles_wide-13745`), `HTTP 200` in 822 s. The first of
  the run's three turns is the measurement: the engine rendered **1280×720, 12.500 s, 375
  frames, 30 fps, 8.1 MB** (the composer's own `ffprobe`, quoted in its report, which also says
  the composition *was* 1080×1350 / 3 s and the brief now asks 1280×720 / ~12 s), the type
  declares **1280×720, 12 s, 360 frames, 30 fps**, and the asset carries `CONFORMED: "scale"`,
  `AUTHORED_FRAME: "1280x720"`, `SHORT: false`, `WIDTH 1280`, `HEIGHT 720`, `FRAME_COUNT 360`,
  `DURATION_MS 12000` beside `S3_BYTES 3716412`. So the length was conformed — 12.5 s trimmed to
  the declared 12 s, 375 frames to the declared 360 at the declared rate — and the record agrees
  with the artifact instead of asserting the request over it.
  **Read from the execution, not the storyboard:** `parse_registry` emitted the registry's
  values (`ASPECT 16:9`, `VIEWPORT 1280`, `FRAMES 360`, `DURATION_SECONDS 12`, `FPS 30`),
  `build_author_brief` derived `WIDTH 1280` / `HEIGHT 720` from them, and `agent_result` carried
  the session's note onto the asset. The three turns each rendered and stored, so the *last*
  turn's bytes are what the caller receives; `ffprobe` of them (in the session pod, after the
  run) reads exactly the container that turn declared. `[UNVERIFIED]` that the frame would have
  been *cropped* live: the composer re-authored the composition at the declared 16:9 during this
  turn (its own report says so), which is the behaviour the brief asks for and the reason the
  live measurement is a trim-and-scale rather than a crop. The crop is measured in 5.2.

- [x] 5.2 Confirm the note answers honestly: `authored` names 1080×1350, `fit` is `crop`, and
  the run record's asset carries both, so a reviewer can see the composer authored the wrong
  frame from the record alone.
  **Measured deterministically against the real bytes, on the live image's own code**, because
  the live turn no longer has an off-frame render to crop (5.1) and the run's artifact key is
  per run and type, so each turn overwrites the previous turn's bytes and the earlier render is
  gone. In the running session pod, `import { needsConformance, transcodeArgs, conformanceNote }
  from '/usr/local/bin/session-lib.mjs'` — the code the cluster runs, digest `3c6983cd…` — fed
  the *real* `out.mp4` of `tiles_wide-13745` (the 13762 revision: **1080×1350, 3.000 s, 90 frames,
  30 fps, 2,640,886 bytes**) against `tiles_wide`'s declared 1280×720 / 12 s / 360 frames / 30 fps:
  `needsConformance` **true**; arguments
  `["-y","-t","12","-i","out.mp4","-vf","fps=30,scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720","-c:v","libx264","-preset","veryfast","-crf","18","-pix_fmt","yuv420p","out.conformed.mp4"]`;
  the note **`{frame: "1280x720", authored: "1080x1350", fit: "crop", durationSeconds: 12,
  authoredSeconds: 3, short: true, reason: ""}`**. Running those arguments on those bytes and
  probing the result: **1280×720, 3.000 s, 90 frames, 1,157,285 bytes** — framed as declared,
  delivered short and reported as such rather than extended (D4). The same note shape is what
  `agent_result` carries: the live run's assets show `AUTHORED_FRAME` and `CONFORMED` filled from
  it, and a missing note leaves them empty (4.4, executed from the live read-back).

- [x] 5.3 Confirm the stills the review received are frames of the conformed artifact (the
  stills' pixel size matches the declared frame) — the review must not be judging a crop the
  caller never receives.
  **Measured, and it exposed a defect of its own.** The stills are made after the transcoder
  (`makeStills` runs after `transcode`), and for the run's last turn the three regenerated stills
  are **1080×1350** — the declared frame of that turn, which is also what the artifact was
  conformed to. The settled still `review-final.jpg` was **1280×720**, i.e. left over from an
  earlier turn: `ffmpeg -sseof -0.1 -frames:v 1` produces **no file at all** on that clip
  ("Output file is empty, nothing was encoded", exit 2) because its frame interval is 0.125 s
  (8 fps) and the seek is 0.1 s, and `makeStills` swallows a single still's failure by design.
  Measured on the same clip: `-sseof -0.1` **empty**, `-sseof -0.2` and `-sseof -0.5` **ok**, and
  the same 3 s clip re-encoded at 30 fps `-sseof -0.1` **ok** — so the failure is the seek being
  shorter than one frame interval, not the clip. The review prompt tells the critic to judge
  geometry on the **last** still, so a stale settled frame is judged. Spin-out: it is one of the
  two defects `openspec/changes/fix-review-turn-container-and-stills/` records.

- [x] 5.4 Check the no-op path costs nothing: a second render whose composition already
  matches the declared frame serves the engine's output without a second encode (the
  response's `fit` is `none` and the byte size is the engine's).
  **The decision is measured in the live image; a live run whose render already matched was not
  produced** — every turn of run 13785 differed from its declaration (a trim on turn 0, a
  re-authored frame on the later turns), so none was a no-op. Run in the session pod against
  `session-lib.mjs` as the cluster ships it, with `tiles_wide`'s declaration: an exact match and
  a render one frame short (within the shared one-and-a-half-frame tolerance) both answer
  `needsConformance=false`, `transcodeArgs=null`, `fit=none`; one pixel of width or half a second
  of length differ and it conforms (`fit=scale`). No second encode is paid on the matching path,
  and the two tolerances are one constant (`lengthTolerance`) shared by the decision and the note,
  so they cannot disagree.

- [x] 5.5 Record what the run exposed, since it is not this change's defect but this change's
  instrument found it: on a review turn `build_author_brief` receives an *asset-shaped* item
  (from `prepare_stills` → `parse_verdict` → `review_feedback`) that carries no `ASPECT`,
  `VIEWPORT`, `FRAMES`, `DURATION_SECONDS` or `FPS`, so its own defaults become the fix turn's
  declared container — measured on run 13785: turn 1 and turn 2 declared **1080×1350 / 3 s / 24
  frames / 8 fps** where the registry says 16:9 / 1280 / 12 s / 360 frames / 30 fps, the composer
  authored that, and the conformance faithfully delivered it (`CONFORMED: "scale"`, final artifact
  `ffprobe` **1080×1350, 8 fps, 24 frames, 3.000 s, 660,531 bytes**, matching `WIDTH 1080` /
  `HEIGHT 1350` / `FRAME_COUNT 24` / `DURATION_MS 3000` / `S3_BYTES`). The critic compounded it:
  told by the degraded brief that 1080×1350 was declared, it demanded the composer change the
  correct 16:9 composition to 4:5. Together with the stale settled still (5.3) this is why run
  13762's second render was 1080×1350 / 3 s — the cause was attributed in this change's design to
  "the composer's frame is unenforced" and is in fact the review loop re-declaring it. Both
  defects are spun out into `openspec/changes/fix-review-turn-container-and-stills/`; this change
  is complete without them and says so rather than absorbing them.


## 6. Documentation

- [x] 6.1 Update the Visual Studio section of `AGENTS.md`: an artifact's container is the
  type's, the runtime conforms it after the render (mp4 included), an aspect mismatch is
  covered and reported rather than fixed in the composer, a short render is never extended,
  and the record's `WIDTH`/`HEIGHT`/`FRAME_COUNT`/`DURATION_MS` describe the declared
  container — with the measured run 13762 numbers as the reason.
  **Landed.** A paragraph after the frame-is-the-type's-data one, carrying the 13762
  measurement (1080×1350 / 30 fps / 90 frames / 3.000 s against a declared 16:9 / 1280 / 12 s /
  360 frames), the engine's missing viewport flag, the cover-crop and the trim-never-extend
  rule, the `mp4` exemption that used to be, the note's three fields, and the no-second-encode
  and `fit: unknown` cases.

- [x] 6.2 Note in `agents/sympozium/MEMORY.md`'s composer section (or the adapter's own
  README, whichever already carries the render contract) that the engine has no viewport
  flag, so a composition authored at the wrong frame can only be conformed afterwards —
  the fact that decided the shape of this change.
  **Landed in the adapter's README**, which is where the artifact contract lives
  (`### The artifact contract (a workflow caller)`): the declared numbers are stated as the
  container the caller receives, with the probe-and-re-encode that delivers it, the
  cover-crop and trim rules, the engine's missing viewport flag as the reason the
  conformance cannot be a re-render, the note's shape, and the unreadable-container case.

- [x] 6.3 Leave every `[UNVERIFIED]` in `design.md` honest after §5: resolve what was
  measured (the crop, the trim, the no-op path) and keep marked what was not (whether the
  critic notices a frame mismatch; whether a responsive composition removes the need).
  **Landed, and one marker resolved the other way round.** The crop resolves against the real
  1080×1350 bytes with the live image's own code (5.2), the trim and the declared frame count
  resolve against the live turn (12.5 s → 12 s, 375 → 360 frames at 30 fps, 5.1), and the no-op
  decision resolves in the live image (5.4) while a *live* no-op turn stays unmeasured. The
  critic's frame awareness was expected to stay marked and is **resolved**: it names the frame
  from the stills and asks for one — the run then showed its correction can point the wrong way
  when the fix turn's brief has re-declared the container, which is a gate finding and a spun-out
  change rather than an open question here. A responsive composition stays `[UNVERIFIED]`, with
  the run's own evidence added: told the declared frame, the composer rebuilt rather than scaled.
  The drift-frequency question gains its first reading (three turns: one correct declaration
  honoured, two turns drifted because the loop had re-declared the frame).

- [x] 6.4 Archive only when the adapter is live, the workflow is applied and read back, and a
  live render has been conformed end to end: `openspec archive conform-artifact-to-type-frame`.
  **Archived 2026-10-17** as `2026-10-17-conform-artifact-to-type-frame`: the adapter carrying
  §1–§2 was live before the apply (checked in the pod), the graph was applied and read back (both
  copies, `active` unchanged, the published version carrying it), and a live render was conformed
  end to end on run 13785 — the declared frame and length delivered, the crop measured against the
  real 1080×1350 bytes with the live image's own code, and the record carrying the note. The
  defects the run exposed are not this change's and are recorded in
  `openspec/changes/fix-review-turn-container-and-stills/`.
