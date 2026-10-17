# Design

## Context

Read from the code this change touches, and from the runs that motivated it.

- `agents/adapters/pi-render/session-lib.mjs`, `transcodeArgs(format, { fps, width, frames,
  durationSeconds })`: derives `rate = outputFps({ frames, durationSeconds, fps })`, builds
  `fps=<rate>` plus `scale=<width>:-2:flags=lanczos`, and takes `-t
  <durationSeconds>` as a trim. Its own comment states the intent — "A declared duration
  trims the input to that length, so the frame count is what the type budget says it is even
  if the agent's render ran long" — and then `case "mp4": return null`, documented as "no
  transcode is needed (mp4)".
- `agents/adapters/pi-render/session-server.mjs` reads `format`, `fps`, `width`, `height`,
  `frames` and `durationSeconds` off the request; renders; calls
  `transcode(dir, format, { fps, width, frames, durationSeconds })`; then calls
  `makeStills(dir, { format, width, height, durationSeconds })`. **`height` is received and
  never passed to the transcode**, which is why the current conformance can only ever scale
  the width.
- The response is an OpenAI-chat-shaped object carrying a bespoke `stills` field, which the
  studio's own review nodes read. A bespoke field for the conformance note is the same shape
  the adapter already uses.
- `visual_studio.workflow.json`, `agent_result`: builds `WIDTH`, `HEIGHT`, `FRAME_COUNT` and
  `DURATION_MS` from `build_author_brief`, i.e. from `visual_types.json`'s values — so they
  describe the request, not the artifact.
- `hyperframes render --help` in the image (v0.8.158, read 2026-10-17) has **no viewport or
  size flag**: the frame comes from the composition's own `data-width`/`data-height`, which
  is why run 13762's file is 1080×1350 with no way to re-render it at 1280×720. It does take
  `-f/--fps`, but only as an integer or a rational, so a derived fractional rate (the GIF
  type's `outputFps`) still belongs in the ffmpeg filter rather than the engine call.
- `openspec/specs/visual-studio/spec.md`, "Types are declared in a registry" and the registry
  itself: an animated type must not mandate a frozen final frame (`holdSeconds` is asserted
  absent, and the `tiles` pair documents "no per-scene floor"). Extending a short render by
  holding its last frame would do exactly what that rule forbids.

## Gate findings

- **The session never received the frame's height.** `session-server.mjs` reads
  `request.height` and `stillArgs` has always taken it, but `build_author_brief`'s
  `AUTHOR_BODY` posted `width` without it — so every height-dependent behaviour was dead: the
  stills fell back to a derived 16:9 window for a 4:5 type, and a conformance would have had
  only a width to scale to (a 1080×1350 render scaled to width 1280 becomes 1280×1600, which is
  still not the declared frame). Found while wiring this change and fixed in it (4.5): the
  request now carries both numbers of the declared frame.
- **The one path every video type takes is the one path without conformance.** `mp4` returns
  `null` from `transcodeArgs`; `gif`, `webp` and the stills path are conformed. Run 13762 is
  that hole measured: `ffprobe` of the served artifact reads
  `width=1080 height=1350 30/1 nb_frames=90 duration=3.000000` for a type declaring
  16:9 / viewport 1280 / 12 s / 360 frames.
- **The run record cannot show the drift.** Execution 13762's asset carries `WIDTH 1280`,
  `HEIGHT 720`, `FRAME_COUNT 360`, `DURATION_MS 12000` — the declared values — beside an
  `S3_KEY` pointing at a 1080×1350, 90-frame, 3 s file. A reader of the record has no way to
  see that the artifact disagrees with it.
- **The composer's frame is not a value the pipeline can re-render.** With no viewport flag
  on the engine, a composition authored at the wrong frame can only be conformed after the
  render. Cover-cropping is lossy; the alternative is a letterboxed artifact or an
  un-delivered frame, and the change reports which was taken.
- **A previous run missed only the length** (13745: 12.5 s against a declared 12 s, into a
  correct 1280×720 frame). Trimming closes that case; nothing reopens it.
- **The stills already come after the transcode**, so the review will judge the conformed
  artifact as soon as the transcode runs for mp4 — the order needs no change, only the
  missing case.

## Goals / Non-Goals

**Goals:**
- An artifact's container is the container the request declared: frame, rate, length.
- The drift a composer introduces is visible on the asset instead of hidden by a crop or
  contradicted by the record.
- Add no new dependency, no new node, and no new request parameter.

**Non-Goals:**
- Making the composer author the right frame. The brief states it and the review may judge
  it; this change does not.
- Stretching or freezing a render to reach a declared length.
- Changing the registry, the form vocabulary, the engine, or the composer's brief.

## Decisions

### D1. Conformance lives in the runtime, after the render

The session owns the artifact and already owns the transcode, and it is the only place that
sees both the request's declared container and the engine's output. A workflow-side
conformance would need ffmpeg in n8n (there is none) and would move a rendering concern into
orchestration; the composer cannot be trusted to obey, which is the measurement this change
starts from.

*Alternatives considered:* a viewport flag on the engine — not available (no such flag, read
from `--help`); re-rendering at the declared size — the composition's frame is authored into
its markup, so a different viewport does not change it.

### D2. `mp4` loses its exemption, and conformance is skipped only when nothing differs

`transcodeArgs` returns arguments for `mp4` on the same terms as the other kinds, and the
session transcodes only when at least one of frame, rate or length differs from the
artifact's. A render that already matches is served untouched, so the common case pays no
second encode. (Reading the engine's actual output frame and duration means probing it —
`ffprobe` is already in the image and is what produces the stills.)

### D3. The frame is scaled, and an aspect mismatch is covered and reported

The declared viewport is the target: `scale=W:H:force_original_aspect_ratio=increase` then
`crop=W:H`, which fills the frame edge to edge. A mismatch is destructive by nature — run
13762's portrait HUD bands would be cut — so the note the runtime returns names both the
authored frame and the declared one, and the asset carries it. Cropping is chosen over
letterboxing because a declared frame means *filled*: every type here is full-bleed, and bars
in a feed read as a broken asset.

*Alternatives considered:* pad with bars — non-destructive but visibly wrong for a
full-bleed pattern; leave the artifact and flag it — the type's frame would not be delivered
at all.

### D4. The length is trimmed, never extended

`-t <durationSeconds>` when the render is longer. When it is shorter, the artifact is
delivered as it is and reported as short. Holding the last frame would produce the frozen
tail the animated-type rule forbids, and looping the clip would invent content the composer
did not author.

### D5. The rate keeps its derivation

`outputFps({ frames, durationSeconds, fps })` already answers the rate that makes the
declared frame count exact over the declared length, and it is what the GIF and WebP paths
use. The mp4 path takes the same value in its `fps` filter; the engine's `-f` is left at what
the brief tells the composer, because the derived value can be fractional and the flag
accepts only integers or rationals.

### D6. The stills follow the conformance

They already do (render → transcode → stills). The change keeps that order deliberately: the
review must judge the artifact the caller receives, not the engine's raw output.

### D7. The drift is data on the asset, and the declared values stop posing as measured ones

The runtime answers with the authored frame and duration beside the declared ones, and
`agent_result` carries it onto the asset. This is the fourth field the workflow reads off the
session's response (after the artifact URL, the report and the stills), so it adds no new
mechanism. The record's `WIDTH`/`HEIGHT`/`FRAME_COUNT`/`DURATION_MS` then describe the
*declared* container, which is true of the artifact by construction, and the note names the
exception when it is not.

### D8. A mismatch never fails the asset

The artifact is delivered, flagged and reviewable. A missing artifact is the separate case
the workflow already handles, and a conformance the runtime could not perform (no `ffprobe`,
an unreadable render) is reported like a review that could not run rather than failing the
run.

## Risks

- **The crop is lossy and the loss is real.** Run 13762's case would ship a 16:9 crop of a
  portrait composition: the field survives, the HUD panels are cut. That is why the note
  rides on the asset — the drift must be actionable, not merely recorded — and why the
  composer's frame drift is left as an open question below.
- **A second encode on the mismatching path costs time and a generation of quality.** Bounded
  by D2: no transcode when the container already matches.
- **Probing the engine's output adds a failure mode** (a malformed render, `ffprobe`
  timing out). D8 keeps it from failing the asset.
