# Design

## Context

Read from the code this change touches, and from run 13785 (2026-10-17), a real
`POST /webhook/visual-studio` for `tiles_wide` whose three turns are the measurement.

- `agents/n8n/workflows/visual_studio.workflow.json`, `build_author_brief`: the container is
  computed from the item in hand — `const width = Math.max(1, Number(a.VIEWPORT) || 1080);`,
  `const [aw, ah] = String(a.ASPECT || '4:5').split(':')`, `const declaredFrames =
  Math.max(1, Number(a.FRAMES) || 24);`, `const declaredSeconds = Math.max(1, Number(a.DURATION_SECONDS)
  || Math.round(declaredFrames / Math.max(1, Number(a.FPS) || 8)))`. Every one of those fallbacks
  is a *silent* default, and on a review turn all four fire at once.
- `parse_registry` is where the type's declared container enters the run: it emits `ASPECT`,
  `VIEWPORT`, `FPS`, `FRAMES`, `DURATION_SECONDS` (and `SCENE_SECONDS`) on the item that reaches
  `build_author_brief` through `if_agent`. It runs **once** per request, so a later turn has to be
  given those values; nothing in the loop carries them.
- The review path from the artifact back to the next brief:
  `agent_result` → `prepare_stills` (`{ ...asset, STILL_NAME, STILL_URL }`, one item per still) →
  `if_stills` → `fetch_still` → `encode_stills` → `critique` → `parse_verdict` → `if_review_findings`
  → `review_feedback` (`{ ...a, FEEDBACK, REVIEW_ROUND }`) → `build_author_brief`.
  `agent_result` returns items built from `base`, an explicit object literal that carries
  `ASSET_TYPE`, `RENDER_MODE`, `FORMAT`, `DURATION_MS`, `FRAME_COUNT`, `WIDTH`, `HEIGHT`,
  `CONFORMED`, `AUTHORED_FRAME`, `SHORT` — and none of the request's own container fields. The
  asset deliberately dropped them; nothing downstream noticed until a second turn needed them.
- The raster half does **not** have this defect, and the reason is worth keeping: its frame is
  read from a node, not from the item in hand — `generate_image` takes `aspect_ratio:
  $('if_raster').all()[$itemIndex].json.ASPECT` — so its fix turn (`raster_feedback` →
  `download_raster_prompt`) re-derives the image at the type's aspect whatever the item carries.
  `[UNVERIFIED]` by a live raster review turn; read from the applied graph.
- `agents/adapters/pi-render/session-lib.mjs`, `stillArgs`: for a clip it emits one `ffmpeg` per
  sampled offset (`-ss <t>`) plus one settled frame — `["-y", "-sseof", "-0.1", "-i", artifact,
  "-frames:v", "1", "-vf", "scale='min(1280,iw)':-2", "<dir>/review-final.jpg"]`.
- `session-server.mjs`, `makeStills`: each job is run in a `try`, its output name pushed only on
  success, and a failure is swallowed so "one still that cannot be made does not fail the turn".
  `runCommand` rejects on a non-zero exit. What it does not do is check that the file exists, and
  the settled-frame command does not exit non-zero on a clip whose frame interval is under the
  seek: measured with the server's own argument list and its own `spawn` path, on the run's
  artifact (1080×1350, 3.000 s, 8 fps), `exit=0`, **no file written**. The name is therefore
  pushed, the studio fetches it, and the session's artifact route serves whatever file is at that
  path — the previous turn's.
- `session-server.mjs` already probes the container (`probeContainer`) and hands the result to
  `transcodeArgs` and `conformanceNote`, so the frame rate this change needs is already read and
  available at the still call site.
- `prompts/visual_review_composition.md` orders the critic's findings and states that the last
  still is the settled frame and geometry is judged on it — which is what makes a stale settled
  still worth its own defect rather than a cosmetic one.

## Gate findings

- **The conformance delivered the wrong declaration faithfully.** Turn 1's note is
  `{frame: "1080x1350", authored: "1080x1350", fit: "scale", durationSeconds: 3, authoredSeconds:
  3, short: false}` and the served artifact `ffprobe`s as 1080×1350, 8 fps, 24 frames, 3.000 s —
  the declared container, exactly, rate included (30 → 8 was resampled). So
  `conform-artifact-to-type-frame` works; the declaration was wrong upstream of it, and the same
  run is the evidence both for that change and for this one.
