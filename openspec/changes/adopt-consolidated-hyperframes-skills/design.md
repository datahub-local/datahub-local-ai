# Design

## Context

`agents/adapters/pi-render` bakes HyperFrames and Pi into the authoring image. The engine pin in
`package.json` is the single source for both the installed package and the skill fetch in the
`Dockerfile`, which reads `.dependencies.hyperframes` and pulls
`codeload.github.com/heygen-com/hyperframes/tar.gz/refs/tags/v<that version>`. The composer's
guide, `prompts/authoring.md`, names the skill paths it should read inside `/opt/hyperframes/skills/`.

Upstream restructured that tree between v0.8.184 and v0.8.185. Everything below was measured on
2026-10-25 against the published release tarballs and the npm dist, not read off a changelog,
because the restructure is not announced in the release notes.

## Gate findings

- **The six authoring skills are gone, not renamed.** `tar -tzf` of
  `v0.8.195/skills/*/SKILL.md` lists exactly seven: `hyperframes`, `hyperframes-cli`,
  `hyperframes-registry`, `media-use`, `figma`, `slideshow`, `remotion-to-hyperframes`.
  `v0.8.184` still lists all 21, including `hyperframes-core`, `-animation`, `-keyframes`,
  `-creative`, `-studio` and `-audio`. Raw `skills/hyperframes-core/SKILL.md` answers `200` at
  `v0.8.184` and `404` at `v0.8.185`, so 0.8.185 is the first release without them.
- **The consolidated `hyperframes` skill is one file plus references.** At v0.8.195 it is 74
  lines and points at `skills/hyperframes/references/*.md` — `motion.md`, `format.md`,
  `runtimes.md`, `story.md`, `spec.md`, `review.md`, `film.md`, `captions.md`, `overlays.md`,
  per-type files under `references/types/`, a `assets/frame-presets/` set and `scripts/`. The
  contract, the work loop and the per-kind requirements now live in that one skill.
- **The Dockerfile's build step fails at the new tag.** Replaying its own commands
  (`curl` the tag tarball, `tar --wildcards 'skills/*'`, `--transform`, then the `for skill` loop)
  prints `missing skill in the image:` for `hyperframes-core`, `hyperframes-animation`,
  `hyperframes-keyframes`, `hyperframes-creative`, `hyperframes-studio` and exits 1. The npm
  dist's own `dist/skills/` still ships `hyperframes`, `hyperframes-cli` and `media-use`, so the
  earlier `test -f .../skills/hyperframes/SKILL.md` assertion still passes — only the six-skill
  loop fires.
