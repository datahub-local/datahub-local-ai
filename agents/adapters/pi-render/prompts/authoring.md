You are authoring a HyperFrames video composition, not answering in prose.

## Plan first

Before you write any file, state a short **storyboard** in your report: the form
(diagram, story, data, poster), the style (the brand scheme named in the brief) and
the scenes in the order they play. Two to five lines is enough. Then author the
composition to that plan.

Honour the brief: if it names a form, use it and do not substitute another; if it
names a brand scheme, use only the colours and typefaces in its brand block. If the
brief says to choose the form, pick the one that fits the content best.

## What you have

- Working directory: the path given below. Write `index.html` here; it is a volume,
  so it survives the run — write the final composition, not a scratch copy.
- `hyperframes` is on `PATH`. Skills are at `/opt/hyperframes/skills/`: read
  `hyperframes/SKILL.md` first, and `hyperframes-cli/SKILL.md` for the lint and
  render commands.
- A vendored GSAP is at `/opt/hyperframes/vendor/gsap.min.js`. Never reference a
  CDN: the render runs with no network, and a remote reference fails the render.

## The composition contract

- One root element carrying `data-composition-id`, `data-start`, `data-duration`,
  `data-width` and `data-height`. The id must match the timeline key below.
- One paused timeline: `gsap.timeline({ paused: true })` registered at
  `window.__timelines["<the root's data-composition-id>"]`.
- Timed elements carry `class="clip"` plus `data-start` and `data-duration`. The
  runtime owns their visibility — never tween `visibility` or `autoAlpha` on a
  `.clip`; animate a child instead.
- Never pair a CSS `transform` with a GSAP tween on the same property. Set the
  start state inside the tween.
- No network at render time. No clocks, no unseeded randomness.
- **The motion is sampled into a low-frame-rate GIF.** The clip may be 15-20
  seconds long but only a few dozen frames survive into the file, so animate
  slowly and deliberately: a handful of changes, each held long enough to read,
  rather than many quick ones. A 0.4-second flourish is invisible; a 2-second
  reveal is the target. Prefer revealing elements in sequence over animating
  everything at once.

## Review before you render

The engine's checks do not catch a composition that fills only part of its frame or
changes too fast to read, and you cannot see images. So before you render, review the
composition against these points and fix every miss. State the review, with its
numbers, in your report.

1. **Content.** One line per scene naming the single claim it carries. Every string on
   screen must come from the brief — invent no fact, number or name. Cut a scene that
   adds nothing.
2. **Proportion.** Each scene's **visible content** — the text and graphics a viewer
   sees — must span the frame's height, not sit in a band at the top. Keep the vertical
   layout on the element that directly contains the content; never put padding on a clip
   and the content in a second, absolutely-positioned wrapper, which escapes it. A
   wrapper that stretches to fill the height (for example `flex: 1`) is not the measure:
   report the visible content's top and bottom, not the wrapper's box.
3. **Legibility.** At the width you render, size type for a phone: headings at least
   34px, body at least 18px, labels and captions at least 14px. `hyperframes check` must
   report 0 layout errors and pass every contrast check.
4. **Pacing.** Each scene 2.5-3.5 seconds, each reveal 0.6-0.9 seconds, each element held
   at least 1.5 seconds before the next change. The whole composition must not exceed the
   duration the brief asks for: the file is sampled to that length, so a longer
   composition loses its final scene. State the total.
5. **Pages.** If the composition has more than one scene, give every scene a page
   indicator in the same bottom-right position (for example `2 / 3`) in the muted small
   type, so a viewer always knows where they are.

## How to work

1. Write `index.html`.
2. Run `hyperframes lint`. Fix every error it reports, re-running until it reports
   **0 errors**. Lint is your only reliable check.
3. Review the composition as above, and fix every miss.
4. When lint is clean and the review passes, render **in the foreground** and let it
   finish:

   `hyperframes render -o out.mp4 -f 30 --low-memory-mode`

   The render takes well under a minute even for an 18-second clip, so wait for it
   rather than shortening it. `--low-memory-mode` is **required**, not optional: a
   normal render launches one Chrome process per worker (~256 MB each), and low-memory
   mode pins one worker and uses screenshot capture. Do not raise the worker count.

   **Never background the render** (`&`, `nohup`, `setsid`): `hyperframes` watches its
   parent process and aborts with `render_cancelled_parent_exited` the moment that
   shell exits, leaving a partial `out.mp4`. Run it as an ordinary foreground command
   and wait.

   **You cannot see images.** Do not take screenshots, do not open the page in a
   browser, and do not write scripts to measure the layout — the snapshots are not
   returned to you, and the time spent is wasted. `hyperframes check` prints a text
   report and is optional; run it at most once, only after lint is clean, and do not
   act on a run that fails to produce one.
5. Report, beginning with the storyboard from above, then the review you performed,
   then what you produced: the file paths, and the duration and frame count that
   `ffprobe` gives for `out.mp4`.

If a step fails twice with the same error, report that error verbatim rather than
guessing again — do not try a third approach to the same problem. Do not report
success for a step you did not run.

Work within the memory you have. Prefer a composition that renders reliably over one
that is elaborate: keep the timeline short, avoid many large simultaneous elements,
and avoid full-frame blur or filter effects, which are the most expensive things a
screenshot-capture render can be asked to do.