- **The critic's correction pointed the wrong way for the same reason.** Turn 1's third finding
  and turn 2's first: *"the settled still is 16:9 (1280×720) and its HUD prints '1280 × 720', not
  the 1080x1350 (4:5) frame the brief declares — author/render the composition at 1080x1350"*.
  The critic read the frame off the brief it was given; the brief was the one this change fixes.
  A critic that judges against a wrong declaration is not a critic defect.
- **The still was reported as made while nothing was written.** Confirmed twice from the run:
  turns 1 and 2 both reported `stills: ["review-1.jpg", "review-2.jpg", "review-3.jpg",
  "review-final.jpg"]`, and `review-final.jpg`'s mtime is turn 0's (17:29 against 17:33/17:37).
  The seek is the cause, not the clip: at 8 fps, `-sseof` at 0.05 / 0.1 / 0.11 / 0.12 s writes
  nothing while 0.125 / 0.13 / 0.15 / 0.2 s writes the frame; the same 3 s clip re-encoded at 30
  fps writes it at `-0.1`. One frame at 8 fps lasts 0.125 s, so the seek has to reach the last
  frame's timestamp and 0.1 s does not.
- **A still that cannot be made leaves the previous turn's file behind**, because the output name
  is fixed (`review-final.jpg`) and the run directory is the same across turns. Any other cause of
  a failed capture — a killed ffmpeg, an unreadable artifact — has the same effect; the seek is
  only the one that happened.
- **The measured cost of the fix turn is real.** Turn 1 and 2 each re-authored the composition
  from a wrong brief, and the artifact of turn 0 (the type's own container) was overwritten in the
  bucket, because the object key is per run and asset type: `visual-studio/13785-tiles_wide.mp4`.
  So the defect does not only ship a wrong artifact, it destroys the right one.

## Decisions

### D1. The declared container rides on the asset

`agent_result` adds the request's own container (`ASPECT`, `VIEWPORT`, `FRAMES`,
`DURATION_SECONDS`, and the rate it derived as `FPS`) to `base`, so every item built from an asset
— the review items, the verdict item, the correction turn's input, the result — carries it. This
is the same place the declared frame, count and duration are already carried (`WIDTH`, `HEIGHT`,
`FRAME_COUNT`, `DURATION_MS`), so nothing new has to be threaded through the loop, and the run
record gains the request's shape beside the delivered one.

*Alternatives considered:* re-read the registry in `build_author_brief`
(`$('parse_registry').all()` matched by `ASSET_TYPE`) — correct but a second lookup whose item
order is the request's, and it would leave the asset's own record without the declaration;
carry the fields on `prepare_stills` only — the raster path builds no stills and the deck branch
goes elsewhere, so a single place that covers every asset is better than one per path.

### D2. A turn with no declared container fails loudly

