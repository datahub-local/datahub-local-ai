# Design

## Context

`agents/adapters/pi-render` bakes HyperFrames and Pi into the authoring image. The engine pin in
`package.json` is the single source for both the installed package and the skill fetch in the
`Dockerfile`, which reads `.dependencies.hyperframes` and pulls
`codeload.github.com/heygen-com/hyperframes/tar.gz/refs/tags/v<that version>`. The composer's
guide, `prompts/authoring.md`, names the skill paths it should read inside `/opt/hyperframes/skills/`.

Upstream restructured that tree between v0.8.184 and v0.8.185. Everything below was measured on
2026-10-25 against the published release tarballs and the npm dist, not read off a changelog,
because the restructure is not announced in the release notes. The first implementation asserted
the paths that survive at the tag; the owner then chose the binary-only direction in D1, so the
tree is not fetched at all and the findings below are the evidence for that choice.

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
- **The binary carries the contract itself.** `hyperframes docs <topic>` serves it from the
  installed package: `compositions` (61 lines: root attributes, nested compositions, variables),
  `data-attributes` (29: timing, media, element visibility), `gsap` (26: timeline registration),
  `rendering`, `troubleshooting`, `examples`. An unknown topic exits 1
  (`Unknown topic: …`, followed by the available list), so a build step can assert the set.
  `hyperframes catalog` browses the registry; `lint`/`check --json` report findings with `Fix:`
  lines. The server already sets `HYPERFRAMES_SKIP_SKILLS=1`, which is what silences the CLI's
  "N skills out of date" notice on every other command.
- **The npm dist ships the entry skill and all its references** (`hyperframes`,
  `hyperframes-cli`, `media-use`, and `dist/skills/hyperframes/references/*`), so a
  package-only variant was available; it does not ship `hyperframes-registry`.
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
- The engine bump builds an image that depends on no upstream repository layout.
- The composer's guide names only documentation the installed binary serves, and cannot drift
  from it silently again.
- An authoring turn still returns a rendered artifact, whatever the framework's interactive
  work loop says.

**Non-Goals**
- Re-implementing the retired skills locally, or vendoring their text.
- Following the interactive loop (storyboard stops, preview approval, the desktop app).
- Changing the composer's model, brief, retry window, conformance or stills/review path.

## Decisions

### D1. The contract comes from the engine binary, not from a skill tree

The image installs the engine from `package.json` and nothing else. The composer is sent to
`hyperframes docs compositions|data-attributes|gsap|rendering` (and `troubleshooting` after a
failure), which the installed release serves. This removes the class of failure this change
exists for: a git tag's directory layout is upstream's to move — as v0.8.185 showed — while the
npm package is pinned in the lockfile and moves only when a bump is accepted, in the same PR
that changes the engine. It also deletes the build's `curl` fetch, the tag extraction and the
skill-path assertions.

Rejected, with their measurements: **fetching the repo tree** (what PR #33's bump broke on, and
what this change first implemented) keeps the richest prose but re-arms the same trap at the next
restructure; **shipping only the npm dist's skills** removes the fetch and keeps the prose but
still binds the guide to paths inside a package that is free to reorganise them, and this studio
uses none of the retired type/caption/film material.

The same rule is applied to the agent loop: `pi` is run with `--no-skills` and `--no-extensions`
beside the existing `--no-prompt-templates`, so discovery cannot introduce a second, unversioned
contract from the image, the run directory or `HOME`. Tools stay enabled — writing the
composition and running the engine is the job.

### D2. The build asserts the docs topics; the guide may name no others

`docker build` runs `hyperframes docs "$topic"` for every topic the guide names and fails naming
one the release does not serve (unknown topics exit 1). `test/dockerfile.test.mjs` reads both
files and fails offline if the guide names a topic the Dockerfile does not assert — the same
guide-to-image drift, now over a surface the engine owns. No copy of the topic list lives in a
third place.

### D3. Motion craft is the one thing the binary does not carry, and it is already ours

`agents/n8n/prompts/visual_motion_rules.md` is the committed motion grammar and is appended to
every brief, so the retired `hyperframes-animation` skill's job is covered without it. What is
not recovered is the per-kind `references/types/*.md` and the review/storyboard process — both
upstream's interactive method rather than this studio's, and the studio's own brief and critic
already own that path.

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

If a release were needed before this change lands, pin `hyperframes` and
`@hyperframes/shader-transitions` at 0.8.184 — the last release carrying all 21 skills — which
built unchanged under the fetched-tree design. It is recorded for the record, not adopted.

### D8. The SVG outputs are outside the engine's gate, and the guide says so

Measured 2026-10-25: `hyperframes lint` on a plain animated SVG reports three errors
(`data-width`/`data-height`, composition attributes, timeline registration), because the engine
validates HTML compositions only. The guide's blanket "lint → render → check" therefore
contradicted the SVG brief, and the first live `svg` turn resolved it by writing an HTML document
into `out.svg` (35,529 bytes starting `<!DOCTYPE html>`; the composer said the engine's static
guard required the wrapper). The guide now states the exception: for `out.svg`, author
well-formed SVG XML, write no `index.html`, and run no lint/render/check. `svg`/`svg_wide` are
the article's diagram formats, so dropping them is not an option; well-formedness is what the
offline side can check, and the composition's quality stays with the caller's critic.

## Risks

- **The binary's docs are shorter than the retired skills.** `docs compositions` (61 lines) plus
  `data-attributes` (29), `gsap` (26) and the `lint`/`check` gate are what the composer gets
  instead of the contract skill and its references; whether that is enough for a first-pass
  composition is measured by the per-type probe, not assumed.
- **`check` has grown.** Contrast verification is on by default at 0.8.195 and the finding set is
  larger than 0.8.158's. A composition that passed before may now fail its own gate; the guide
  already says to fix every error before rendering, so the risk is a longer authoring turn, not a
  wrong artifact.
- **The drift test only sees topic names.** Upstream can rewrite the content behind a topic
  without moving it, which no offline assertion can catch; the live authoring probe is the only
  cover.

## Open Questions

- Whether `hyperframes docs` coverage is enough without the retired motion skill. The brief still
  carries the committed motion grammar, so the open half is the composition mechanics (timeline
  registration, attributes), which `docs compositions` + `docs gsap` + `check` should cover —
  measured by the per-type probe (5.3/5.4).
- Whether the composer should also be given `hyperframes catalog` guidance for named effects.
  The guide names it; the vendored `@hyperframes/shader-transitions` remains the always-available
  surface, and the probe will show whether the composer reaches for it.

## Definition of Done

- `agents/adapters/pi-render` builds from a clean checkout at the pinned release, with no fetch
  from an upstream repository, and the build fails naming the topic when a guide-named docs topic
  is absent from the installed engine.
- `node --test 'test/*.test.mjs'` passes, including the guide↔build test, which fails if
  `authoring.md` names a docs topic the Dockerfile does not assert.
- One asset of each authored family is authored and rendered on the new image; each artifact's
  `ffprobe` frame, rate and duration match the declared container, the stills review runs, and the
  motion is judged by a person against the committed grammar.
- `README.md`, `agents/render-samples/README.md` and the two `AGENTS.md` passages describe the
  contract source and the CLI that the image actually has.
- Every claim that could not be measured is marked `[UNVERIFIED]` in `tasks.md`.
