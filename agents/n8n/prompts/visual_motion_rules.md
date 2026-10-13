# Motion rules

Craft rules for an authored composition. They apply to every scene; they are not a
checklist to report back.

- **Nothing fully stops.** A still final frame is the biggest tell an authored clip
  has. End on an ambient idle — a slow breathe, drift or sheen — rather than a hold.
- **Keep one continuous camera move underneath the scene** and never let it decay to a
  stop; a move that eases to zero reads as frozen.
- **Stagger entrances at offsets shorter than the animations they offset**, so an
  arrival reads as one overlapping wave instead of a queue.
- **Compound a property only when it tells one story** — position and scale moving one
  object. Do not stack unrelated changes on an element for their own sake.
- **Overshoot belongs on transforms, never on a number.** A counter settles on its
  value; a scale pop may pass it. Keep overshoot rare and playful, not the default.
- **Build depth from planes with a real foreground occlusion** — something in front of
  something else — not from size alone.
- **Match the pacing to the content.** A calm idea moves slowly; a punchy one snaps.
  Read the brief for the tone.
- **Seed imperfection where a handmade feel is wanted**, with an index-derived offset —
  never a clock and never unseeded randomness.

## Prove it

`check` verifies motion only when the composition ships a sidecar, so ship one:
`index.motion.json` beside the composition, matching its basename. Assert the intent —
`appearsBy` that each subject is on screen when its scene needs it, `staysInFrame` that
it stays there, `keepsMoving` that no shot freezes — then run `check` once after lint is
clean and fix every finding before you report. With no sidecar the motion audit does not
run, and `check` passes a clip whose subjects never reach the screen.

`staysInFrame` reads a box from the moment the element is half-opaque, so an entrance
that travels in from off-canvas must still be under that opacity while it is outside the
canvas.

Never put `data-layout-allow-overflow` on an element that clips its children
(`overflow: hidden`): the hatch silences the clipping findings for everything inside it,
which is how content that never renders passes the gate. Mark the travelling element, or
put the hatch on a wrapper that does not clip.
