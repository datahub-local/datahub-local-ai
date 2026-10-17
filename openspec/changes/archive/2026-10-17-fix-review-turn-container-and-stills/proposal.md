# Proposal

## Why

The studio's self-review loop (`openspec/changes/archive/2026-10-17-self-review-authored-artifact/`)
was verified live on 2026-10-17 and two defects came out of that run. Both are measured; neither
is visible from the export or from the tests that shipped with the loop.

**The fix turn re-declares the artifact's container.** A review turn's input is an *asset-shaped*
item — `prepare_stills` builds it from `agent_result`'s output, `parse_verdict` adds the verdict,
`review_feedback` passes it on — and that item carries none of `ASPECT`, `VIEWPORT`, `FRAMES`,
`DURATION_SECONDS` or `FPS`. `build_author_brief` therefore falls back to its own defaults
(`Number(a.VIEWPORT) || 1080`, `a.ASPECT || '4:5'`, `Number(a.FRAMES) || 24`,
`Math.round(declaredFrames / Math.max(1, Number(a.FPS) || 8))`) and the correction turn asks for
**1080×1350 / 3 s / 24 frames / 8 fps** whatever the type declares. Measured on run 13785, a
`tiles_wide` request (16:9, viewport 1280, 12 s, 360 frames, 30 fps):

| turn | declared container | engine render | asset says |
| --- | --- | --- | --- |
| 0 (first authoring, from the registry) | 1280×720 / 12 s / 360 / 30 | 1280×720, 12.5 s, 375 frames | `WIDTH 1280`, `HEIGHT 720`, `FRAME_COUNT 360`, `DURATION_MS 12000` |
| 1 (the critic's correction) | **1080×1350 / 3 s / 24 / 8** | 1080×1350, 3 s, 30 fps | `WIDTH 1080`, `HEIGHT 1350`, `FRAME_COUNT 24`, `DURATION_MS 3000` |
| 2 (second correction) | **1080×1350 / 3 s / 24 / 8** | 1080×1350, 3 s, 30 fps | same |

The composer authored what it was asked for, the conformance delivered it exactly (`CONFORMED:
"scale"`, the rate resampled 30 → 8), and the caller received a 4:5, three-second artifact for a
16:9, twelve-second type — the drift the previous change made *visible* and this one has to stop.
The critic compounded it: told by the degraded brief that 1080×1350 was declared, it named the
*corect* 16:9 composition as the defect and asked for it to be changed. This is also the true
cause of run 13762's 1080×1350 artifact, which the previous change's design attributed to "the
composer's frame is unenforced".

**The settled-frame still is silently stale.** `stillArgs` captures the settled frame with
`ffmpeg -sseof -0.1`, a seek shorter than one frame interval whenever the clip runs below 10 fps —
which is exactly what this pipeline produces, because the conformance derives the rate from the
declared frame count over the declared length (24 frames over 3 s is 8 fps). On such a clip the
command **exits 0 and writes no file**, so `makeStills` counts it among the stills it made and the
studio fetches `review-final.jpg` — which is still the *previous turn's* frame, served under the
same name. Measured on run 13785: turns 1 and 2 both reported four stills, `review-final.jpg`'s
mtime is turn 0's, and the critic's finding for both turns describes that 16:9 frame. The review
prompt tells the critic to judge geometry on the last still, so the stale frame is the one it
judges.

## What Changes

- The container a request declared reaches **every** turn of the review loop: the asset carries it
  (`ASPECT`, `VIEWPORT`, `FRAMES`, `DURATION_SECONDS`, and the rate), and `build_author_brief`
  refuses to invent one — a turn with no declared frame or length fails loudly and names the
  missing field instead of defaulting to 1080×1350 / 24 frames / 8 fps.
- A still is of the render it belongs to or it is not offered: the settled-frame capture seeks at
  least one frame interval, and a still that was not written this turn is neither reported nor
  served (the earlier turn's file is removed rather than left to stand in).

## Non-goals

- Not the conformance itself: `openspec/changes/conform-artifact-to-type-frame/` delivers the
  declared container faithfully, which is why the wrong declaration reached the caller.
- Not the composer's obedience, the critic's prompt, the registry, or the bound on the loop.
- Not a change to what a caller may ask for: a caller that names a frame still gets it.

## Capabilities

### Modified Capabilities

- `visual-studio`: a correction turn keeps the container the original request declared, and the
  review's evidence is a still of the turn that produced the artifact it is judging.
- `agent-authored-compositions`: the still of a settled frame is made at a seek the clip's own
  rate supports, and a still that could not be made is not reported as one.

## Impact

- **`agents/n8n/workflows/visual_studio.workflow.json`**: `agent_result` carries the declared
  container on the asset (it already carries the declared frame, count and duration);
  `build_author_brief` loses its silent container defaults for a missing declaration. Graph edit,
  so an export change is live only after `scripts/apply_workflow_changes.py`, guarded and read
  back — and the studio is published, so the apply is a `PUT` plus a `publish`.
- **`agents/adapters/pi-render/`**: `stillArgs` (the settled-frame seek) and `makeStills` (report
  only what was written), with the adapter's own tests; the image publishes through CI and the
  digest is pinned by the follow-up commit, as every adapter change here is.
- **Tests**: `agents/n8n/scripts/test_visual_studio_graph.py` for the container surviving the
  loop, and `agents/adapters/pi-render/test/` for the seek and for a still that was not made.
- **Sequencing**: the graph half must not be applied before the adapter half is live if the
  adapter's report changes shape; the container half is independent of the adapter.
