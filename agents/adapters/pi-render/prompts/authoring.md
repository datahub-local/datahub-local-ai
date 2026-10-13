# Authoring a HyperFrames composition

You are authoring a HyperFrames video composition, not answering in prose. The brief
above is the work; this file is only a map of the sandbox you run in.

## What you have

- The brief names the working directory. Write the final composition (or the requested
  file) there, not a scratch copy: it is a volume and survives the run.
- `hyperframes` is on `PATH`. The framework's skills are at `/opt/hyperframes/skills/`
  — read `hyperframes/SKILL.md` first. `hyperframes-core/SKILL.md` carries the
  composition contract and `hyperframes-cli/SKILL.md` the lint and render commands;
  read `hyperframes-animation` and `hyperframes-keyframes` when the brief calls for the
  motion or effects they describe.
- A vendored GSAP is served beside the composition as `gsap.min.js`. Reference it as a
  sibling, `<script src="gsap.min.js"></script>`. Never reference a CDN: the render
  runs with no network, and a remote reference fails the render.
- There is no network at render time. No clocks and no unseeded randomness.

## How to work

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

   **Your turn must end in a render.** A run that spends its whole turn on layout probes
   and never renders is a failure, whatever else it produced.
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
