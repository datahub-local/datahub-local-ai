You are authoring a HyperFrames video composition, not answering in prose.

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

## How to work

1. Write `index.html`.
2. Run `hyperframes lint`.
3. Fix every error it reports. Run lint again until it reports **0 errors**.
4. Run `hyperframes render -o out.mp4 -f 30`.
5. Report what you produced: the file paths, and the duration and frame count that
   `ffprobe` gives for `out.mp4`.

If a step fails twice with the same error, report that error verbatim rather than
guessing again. Do not report success for a step you did not run.
