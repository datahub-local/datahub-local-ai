# Design

## Context

See [proposal.md](proposal.md) — Why. The facts that shape the approach, read from
the code, the image and the cluster:

- **The composer's guide is read first and wins.** `authoring.md` is the system
  prompt; the brief is the user turn. Where they disagree the guide is the method the
  agent follows, so our rules outrank the framework's skills whenever both are
  present. Today only the guide is present.
- **The npm dist is not the skill set.** `hyperframes`'s published package ships
  `dist/skills/` with three skills. Verified by listing
  `hyperframes-0.8.123.tgz` and `hyperframes-0.8.146.tgz`: in both, the only entries
  under `dist/skills/` are `hyperframes`, `hyperframes-cli`, `media-use`. The rest
  live in the repository's `skills/` directory and are installed by
  `npx skills add heygen-com/hyperframes`.
- **The engine's checks are the only automated gate.** `hyperframes lint` and
  `hyperframes check` run in the pod. The nine-point review was added because they do
  not catch a frame that is only partly filled or a clip that overruns its requested
  length. It is model-reported, not enforced.
- **`build_author_brief` drops `FEEDBACK`.** Read from the active version: the brief
  is built from `CONTENT`, the type's frame and a fixed set of lines; `req.FEEDBACK`
  is normalized but never concatenated.
- **The registry declares the frame.** `visual_types.json` carries `fps`, `frames`,
  `viewport`, `durationSeconds` and `holdSeconds`, and `build_author_brief` turns
  `holdSeconds` into the "end on a hold" instruction. `animation_linkedin` is
  `8 fps`, `48 frames`, `9 s`, `holdSeconds: 5`.
- **The publish node keys on the media, not the type.** `send_2_linkedin_omImage`
  picks its binary with `$('convert_animation').isExecuted ? … : $('convert_image')…`
  and declares `shareMediaCategory: IMAGE`. A video asset needs a different
  `shareMediaCategory` and a different upload handshake.
- **The session's egress is one rule in our chart** (the model namespace on 4000).
  Whether the controller also admits `{53,443,8080,9473}` is not established here —
  marked a gate below.

## Goals / Non-Goals

**Goals:**

- The brief is the deliverable; the composer's guide stops carrying method.
- The composer has, and uses, the framework's full authoring skill set and effects.
- A rejection reaches the composer on the next turn.
- Motion reads and does not freeze; the LinkedIn media can be a real video.
- A presentation is a first-class, if currently studio-only, output.

**Non-Goals:**

- Making authoring deterministic, cheap or fast. It remains one or more model runs.
- Authoring the composition ourselves, or handing it back as HTML we check.
- A new workflow that consumes a deck. The `deck` type is reachable from the
  webhook, the form and a sub-workflow call; no pipeline requests it yet.
- Replacing `hyperframes`'s own validation with our own. Removing our review is the
  point; adding a different harness would repeat the mistake.

## Gate findings

- **[UNVERIFIED] The `n8n-nodes-base.linkedIn` node accepts
  `shareMediaCategory: VIDEO` on this instance.** The installed node's parameter
  surface must be read before the publish path is written; if it does not support a
  video upload, the publish becomes a LinkedIn API call (`registerUpload` → `PUT` →
  post with the video URN). Probed in task 6.1, and the publish binding is chosen
  from the probe.
