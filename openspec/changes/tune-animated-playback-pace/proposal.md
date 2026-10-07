# Proposal

## Why

The LinkedIn animated media published by `LinkedIn Post Sharing` plays too fast to
read. The GIF shows 24 frames over the duration the authoring model chose in the
content spec (`motion.durationMs`, 2000–4000 ms) → 6–12 fps, and no surface owns the
pace: the type registry cannot set it, and the animated path caps duration at 4000 ms
(`merge_assets`, `capture_frames`, `build_assemble`), so a caller cannot ask for a
longer, slower loop. The last post (`diagram_animated_linkedin`) was reported hard to
follow at screen size.

The video path already allows up to 20 s (`build_video`); the animated path never got
the same ceiling. 24 frames is the maximum at 1080×1350 (the LinkedIn pixel cap), so
the only levers are the total duration and the frame size — and a longer duration adds
no frames and no bytes, just more time between them.

## What Changes

- Give an animated type an optional declared **`durationMs`** that sets its playback
  pace, independent of the authored spec.
- Raise the animated duration ceiling from 4000 ms to 20000 ms (matching the video
  path) in `merge_assets`, `capture_frames` and `build_assemble`, and widen the
  authored `motion.durationMs` range to 2000–12000 ms for types with no declaration.
- Set `diagram_animated_linkedin` to **9000 ms** (3× slower, ~2.7 fps).

Out of scope: any change to the composition's motion design (the per-block stagger
already spans the full duration), and the frame count (fixed by the platform cap).

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `visual-studio`: an animated type may declare its playback pace, and the animated
  duration ceiling is raised to the video path's.

## Impact

- `agents/n8n/workflows/visual_studio.workflow.json` — `parse_registry` carries the
  type's declared pace, `merge_assets` applies it, and three duration clamps are
  raised.
- `agents/n8n/datasets/visual_types.json` — `diagram_animated_linkedin` gains
  `durationMs: 9000`.
- `agents/n8n/prompts/visual_spec.md` — the authored `motion.durationMs` range.
- Tests and a live apply of `Visual Studio` with `--require-edge` guards.

## Archive order

Archive after `add-linkedin-animated-post-media` and `add-hyperframes-render-service`,
whose deltas this change builds on.