- **The workflow half needs a live apply**, so the platform is briefly in a state where the
  runtime reports the note and the record does not yet carry it. The note is additive, so
  that state is harmless; the tasks order the apply after the adapter is live.

## Open questions

- **Should the review judge the container too?** The critic's own prompt orders its findings
  geometry, then legibility, then brand — the frame a composition was authored at is not on
  the list, and it is the one defect this change can only mitigate. `[UNVERIFIED]` whether the
  critic's stills make an aspect mismatch obvious to it; the authoring brief already states
  the frame.
- **Would a responsive composition remove the need to crop?** A composition whose layout is
  full-bleed and whose type scales to the viewport would render correctly at any declared
  frame; run 13762's file hardcodes `width: 1080px`. If the engine gains a viewport flag, or
  the brief asks for a responsive root, this change becomes a backstop rather than the
  mechanism. `[UNVERIFIED]` for both.
- **How often the frame drifts is unmeasured.** Two runs were looked at: one missed the
  length by 0.5 s, one missed frame and length entirely. The note this change adds is the
  instrument that answers it over time.

## Definition of done

- `openspec validate --all` passes with this change present.
- `transcodeArgs` returns conformance arguments for `mp4`; the unit tests cover a matching
  container (no arguments), a width-only difference, an aspect mismatch (cover-crop), a
  longer render (trim), a shorter render (no extension), and the derived rate; and each test
  fails without the change.
- A session's response carries the authored and declared frames and the durations, and the
  stills are taken after the conformance.
- A live render of a known-off container (the `tiles_wide-13745` session, which authored
  1080×1350) is served at the declared frame, and `ffprobe` of the served artifact agrees
  with the declared values.
- The workflow edit is applied and read back: the asset carries the note, and the export
  matches live.
- Every `[UNVERIFIED]` above is either resolved or still marked as such.