- **[UNVERIFIED] The session may reach `raw.githubusercontent.com` (443) at author
  time.** Our chart's egress policy admits only the model namespace on 4000; the
  controller's own policy may add more. Read the live policies (`kubectl get
  networkpolicy -n automation`) before relying on a registry install at author time.
  The design does not depend on it: shared primitives are vendored at build, and a
  registry block is used only when a probe shows the reach.
- **Verified by reading the image package: the npm dist ships three skills.** This is
  why the full set must be fetched, not `npm ci`'d.

## Decisions

### D1. The guide is sandbox facts; the brief is the work

`authoring.md` keeps only what the brief cannot state and the framework does not
know: the working directory, `hyperframes` on `PATH`, the skills location, the
vendored GSAP, "no network", "run the render in the foreground and wait", and "you
cannot see images, do not screenshot or measure the layout". Everything that
describes *how* to author is deleted — the contract restatement, the pacing numbers,
the review and the page indicator. What remains is a map of the sandbox.

*Alternatives considered:* keep the review but soften the numbers — rejected; a
softened checklist is the same drift with a longer tail. Move the review into the
brief — rejected; it would then be re-sent by every caller and reach no other
session. Put the review in the motion-rules file — rejected; the rules file is the
framework's craft, and our review is not craft.

### D2. The motion grammar is one committed file, appended to every brief

`agents/n8n/prompts/visual_motion_rules.md` holds the rules and is fetched by the
workflow the way `brand.json` is. `build_author_brief` appends it after the content
and the frame, so the brief is: source text, form and frame, then the method. One
copy; a change to the grammar is a prompt-file change, live on push.

*Alternatives considered:* inline it in `build_author_brief` — rejected, it would be
a copy inside a workflow export that only a live apply can change. Inline it in
`authoring.md` — rejected; it is per-brief craft and a direct successor to the
harness we are removing.

### D3. The image carries the repository's `skills/` tree at the pinned release

`docker build` fetches `skills/` from `heygen-com/hyperframes` at the release tag,
alongside the `npm ci` that pins the CLI. The build has network; the render does not.
A test asserts each expected skill's `SKILL.md` exists, so a layout change on the
registry fails the build rather than silently shipping three skills again.

*Alternatives considered:* `npx skills add` at author time — rejected as the
mechanism; it needs egress the pod may not have and would fail at run time.
Vendoring the skill files into this repository — rejected; it is the committed-copy
drift this repository warns about, for files that upstream revises often.

### D4. `FEEDBACK` is threaded and `EXTRA_PROMPT` is added

The brief gains the request's `FEEDBACK` verbatim under a heading that says it is a
reviewer's correction, and `normalize_input` accepts an optional `EXTRA_PROMPT`
appended last. Both are free text the caller owns; neither is parsed.

*Alternatives considered:* a `RULES` parameter naming a rules file — rejected; the
grammar is the committed file (D2) and a second, caller-named method file is a second
coping path for one need. A structured correction schema — rejected; the reviewer
writes prose today and a schema would have to be maintained with the prompt.

### D5. No budget may mandate a frozen frame

`holdSeconds` is dropped from the animated types, `build_author_brief` stops emitting
an "end on a hold" line, and the motion rules ask for an ambient idle in place of a
still final frame. A type may still declare a duration; it may not require the frame
to stop.

*Alternatives considered:* keep a short hold (0.5 s) — rejected; it preserves the
defect at a smaller scale, and "nothing fully stops" is the framework's rule, not a
threshold to tune. Let a caller ask for a hold through the brief — that is what
`EXTRA_PROMPT` is for.

### D6. The LinkedIn animated type becomes a video, and the publish chooses by type

A new type produces an MP4 at the feed's aspect (4:5), 30 fps, without a hold; the
existing GIF type stays for the deterministic path and for rows that must attach an
image. `LinkedIn Post Sharing` reads the asset's `CONTENT_TYPE` and sets
`shareMediaCategory` accordingly — `VIDEO` for `video/mp4`, `IMAGE` otherwise — on
the one publish node, keeping the "pick whichever conversion ran" shape it has.

*Alternatives considered:* repoint the existing `animation_linkedin` at MP4 —
rejected; the GIF cap type is the documented fallback and a caller may want it. Two
publish nodes — rejected; the existing node already selects its media by which
conversion ran.

### D7. A deck is one composer run that yields two artifacts

The registry gains `deck` (`render: deck`, `format: html`). The adapter serves
`out.html` and `out.mp4` from the same run; the workflow returns the deck as the
asset and the MP4 as a second asset in the same run, so asking for `deck` costs one
composer turn, not two. The deck is self-contained: one file, no external stylesheet,
script or network, so it opens anywhere.

*Alternatives considered:* a second type and a second composer turn for the MP4 —
rejected; it doubles the cost of the same plan. Return only HTML — rejected by the
user's choice of the paired artifact. Serve the deck from the session and return a
URL — rejected; the studio's contract is content, not a reference.

### D8. Effects come from the framework, not from us

With `hyperframes-registry` and `hyperframes-creative` present, a brief may name a
block, a VFX chain or a transition; the composer uses the vendored
shader-transitions primitives always, and installs a registry block only when the
reach probe passes. We do not curate a block list in this repository.

*Alternatives considered:* vendor a curated set of blocks — rejected; the catalog is
447 items and a committed subset is a copy that ages. Hard-code a transition list —
rejected for the same reason.

## Risks / Trade-offs

- **Deleting the review can let the two defects it caught return.** → Accepted and
  named. The engine's checks remain the gate; the motion brief asks for a filled
  frame and a total within the requested duration as craft rather than as a
  checklist; a caller can re-assert it through `EXTRA_PROMPT`. If a defect recurs
  often enough to matter, the fix is a post-render assertion in this repository, not
  a longer prompt.
- **A bigger skill set is a bigger context.** → The skills are read on demand
  (`SKILL.md` first, then one reference), and the deleted guide was itself consuming
  budget. The task list includes a run that measures the composer's turn length.
- **A build-time fetch adds a failure mode to the image.** → The tag is pinned and
  the test asserts each skill file; a fetch failure fails the build, which is loud.
- **A video publish changes the approval flow's subject.** → The reviewer still sees
  the media uploaded to Slack before the double approval, now as a video; the
  notification names the run and the content type, as it does today.
- **Two artifacts from one run complicate the asset contract.** → The contract stays
  "content per requested type"; `deck` is one requested type that yields its deck and
  its render. Stated in the spec delta so it is not read as a violation.
- **`@hyperframes/shader-transitions` is a new dependency in the image.** → Vendored
  at build from the pinned release; no author-time network.

## Migration Plan

1. Adapter image: fetch `skills/` at the pinned release and the shader-transitions
   package; assert the skill set; reduce `authoring.md` to sandbox facts. Rebuild and
   pin the digest.
2. Prompt file: add `visual_motion_rules.md` and push it (read from `main`).
3. Workflow: `EXTRA_PROMPT`, the rules fetch, the motion brief, `FEEDBACK` threaded,
   the deck fetch. Apply live with `--require-edge`, publish, re-read and diff.
4. Registry: the `deck` type and retuned budgets; push.
5. Publish: the content-type branch and the video upload; apply live with
   `--require-edge`, publish, re-read and diff.
6. Probe: session egress and the LinkedIn node's video support. Offline tests, then
   one live run of an animated row and one of a deck.

Rollback: set the new types `available: false` and repoint `ASSET_TYPES` at
`animation_linkedin` (GIF); the image and the guide revert with a digest pin.

## Open Questions

- Does the LinkedIn node's video upload handle the multi-step handshake, or does the
  publish become a raw API call? Answered by the probe (gate above), not by guessing.
- Should the composer's turn budget widen now that it carries more skill text? The
  run in task 6.4 measures it before the default changes.
