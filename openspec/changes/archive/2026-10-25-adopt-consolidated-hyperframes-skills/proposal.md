# Proposal

## Why

Renovate's "pi-render toolchain" PR (datahub-local-ai#33) bumps `hyperframes` 0.8.158 → 0.8.195
and `@earendil-works/pi-coding-agent` 1.2.0 → 1.4.0. The Pi half is safe — every flag, settings
key and schema the adapter uses still exists in 1.4.0 — but the engine half cannot build, and
even if the build were relaxed the composer would lose its guide.

Upstream consolidated the authoring skills at **v0.8.185**. Measured on the release trees:

| Tag         | `skills/*/SKILL.md`                                                                |
| ----------- | ---------------------------------------------------------------------------------- |
| `v0.8.158`  | 21, including `hyperframes-core`, `-animation`, `-keyframes`, `-creative`, `-studio` |
| `v0.8.184`  | 21, the same set (last release that carries them)                                   |
| `v0.8.195`  | 7: `hyperframes`, `hyperframes-cli`, `hyperframes-registry`, `media-use`, `figma`, `slideshow`, `remotion-to-hyperframes` |

`v0.8.186`'s release notes ("Hide retired skills on ClawHub once the sync has run") date the
retirement; `raw.githubusercontent.com/.../v0.8.185/skills/hyperframes-core/SKILL.md` answers
`404` where `v0.8.184` answers `200`.

Three concrete consequences, each reproduced rather than inferred:

- **The image build fails.** `agents/adapters/pi-render/Dockerfile` fetches the skill tree at the
  pinned tag and asserts eight skills exist. Running that fetch and loop against the v0.8.195
  tag tarball prints `missing skill in the image:` for `hyperframes-core`, `-animation`,
  `-keyframes`, `-creative` and `-studio`, then exits 1. `test/dockerfile.test.mjs` only checks
  the names appear in *our* file, so `Test Agents` still passes and the failure lands in
  `publish-images`' adapter build after merge — where the image re-pin step never runs.
- **The composer's guide points at files that no longer exist.** `prompts/authoring.md` tells the
  composer to read `hyperframes-core/SKILL.md` for the contract and `hyperframes-animation` /
  `hyperframes-keyframes` for motion. At 0.8.195 those are gone; the replacement is one
  `skills/hyperframes/SKILL.md` (74 lines) plus `skills/hyperframes/references/*.md`
  (`motion.md`, `format.md`, `runtimes.md`, …).
- **The replacement skill contradicts this sandbox's job.** Its work loop ends: *"Render when the
  person approves the Studio preview, asks for the file or asks for no stops, after your check
  and review pass; otherwise stop at the preview and wait."* A composer turn exists to return an
  artifact; a turn that follows that line returns nothing and the caller sees a 404. It also
  invokes the CLI as `npx hyperframes`, where the image has `hyperframes` on `PATH` and no
  network at render time.

Nothing is updated by this proposal's own writing: PR 33 is left as it is. This change is the
work that makes the engine bump mergeable and keeps the image and the guide in step afterwards.

The first implementation asserted the paths that survive at the tag. The owner then asked
whether the adapter could depend on the engine binary instead of upstream's skill *files*, so the
image no longer fetches a repository tree at all: the contract comes from
`hyperframes docs <topic>`, which the installed package serves.

## What Changes

- **The contract comes from the engine binary, not a fetched skill tree.** The build drops the
  GitHub fetch, its `curl`, the tag extraction and the skill-path assertions, and instead asserts
  that the pinned release serves every docs topic the composer's guide names. Unknown topics exit
  non-zero, so a missing one fails the build naming it.
- **The guide is rewritten against the binary**: which `hyperframes docs` topics to read, the CLI
  as `hyperframes` (not `npx`), and an explicit statement that the turn always renders — the
  framework's interactive stop-at-preview loop does not apply inside this adapter.
- **A drift test ties the guide to the build.** The docs topics `prompts/authoring.md` names must
  be the ones the Dockerfile asserts, so a removed topic fails offline in `Test Agents` instead
  of at the composer's first read.
- **The documentation that states the old layout is corrected**: `agents/adapters/pi-render/README.md`
  (contract source, skill paragraph), `agents/render-samples/README.md`, and the two `AGENTS.md`
  passages naming the six skills and claiming the render has no size flag — `render --help` at
  0.8.195 lists `--resolution` presets, so that claim needs to say what is actually true (presets
  exist; arbitrary frames are still conformed after the render).
- **The Pi half rides along** (1.2.0 → 1.4.0) with the engine bump, since it is the same Renovate
  group and its compatibility is already checked — and the loop is run with skills and extensions
  discovery disabled, so no skill ecosystem can reintroduce a second contract behind the engine's
  docs.

## Capabilities

### Modified Capabilities

- `agent-authored-compositions`: the authoring image takes the framework's contract from the
  installed engine, the guide's named documentation is inside what the image ships, and a turn
  always produces a rendered artifact regardless of the framework's interactive preview gate.

## Impact

- `agents/adapters/pi-render/Dockerfile`: the fetch removed, a docs-topic assertion added, and the
  Pi pin moved to 1.4.0.
- `agents/adapters/pi-render/package.json` + `package-lock.json`: engine and transition primitives
  at the chosen release (Renovate's edit, kept).
- `agents/adapters/pi-render/prompts/authoring.md`: rewritten against the engine's own docs.
- `agents/adapters/pi-render/test/dockerfile.test.mjs`: asserts the guide↔image relationship
  instead of three hardcoded skill names.
- `agents/adapters/pi-render/README.md`, `agents/render-samples/README.md`, `AGENTS.md`: the
  documented layout and the render-flag claim.
- No workflow, prompt-brief, registry, brand or model change: the brief already carries the
  motion grammar from `agents/n8n/prompts/visual_motion_rules.md`.

## Non-Goals

- Working around the consolidation by re-creating the six skills ourselves. They are upstream's
  text; a local fork would be a second copy that drifts from the engine it describes.
- Pinning `hyperframes` at 0.8.184 forever. It is the last release with the old layout and is
  recorded in `design.md` as a stopgap only, if a fix is needed before this change lands.
- Adopting the skill's interaction model (storyboard stops, preview approval, the desktop app).
  The adapter is a one-turn headless author; `design.md` records why the loop is overridden rather
  than followed.
- Changing the composer's model, its retry window, or the studio's graph.
