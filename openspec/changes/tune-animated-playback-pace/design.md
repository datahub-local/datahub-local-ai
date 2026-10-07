# Design

## Context

An animated asset is produced in two stages: `merge_assets` builds the markup with the
animation duration baked into the CSS (`animation-duration: var(--duration)`), and
`capture_frames` seeks every CSS animation to `i * duration / frames` and screenshots
it. `build_assemble` then writes the GIF delays from `duration / frames`. So the pace
is exactly `frames / duration`; doubling `duration` halves the perceived speed without
adding frames or bytes.

`frames` is bounded by the LinkedIn pixel cap: `36,152,320 / (1080 × 1350) ≈ 24.8`, so
24 frames is the ceiling at the type's declared 1080 px. `fps` in the registry only
feeds `FRAME_COUNT = min(frameCap, duration × fps / 1000)` and therefore saturates;
duration is the real control.

## Decisions

- **D1 — The type's duration wins over the spec's.** `duration = type.durationMs ||
  spec.motion.durationMs`, clamped. A type that must read calmly (LinkedIn) fixes its
  pace; a type with no declaration keeps following the authored spec. Precedence is
  type-first because the whole point is to take the pace away from a model that chose
  2–4 s.
- **D2 — One ceiling, shared with video: 20000 ms.** The animated clamps were an
  arbitrary 4000 ms; `build_video` already allows 20000 ms. Reuse that number rather
  than introduce a third value.
- **D3 — Widen the authored range to 2000–12000 ms.** Types without a declaration must
  still be able to be tuned, and 12 s is the 4× end of the requested range. The spec
  validator and the prompt move together.
- **D4 — No template change.** The per-block stagger (`step = duration/(blocks+1)`,
  each block animating over its remaining time) already spreads the motion across the
  full duration, so lengthening the duration produces a genuinely slower motion, not a
  static hold.

## Risks

- A long GIF is more likely to be skipped by a scrolling reader. 9 s is the 3× middle
  of the requested range; the type's `durationMs` is the single knob to revisit.
- `capture_frames` cost is the frame count, not the duration, so a longer render is not
  slower to produce.

## Open Questions

- Whether the other animated types (`diagram_animated`) should also declare a pace, or
  keep following the spec. Samples at 3/6/9/12 s will answer it.

## Definition of done

- `diagram_animated_linkedin` renders at 9000 ms from a spec that asks for 3000 ms.
- A type with no declared pace still follows the spec.
- The full offline suite passes and the live `Visual Studio` carries the change.