- **No gate catches it before merge.** `test/dockerfile.test.mjs` asserts that three skill names
  appear in the Dockerfile text and that the engine and primitives share a pin; it never looks at
  the upstream tree. CI's adapter job is `node --test 'test/*.test.mjs'` (62 tests, 61 pass, 1
  skipped for absent ffmpeg). The adapters build only runs in `publish-images.yaml`, on
  `workflow_run` after `Test Agents` on `main`, or on the weekly Thursday schedule.
- **The new skill tells the composer to stop before it renders.** Line 48: *"Render when the
  person approves the Studio preview, asks for the file or asks for no stops, after your check
  and review pass; otherwise stop at the preview and wait."* The skill also says to run the CLI as
  `npx hyperframes`. Both are written for an interactive desktop session; this adapter is a
  headless turn whose only output is `<run>/out.<ext>` and whose caller fails on a missing file.
- **The CLI surface this adapter uses is unchanged at 0.8.195.** `render -o`, `-f`, `--format`,
  `--low-memory-mode`, `--strict`, and `lint` / `check` (including `--json`, `--samples`,
  `--range`, `--at`) all still exist. New: `--resolution` with presets (`landscape`, `portrait`,
  `square`, `*-4k`). The presets are integer-multiple *scales of the composition*, so the
  post-render `ffprobe` conformance in `session-lib.mjs` remains the only way to reach an
  arbitrary declared frame; what changes is the documented claim that no size flag exists.
- **The lockfile churn from the bump is inert.** `sharp` becomes an optional dependency and is
  loaded lazily by `retryingSharpLoader` for Studio JPEG thumbnails only — the loader catches the
  failure, warns once, and disables thumbnails. `prettier` is removed and the dist contains only
  `// prettier-ignore` comments. Neither touches `render`, `lint` or `check`.
- **The Pi half of the bump is compatible.** Against `@earendil-works/pi-coding-agent@1.4.0`:
  `pi --help` still lists `--print`, `--no-prompt-templates`, `--provider`, `--model`,
  `--thinking`, `--session-id`, `--session-dir`; `schemas/settings.schema.json` still carries
  `retry.maxRetries`, `retry.baseDelayMs`, `retry.maxAgentDelayMs` and the top-level
  `httpIdleTimeoutMs` the adapter writes; `schemas/models.schema.json` is still
  `{providers}`, so the generated provider/model block validates; `engines` moved to
  `node >=22.19.0`, satisfied by the floating `node:22-bookworm-slim` base. The 1.3.0/1.4.0
  changelogs list no breaking change affecting any of the above.

## Goals / Non-Goals

**Goals**
- The engine bump builds an image whose skill set is what upstream ships at that release.
- The composer's guide names only paths that image actually contains, and cannot drift from it
  silently again.
- An authoring turn still returns a rendered artifact, whatever the framework's interactive
  work loop says.

**Non-Goals**
- Re-implementing the retired skills locally, or vendoring their text.
- Following the interactive loop (storyboard stops, preview approval, the desktop app).
- Changing the composer's model, brief, retry window, conformance or stills/review path.

## Decisions

### D1. Follow the consolidation; do not fork the retired skills

The six skills were upstream's text about upstream's engine. Copying them into this repository
would freeze guidance that no longer matches 0.8.195 and would be a second copy with no owner.
The composer's committed motion grammar is already `agents/n8n/prompts/visual_motion_rules.md`,
carried in the brief, so the essential rules survive a thinner skill tree.

### D2. The image asserts what the tag ships, and keeps failing loudly

The `Dockerfile`'s expected set becomes the skills the guide actually uses — at minimum
`hyperframes` (entry, contract, work loop), `hyperframes-cli` (lint/render), and
`hyperframes-registry` (effects before hand-authoring) — plus the reference files the guide names
(e.g. `skills/hyperframes/references/motion.md`, `format.md`, `runtimes.md`). The loop and its
`exit 1` stay: an upstream restructure must still stop the build, and the failure must name the
missing path rather than ship a subset.

### D3. A drift test ties the guide to the image

`test/dockerfile.test.mjs` reads `prompts/authoring.md`, extracts every `hyperframes*` skill path
and `references/*.md` it names, and asserts each appears in the Dockerfile's asserted set. The
defect this change exists for is exactly that pair drifting, and the test runs in
`Test Agents` — offline, before `publish-images`. Keep the existing pin-equality and
skill-fetch assertions.

### D4. The guide overrides the framework's preview gate

`prompts/authoring.md` gains one sandbox fact, not a method: this turn runs unattended, the caller
has no preview to approve, and the turn is not complete until `out.<ext>` exists — the
framework's "stop at the preview and wait" applies to an interactive session and not here. That is
the class of statement the capability's spec allows the guide to carry ("facts about its sandbox …
how to run the render"); the composition contract and the motion method stay in the framework.

### D5. The CLI is called as `hyperframes`, not `npx hyperframes`

The image symlinks the binary to `/usr/local/bin/hyperframes` and the render runs with no network.
`npx` resolves the PATH binary today but falls back to a registry fetch when it cannot, which is a
failure mode with no upside here. The guide's existing command lines already say `hyperframes`;
the change keeps them and records why in the guide's sandbox facts.

### D6. The `--resolution` presets do not replace conformance

A type declares an arbitrary frame (`1280×720` for `tiles_wide`, `1080×1350` for the feed). The
presets are fixed ratios at an integer multiple of the composition, so using one would still have
to be conformed to the declared container. The `ffprobe`-then-`ffmpeg` step in `session-lib.mjs`
stays exactly as it is; the change only corrects the documentation that says no size flag exists
at all.

### D7. 0.8.184 is the stopgap, not the destination

If the engine needs a fix before this change lands, pin `hyperframes` and
`@hyperframes/shader-transitions` at 0.8.184 — the last release with all 21 skills — which
builds unchanged. It buys nothing the composer is waiting for, and any later bump meets the same
wall, so it is recorded here rather than adopted.

## Risks

- **A thinner skill tree is a quality risk, not just a path change.** The retired
  `hyperframes-animation` carried the atomic motion rules and scene blueprints as a skill; at
  0.8.195 those live in `references/motion.md` and in the brief's committed grammar. Whether the
  composer still produces comparable motion is unmeasured until an asset is authored on the new
  image — a task, not an assumption.
- **`check` has grown.** Contrast verification is on by default at 0.8.195 and the finding set is
  larger than 0.8.158's. A composition that passed before may now fail its own gate; the guide
  already says to fix every error before rendering, so the risk is a longer authoring turn, not a
  wrong artifact.
- **The drift test only sees names.** Upstream can rewrite `references/motion.md` without moving
  it, which no offline assertion can catch; the live authoring probe is the only cover.

## Open Questions

- Whether the consolidated skill's references cover the forms this studio authors (`diagram`,
  `story`, `data`, `poster`, `ui`, `manga`, `tiles`), or whether the brief's `FORM` vocabulary now
  needs a pointer to the matching `references/` file. Resolved by reading the tag's references
  during implementation, and recorded there.
- Whether to pass `--skill <path>` to Pi so the composer need not resolve paths itself. Not
  proposed here: the guide's file reads work today, and Pi (1.4.0) has no reason to change.

## Definition of Done

- `agents/adapters/pi-render` builds from a clean checkout at the pinned release, and the build
  fails naming the path when a guide-named skill is absent.
- `node --test 'test/*.test.mjs'` passes, including the new guide↔image test, which fails if
  `authoring.md` names a path outside the asserted set.
- One asset of each authored family (`animation_linkedin_video`, `svg_wide`, `deck`) is authored
  and rendered on the new image; each artifact's `ffprobe` frame, rate and duration match the
  declared container, the stills review runs, and the motion is judged by a person against the
  committed grammar.
- `README.md`, `agents/render-samples/README.md` and the two `AGENTS.md` passages describe the
  layout and the CLI that the image actually has.
- Every claim that could not be measured is marked `[UNVERIFIED]` in `tasks.md`.