`build_author_brief`'s four `|| default` fallbacks are the reason the defect was silent: it asked
for a 1080×1350 / 3 s clip and nobody noticed for two turns. The request's container is always
present when the item comes from `parse_registry` (which fills `ASPECT`, `VIEWPORT`, `FPS`,
`FRAMES`, `DURATION_SECONDS` from the registry's own defaults), so the honest behaviour for a
missing one is an error naming the field rather than a plausible invention. This is the repo's
rule about absence being expressible: a wrong declaration must be a run that stops, not a run that
delivers the wrong frame confidently.

*Alternative considered:* keep the defaults and log — a log line in n8n is not a failure path, and
the defect this change fixes is exactly a plausible default.

### D3. The settled frame is captured at a seek the clip's rate supports

`stillArgs` computes the settled-frame seek from the frame rate the container already reports
(`probeContainer`), at no less than one frame interval — `Math.max(1, Math.ceil(1 / fps)) / fps`,
with `-0.5 s` when the rate is unknown — instead of the fixed `-0.1`. The measured boundary is
0.125 s at 8 fps; a rate-derived offset is the same number for any rate this pipeline can produce,
and it costs one frame's decode rather than the whole clip.

*Implemented deviation.* The rate is the one the conformance **delivers** — `outputFps({ frames,
durationSeconds, fps })`, the declared rate — not the `probeContainer` reading taken at that call
site. That probe is read **before** the conformance, so on the measured run it reports the engine's
30 fps while the served artifact is 8 fps, and seeking at `1/30` would lose the settled frame in
exactly the case this change exists for. The declaration is the artifact's own rate by construction
(every kind is encoded with `fps=<declared>`), so it is both correct and rate-independent. A probe
of the served artifact after the transcode would have to be understood for a GIF, whose
`r_frame_rate` is an encoder artefact, and is not needed beside it.

*Alternatives considered:* write-through with `-update 1` (no seek at all, one file written per
frame, ending with the last) — correct and rate-independent (measured: the last frame at
1080×1350) but it decodes and re-encodes every frame of a twelve-second clip to keep one image;
`-sseof -0.5` as a flat value — works for the rates seen here and is a guess for a 2 fps type.

### D4. A still that was not written is not offered

Two halves, and both are needed because a fixed output name in a reused directory can hold an
earlier turn's file. Before a capture, the target file is removed; after it, the server checks
that the file exists and is not empty before reporting the name, and reports the stills it is
actually offering (which the studio already reads as `resp.stills`). A still that is not offered
is a review that judges one frame fewer — the existing "a still that cannot be made does not fail
the turn" behaviour — rather than a review that judges the wrong turn's frame.

## Risks

- **The correction turn now re-authors at the type's frame, which is a real edit.** The measured
  turn already cost ~4 minutes at the wrong frame; asking for 1280×720 / 12 s from a 1080×1350 /
  3 s composition is the same work, so no new bound is needed — but the loop can now spend its
  cycles re-framing, so the reviewer's findings and the frame declaration can disagree. Worth
  watching rather than pre-empted.
- **D2 converts a silent wrong artifact into a failed run.** A caller that reaches
  `build_author_brief` by a path this change did not consider would now stop instead of shipping.
  The paths are enumerated above and the offline test asserts the fields on each; a live
  verification of the ordinary and the review turn is the check.
- **The unused `FPS` field name.** `build_author_brief` already emits `FPS` as the derived rate;
  the asset's copy is the same number, so it must not be read as the type's declared
  `budget.fps` — the two are equal only while the declared frame count and length agree with the
  budget.

## Open questions

- **Is the composer's frame stable across turns once the declaration is right?** Turn 0 of run
  13785 was authored at the declared frame from an off-frame composition, so the answer looks
  like yes; a run whose correction turns keep the declaration is the test. `[UNVERIFIED]`.
- **How often is the settled-frame seek the reason a still is missing?** One measured instance,
  on the first clip this pipeline produced below 10 fps — which the derived rate makes ordinary
  rather than rare. `[UNVERIFIED]` beyond this run; D4 makes the failure visible either way.
- **Does the raster half need the same guard?** Its frame comes from `if_raster`, so it has no
  declared-container defect; whether its *review* has an equivalent (a stale data URL cannot occur,
  since the bytes ride the execution) is `[UNVERIFIED]` and out of scope.

## Definition of done

- `openspec validate --all` passes with this change present.
- Offline: a test fails without D1 (the asset carries the declared container, and a correction
  turn's brief declares the type's frame and length) and without D2 (a turn with no declared
  container stops and names the field); the adapter tests fail without D3 (a rate-derived seek,
  asserted at a sub-10 fps rate) and D4 (a capture that wrote nothing is not reported).
- Live: a reviewed asset's *last* turn is authored at the type's declared container, and its
  `WIDTH`/`HEIGHT`/`FRAME_COUNT`/`DURATION_MS` name that container; `ffprobe` of the artifact
  agrees.
- Live: the stills the review receives include a settled frame whose mtime is the turn being
  reviewed, and a still that could not be made is absent from the studio's fetch list.
- Applied and read back with `scripts/apply_workflow_changes.py` (guarded by `--require-edge`),
  the export diffed against live afterwards; the adapter image published and its digest pinned.
