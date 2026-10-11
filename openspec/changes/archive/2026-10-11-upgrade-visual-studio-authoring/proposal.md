# Proposal

## Why

The composer's method is a harness we maintain, and it competes with the framework's
own knowledge instead of using it.

- `agents/adapters/pi-render/prompts/authoring.md` restates the HyperFrames
  composition contract (root attributes, one paused timeline, `.clip` timing,
  transform rules) and then adds a nine-point pre-render review with hard-coded
  numbers. `build_author_brief` in `visual_studio.workflow.json` repeats half of it.
  Two copies of one contract, and the one the agent reads first is ours.
- The harness mandates the motion the framework names as the cheap-motion tell: a
  final hold that stays still for at least five seconds, "a few clear beats, each
  held long enough to read", scenes of 2.5–3.5 s. HyperFrames' own guide says a
  frozen final second is the single biggest tell and that nothing should ever fully
  stop.
- The image ships three skills. `hyperframes@0.8.123`'s npm dist contains only
  `hyperframes`, `hyperframes-cli` and `media-use` (verified in the tarball; the
  same three in 0.8.146), so the composer has no access to `hyperframes-animation`
  (48 motion rules, 22 scene blueprints, 16 transitions), `hyperframes-keyframes`,
  `hyperframes-registry`, `hyperframes-creative` or `hyperframes-studio`. The
  framework's full power is not in the pod, and the core skill's own routing table
  points motion work at a skill that is absent.
- A reviewer's retry feedback never reaches the composer. `execute_visual_studio`
  passes `FEEDBACK`, `normalize_input` keeps it, and `build_author_brief` drops it:
  a rejected asset is re-authored from the same brief that failed.
- The only moving output is a frozen GIF — 8 fps, 48 frames, nine seconds with a
  five-second hold, so 55 % of the clip is still — and the studio cannot produce a
  presentation at all.

Our work is the **prompt**: the brief is the deliverable, and the composer executes
it with the framework's own skills, checks and effects. We do not hand-maintain a
parallel contract, a layout checklist or an HTML conformance review.

## What Changes

- **`authoring.md` becomes sandbox facts only.** Keep the working directory,
  `hyperframes` on `PATH`, the skills path, the vendored GSAP, "no network at
  render", "run the render in the foreground", "you cannot see images". Delete the
  restated composition contract, the nine-point review, the pacing numbers and the
  page-indicator rule. The framework's skills and its `lint`/`check` own method and
  validation.
- **The image carries the full skill set.** Pin `hyperframes` to a release and fetch
  the repository's `skills/` tree at that tag during `docker build`, so
  `hyperframes-animation`, `-keyframes`, `-registry`, `-creative`, `-studio` and
  `-core` are present. Vendor `@hyperframes/shader-transitions` at build too, since
  the render has no network.
- **The brief carries the motion grammar, once.** A new committed
  `agents/n8n/prompts/visual_motion_rules.md` holds the framework's motion rules;
  the workflow fetches it the way it fetches `brand.json` and appends it to the
  brief. It is not pasted into `authoring.md` and not into `build_author_brief`.
- **The caller can steer a re-author.** `build_author_brief` threads the request's
  `FEEDBACK`, and the trigger contract gains an optional `EXTRA_PROMPT` appended
  last, so a rejection or a one-off direction reaches the composer.
- **The budgets stop freezing the frame.** The five-second hold is dropped from
  `animation` and `animation_linkedin`, and the LinkedIn type's budget is retuned
  for motion rather than for a silent GIF.
- **Effects and registry blocks are available.** With `hyperframes-registry` and
  `hyperframes-creative` present and the shader-transitions package vendored, a
  brief may name a registry block, a VFX chain or a named transition; the composer
  installs a block only when the session can reach the registry, and otherwise uses
  the vendored primitives.
- **A `deck` type produces a presentation.** One composer run authors a
  self-contained HTML deck and renders it to MP4; the studio returns the deck as the
  asset and the MP4 alongside it.
- **LinkedIn publishes video.** `LinkedIn Post Sharing` uploads an MP4 as a video
  post when the asset's content type is `video/mp4`, and keeps the image path
  (`IMAGE`) for a `gif`/`png` asset. One publish node chooses by content type.

## Archive order

Archive **`add-hook-registry-and-visual-intent` first**, then this change. Both MODIFY
`visual-studio` → *Every trigger speaks one contract*, and a MODIFIED block replaces the
whole requirement: the hook change's block carries `SCENES` but not `EXTRA_PROMPT`, so
archiving it after this one would silently drop `EXTRA_PROMPT`. This change's block
carries the union (`SCENES` **and** `EXTRA_PROMPT`) and is safe to archive second.

This change also supersedes two landed pieces of that one, which must not be read as
lost work: its `holdSeconds` (a configurable final hold, its task 9.14) and its composer
review points 6–9 (task 10.1) are the harness this change removes — see tasks 1.1 and
5.3. Its task 10.3 (a composer handoff) is folded into task 1.2 here.

## Capabilities

### New Capabilities

- `visual-decks`: a source text can be authored as a navigable, self-contained HTML
  presentation, and the same run renders it to MP4.

### Modified Capabilities

- `visual-studio`: the registry gains a `deck` type; a type's budget may not mandate
  a frozen final frame; the trigger contract gains an optional extra prompt.
- `agent-authored-compositions`: the composer's guide states sandbox facts rather
  than a method; the image carries the framework's full skill set; the brief carries
  the motion grammar and the caller's feedback; the engine's own checks gate the
  render, not a bespoke checklist.
- `linkedin-post-publishing`: a video asset is published as a video post.

## Impact

- `agents/adapters/pi-render/prompts/authoring.md` — reduced to sandbox facts.
- `agents/adapters/pi-render/Dockerfile`, `package.json` — fetch the full skill set
  at the pinned release; vendor the shader-transitions package.
- `agents/adapters/pi-render/test/authoring-prompt.test.mjs` — assert the guide is
  facts-only and that the removed review does not come back.
- `agents/n8n/prompts/visual_motion_rules.md` — new, read from GitHub `main`.
- `agents/n8n/datasets/visual_types.json` — the `deck` type and retuned budgets.
- `agents/n8n/workflows/visual_studio.workflow.json` — `EXTRA_PROMPT` on the
  triggers, the rules fetch, the motion brief, `FEEDBACK` threaded, the deck fetch.
- `agents/n8n/workflows/linked_in_post_sharing.workflow.json` — the video publish
  path.
- `agents/sympozium/templates/pi-render-session.yaml` — an egress rule for HTTPS if
  the controller's policy does not already provide one.
- `agents/n8n/scripts/` — structural tests over the two exports and the registry.
- `AGENTS.md` — the Visual Studio section, which currently documents the review and
  the GIF budget as the design.
