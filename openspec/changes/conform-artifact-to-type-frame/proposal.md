# Proposal

## Why

A type declares a frame, a rate and a length; the artifact a caller receives has none of
them enforced. Measured on run 13762 (2026-10-17), a request for `tiles_wide` — 16:9,
viewport 1280, 12 s, 360 frames — returned an artifact that `ffprobe` reads as
**1080×1350, 30 fps, 90 frames, 3.000 s**: a portrait, three-second clip. The composition's
own markup says so (`data-width="1080" data-height="1350" data-duration="3"`). The previous
run for the same type (13745) missed the length by 0.5 s (12.5 s against a declared 12 s).

The record the caller sees does not reveal it either: `agent_result` builds `WIDTH`,
`HEIGHT`, `FRAME_COUNT` and `DURATION_MS` from the *request's* values, so execution 13762's
asset row claims `1280 × 720`, `360` frames and `DURATION_MS 12000` while the stored file is
1080×1350, 90 frames, 3 s. A consumer that reads the record instead of the bytes describes
the asset wrongly, and nothing anywhere compares the two.

The runtime already knows how to conform an artifact — `transcodeArgs` derives the output
rate from the declared frame count and length, scales to the declared width, and trims to
the declared duration — **except for `mp4`, where it returns `null`** ("no transcode is
needed"). `tiles_wide` is mp4, so the one path that skips conformance is the path every
video type uses; the GIF and WebP types are conformed and the MP4 types are not.

## What Changes

- Conform the engine's render to the declared container for every output kind, mp4
  included: the declared frame, the declared rate (so the declared frame count is exact),
  and the declared length.
- Set the frame by scaling, covering the declared frame and cropping the overflow when the
  authored aspect differs, and report the authored frame alongside the declared one so a
  composer that authored the wrong shape is visible rather than silently cropped.
- Never extend a render to reach a declared length: a frozen tail is the cheap-motion tell
  the composition rules forbid. A short render is trimmed-eligible only in the other
  direction and is reported as short.
- Take the stills the review looks at from the conformed artifact, so the review judges
  what the caller receives.
- Carry the conformance note onto the asset, so the run record stops asserting the declared
  frame as if it were the artifact's.

## Capabilities

### New Capabilities

<!-- None. -->

### Modified Capabilities

- `agent-authored-compositions`: the artifact contract gains the container — frame, rate,
  length — the runtime must deliver, and the duty to report a render that did not match it.
- `visual-studio`: an asset carries what the runtime actually produced, so the declared
  container is only asserted once it is the artifact's.

## Impact

- **`agents/adapters/pi-render/`**: `session-lib.mjs` (the conformance arguments, pure and
  unit-testable without a server), `session-server.mjs` (run it after the render and before
  the stills, and report it), `test/session-lib.test.mjs`, `test/session-server.test.mjs`.
- **`agents/n8n/workflows/visual_studio.workflow.json`**: `agent_result` carries the note.
  An export edit is the backup's output, so this half is live only once applied with
  `scripts/apply_workflow_changes.py`, guarded and read back.
- **No change** to the composer's brief, the engine, the registry or the form vocabulary,
  and no attempt to stop a composer authoring the wrong frame — the pipeline delivers the
  declared container and reports the drift instead.
- **Sequencing**: `agents/adapters/pi-render/session-lib.mjs` and `session-server.mjs` were
  being edited by another change (`self-review-authored-artifact`, commit `21ea231`) when
  this was written, so the code lands after that work settles rather than as a second writer
  in the same file.
