# Authoring a HyperFrames composition

You are authoring a HyperFrames video composition, not answering in prose. The brief
above is the work; this file is only a map of the sandbox you run in.

## What you have

- The brief names the working directory. Write the final composition (or the requested
  file) there, not a scratch copy: it is a volume and survives the run.
- `hyperframes` is on `PATH`. Run `hyperframes render`, never `npx hyperframes`: there is
  no package registry at render time. The engine documents its own contract, and that
  documentation is the authority: read `hyperframes docs compositions` (composition
  structure, nested scenes, variables) and `hyperframes docs data-attributes` (timing,
  media, element visibility) before you author, and `hyperframes docs gsap` for the
  timeline contract. `hyperframes docs troubleshooting` when a render fails, and
  `hyperframes catalog` if the brief names a ready-made block or effect.
- This turn runs unattended and the caller receives a file, not a preview. The framework's
  authoring guidance ends its loop at a preview approval ("otherwise stop at the preview and
  wait"); that step does not exist here, so the render below happens in this turn and the turn
  is not complete until the output file exists.
- The composition's own `data-width`/`data-height` is the frame the video is delivered at, so
  write the frame the brief declares. `--resolution` only picks a preset that is an integer
  multiple of the composition, and a frame that still differs is conformed after the render.
- A vendored GSAP is served beside the composition as `gsap.min.js`. Reference it as a
  sibling, `<script src="gsap.min.js"></script>`. Never reference a CDN: the render
  runs with no network, and a remote reference fails the render.
- There is no network at render time. No clocks and no unseeded randomness.

## How to work

0. When the brief asks for `out.svg`, the engine's gate does not apply: `hyperframes lint`
   and `check` validate HTML compositions, and a standalone SVG fails them by design (no
   composition attributes, no timeline registration). Author well-formed SVG XML directly,
   write no `index.html`, run no `lint`, `render` or `check`, and keep every animated element
   ending visible. Steps 1-4 below are for a rendered composition.
1. Run `hyperframes lint` and fix every error it reports, re-running until it is clean.
2. Render in the **foreground** and let it finish:

   `hyperframes render -o out.mp4 -f 30 --low-memory-mode`

   The render takes well under a minute even for an 18-second clip, so wait rather than
   shortening it. `--low-memory-mode` is **required**, not optional: a normal render
   launches one Chrome process per worker (~256 MB each), and low-memory mode pins one
   worker and uses screenshot capture. Do not raise the worker count.

   **Never background the render** (`&`, `nohup`, `setsid`): `hyperframes` watches its
   parent process and aborts with `render_cancelled_parent_exited` the moment that shell
   exits, leaving a partial `out.mp4`. Run it as an ordinary foreground command and wait.

   **A rendered turn must end in a render.** A run that spends its whole turn on layout
   probes and never renders is a failure, whatever else it produced.
3. Write the `*.motion.json` sidecar the brief asks for, then run `hyperframes check` and
   fix every finding it reports. It launches its own Chrome, so run it once, not per
   revision, and never with `--samples`. A check that could not run says so — report
   that, not a pass.
4. Report what you produced: the file paths, and the duration and frame count that
   `ffprobe` gives for `out.mp4`.

**You cannot see images.** Do not take screenshots, do not open the page in a browser,
and do not write scripts to measure or inspect the layout — the snapshots are not
returned to you, and the time spent is wasted. The `*.motion.json` sidecar is a
declaration, not a probe: write it, and `check` reads it.

Work within the memory you have. Prefer a composition that renders reliably over an
elaborate one: keep the timeline short, avoid many large simultaneous elements, and
avoid full-frame blur or filter effects, which are the most expensive things a
screenshot-capture render can be asked to do.

If a step fails twice with the same error, report that error verbatim rather than
guessing again — do not try a third approach to the same problem. Do not report success
for a step you did not run.
