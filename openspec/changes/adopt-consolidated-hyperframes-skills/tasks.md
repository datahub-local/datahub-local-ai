# Tasks

Unstarted. PR datahub-local-ai#33 is deliberately untouched: this change is the work that makes
its engine bump mergeable. The Pi half of that PR is verified compatible (design gate findings)
and lands with the engine bump rather than as its own change, since one Renovate group moves them.

## 1. Pin and image

- [ ] 1.1 Keep the engine and the transition primitives on one release at or above `0.8.195`
  (`package.json` + `package-lock.json`) and move the Dockerfile's
  `@earendil-works/pi-coding-agent` pin to `1.4.0`. One release for engine + primitives is
  asserted by `dockerfile.test.mjs` and the skill fetch reads it from `package.json`; do not add a
  second `ARG HYPERFRAMES_VERSION`.
- [ ] 1.2 Replace the `Dockerfile`'s eight-skill assertion with the set the pinned tag ships and
  this adapter reads: `hyperframes`, `hyperframes-cli`, `hyperframes-registry` plus every
  `skills/hyperframes/references/*.md` and `references/types/*.md` the guide names. Keep the
  `missing skill in the image: <path>` failure and the `exit 1`.
- [ ] 1.3 Confirm the engine's own `dist/skills/hyperframes/SKILL.md` assertion still holds and
  that the fetch overlays the repository tree without dropping `references/`.

## 2. Guide (`prompts/authoring.md`)

- [ ] 2.1 Rewrite the skills paragraph against the consolidated layout: `hyperframes/SKILL.md`
  first (contract + work loop), `hyperframes-cli` for lint/render, `hyperframes-registry` before
  hand-authoring a named effect, and the specific `references/*.md` a brief's form needs. No
  method, no contract restatement, no review checklist — the guide stays sandbox facts.
- [ ] 2.2 State the two sandbox facts the new skill would otherwise contradict: this turn runs
  unattended and has no preview to approve, so it is not complete until `out.<ext>` exists; and
  the CLI is `hyperframes` on `PATH`, never `npx`.
- [ ] 2.3 Keep the existing `lint` → render → `check` order and the `-f 30 --low-memory-mode`
  invocation, and say why a `--resolution` preset does not replace the declared frame.

## 3. Drift test

- [ ] 3.1 In `test/dockerfile.test.mjs`, extract every skill and `references/` path named by
  `prompts/authoring.md` and assert each is inside the Dockerfile's asserted set. Prove it fails
  by adding a path the Dockerfile does not assert (e.g. `hyperframes-core/SKILL.md` — the exact
  drift this change exists for) and record the failure.
- [ ] 3.2 Replace the three hardcoded skill names in the existing assertion with the new set, and
  keep the pin-equality, `curl`-installed and skill-fetch assertions unchanged.

## 4. Documentation

- [ ] 4.1 `agents/adapters/pi-render/README.md`: the skill-set paragraph (which skills ship, which
  are fetched, and the retired `hyperframes-core`-not-bundled note) describes the release now
  pinned.
- [ ] 4.2 `agents/adapters/pi-render/README.md`: correct the "no viewport or size flag" claim —
  `render --help` at the pinned release lists `--resolution` presets, and the post-render
  conformance is still what reaches a type's declared frame.
- [ ] 4.3 `agents/render-samples/README.md`: the contract/motion skill names it tells a reader to
  read.
- [ ] 4.4 `AGENTS.md`: the `Visual Studio` passage's "full skill set at the pinned release" list and
  the `hyperframes render` size-flag sentence, both of which name the retired layout.

## 5. Verification

- [ ] 5.1 Build the image from a clean checkout (multi-arch target is not needed for this check;
  `docker build agents/adapters/pi-render` on this host is enough to exercise the fetch and the
  assertions), and record the resolved engine, Pi and skill tree
  (`ls /opt/hyperframes/skills`).
- [ ] 5.2 `node --test 'test/*.test.mjs'` in `agents/adapters/pi-render` — expect the same
  62 tests (1 skipped for absent ffmpeg) plus 3.1's test.
- [ ] 5.3 Author and render one asset of each family on the new image —
  `animation_linkedin_video`, `svg_wide`, `deck` — through `Visual Studio Test`, and confirm for
  each: the artifact exists at the declared key, `ffprobe` matches the type's declared frame, rate
  and duration (or is reported `SHORT`), the stills review ran and produced a verdict, and no
  `CONFORMED` note appears where the composer already matched. `[UNVERIFIED]` until run.
- [ ] 5.4 Judge the motion of 5.3's animated asset against
  `agents/n8n/prompts/visual_motion_rules.md` by eye, since the retired `hyperframes-animation`
  skill's rules now live in `references/motion.md` and this is the one claim no offline test
  covers. Record the verdict and any rule that the new skill fails to convey.
- [ ] 5.5 Confirm Pi 1.4.0 in the built image: `pi --help` still lists the seven flags the adapter
  passes, and a session started from a 1.2.0 transcript either resumes or fails loudly.
  `[UNVERIFIED]` for the transcript case — the session TTL is 7 days, so a stale transcript is the
  only way to meet it.
- [ ] 5.6 Publish through `publish-images` and confirm the adapter image is re-pinned in
  `agents/adapters/pi-render/deploy` and that the session Deployment rolls onto it.

## 6. Stopgap (only if the engine fix is needed sooner)

- [ ] 6.1 If a release before this change is needed, pin `hyperframes` and
  `@hyperframes/shader-transitions` at `0.8.184` — the last release carrying the 21-skill tree —
  and leave `prompts/authoring.md` and the Dockerfile's assertion untouched. Record here that this
  buys build compatibility only, and skip 6.1 once 1.1–1.2 land.
