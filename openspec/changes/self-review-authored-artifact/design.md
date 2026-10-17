# Design

## Context

Two halves, because the bytes live in two places and the repo has already decided that
they must not move.

- **An agent-authored asset's bytes are in the session pod.** The composer renders in
  `runs/<session_id>/` and the studio's `store_artifact` uploads them to Garage from the
  session's own HTTP route, so the studio's graph carries no bytes at all (measured: a
  9,326,134-byte asset recorded as a 13 kB payload holding its key). A critique therefore
  happens where the artifact already is — in the adapter, inside the authoring request.
- **A raster's bytes are made inside n8n.** The Gemini image comes back as a data URL in
  the studio's own execution (measured 2,330 kB for one 1080x1350 PNG), because no store
  can fetch bytes that n8n created. Sending that data URL to a vision model adds no new
  class of traffic, so the raster half of the loop lives in the graph.

## Gate findings

Reconciled against the running system on 2026-10-17.

- **The gateway serves vision.** `supports_vision: true` is declared on
  `opencode-go/deepseek-v4.1-flash`, `glm-5.3-flash`, `kimi-k3`, `qwen3.8-flash` and
  `qwen3.8-max` in the applied `datahub-local-core-data-litellm-config`, and it is real
  rather than declared: a `chat/completions` call carrying a 2x2 red PNG as a data URL
  answered `"Red"` from both `opencode-go/deepseek-v4.1-flash` and
  `opencode-go/glm-5.3-flash`, probed from inside the session pod with its own
  `OPENAI_API_KEY`.
- **The session pod can make a still of anything it authors.** `/usr/bin/chromium` and
  `/usr/bin/ffmpeg` are both present; there is no `rsvg-convert`, `inkscape` or ImageMagick,
  so Chromium is the rasteriser for an SVG and for an HTML deck.
- **The composer writes no `index.html` for the `svg` type** ("Do not render and do not
  write index.html"), so a still for an SVG is made from `out.svg` itself rather than from
  a composition, and the mp4/GIF/webp types are sampled from their own artifact.
- **A sub-workflow's response is its last node's last run**, so a caller cannot receive two
  branches' items from one call (measured the same day: the studio authored two assets and
  the caller received one). The review is a step *inside* the producing half, never a second
  caller-side pass, so this does not arise.

## Goals / Non-Goals

**Goals:**
- An artifact is looked at before a human is asked to look at it.
- The correction is authored by the thing that owns the composition, in the same thread,
  so a fix is an edit rather than a new take.
- The loop is bounded and its findings are recorded.

**Non-Goals:**
- A second opinion on the *human's* verdict, or a replacement for it.
- Judging an artifact against anything but its own declared contract (frame, form, brand)
  and the brief's intent. A critic that invents requirements is a source of churn.
- Making the composer's authoring brief carry images.

## Decisions

### D1. The workflow orchestrates; the session renders and serves stills

The critic is a node in `Visual Studio`: `prepare_stills` → `fetch_still` → `encode_stills` →
`critique` (an `httpRequest` to the gateway's `chat/completions`, reusing the credential
`generate_image` already uses, with `opencode-go/glm-5.3-flash` — a different model from the
composer's) → `parse_verdict`. The session's only addition is the stills it renders and serves,
because the artifact is there and the tools are already its dependencies (Chromium for a
document, `ffmpeg` for a clip, both of which the render already uses).

This is a correction of the first shape, and the correction is the point: an API call inside
the adapter puts a model dependency and a critic's opinion inside the agent that authors. The
agent renders and reports what it rendered; deciding whether that is good is orchestration.

*Alternatives considered:* the critic call inside the adapter (built first, then rejected by
the owner); the composer reviewing its own render — rejected as the weakest possible critic, an
author re-reads its intent rather than its pixels; a critic that both judges and fixes —
rejected, one call but the judgement and the edit collapse into one model's opinion; passing the
gateway a URL instead of the bytes — not available, the session's route is not reachable from
the gateway's namespace, so the stills' bytes (a few hundred kB, not the multi-MB artifact) are
the one thing the review adds to the graph.

### D2. The critic's verdict is data, and an unreadable verdict ships

The call asks for a JSON object: `{"verdict": "ok" | "fix", "findings": [{"where", "what",
"fix"}]}`. It is parsed tolerantly, and anything unparseable is treated as `ok` with the raw
text recorded. The alternative — treating an unparseable verdict as "keep fixing" — turns a
model that cannot hold the format into a loop that never ends.

### D3. Two cycles, and the budget is a setting

`PI_RENDER_REVIEW_CYCLES` (default `2`) bounds the extra authoring turns per request. A
cycle is: critique → fix turn → re-render → critique. The last critique's findings are
recorded whether or not they were fixed, so a shipped-with-findings artifact says so.

### D4. The still is chosen per medium, and the final frame is always one of them

- `svg`, `svg_wide`: Chromium screenshot of `out.svg` at the declared frame.
- `deck`: Chromium screenshot of `out.html` (and the paired `out.mp4`'s frames are the
  motion the deck's video half will be judged on, so the deck's own frames are enough).
- `animation*`, `tiles*` (mp4/gif/webp): `ffmpeg` frames at evenly spaced offsets **plus
  the final frame**, because "nothing fully stops" makes the last frame the one a frozen
  clip hides in.
- `launch_card` (a still png the composer rendered): the artifact itself.

A critique of one still cannot judge motion; the framework's `check` gate owns that
(motion sidecar, `keepsMoving`). The critic judges what a still shows: geometry, legibility,
overlap, frame fit, brand use, and whether the subject reads.

### D5. The review prompts are fetched, not baked

`prompts/visual_review_composition.md` and `prompts/visual_review_raster.md` are committed
files the studio fetches from GitHub `main` (the `visual_motion_rules.md` idiom) and carries
in the request body. The adapter's own `prompts/authoring.md` is baked into the image
because it is sandbox facts that change with the sandbox; a review grammar changes with
taste, so it must be a prompt push.

*Alternatives considered:* baking the review prompt into the adapter image — rejected, a
taste change would need an image rebuild; letting the adapter fetch it — rejected, the
session's brief is prose the caller supplies and the adapter reads no prompts over the
network.

### D6. The raster half is the same loop, without stills

After `raster_result`, the PNG's data URL goes to the critic; on findings the findings are
appended to the image director's input and the image is regenerated, up to the same budget.
The alternative — routing a raster through the session — rejected: the session authors
compositions, and a raster has no composition to edit.

## Risks

- **A longer turn.** Two cycles is roughly twice today's authoring time (386 s measured for
  one asset with one type). The callers' `executionTimeout` is 3600 s; the studio's own bound
  is re-measured in the verification task rather than assumed.
- **A critic that invents requirements.** Bounded by the prompt naming what it may judge
  (the declared frame, the form, the brand, the brief's intent) and by the budget.
- **A fix that breaks what was right.** Each cycle re-critiques the whole still, so a
  regression is caught by the next cycle rather than shipped; the last cycle's findings are
  recorded, so a regression that survives is visible on the asset.
- **Cost.** One vision call per cycle per asset, plus the extra authoring turn.

## Open questions

- **Whether a critique improves the acceptance rate is unmeasured.** The verification task
  records the findings for one live asset and whether the human approves it, but a rate needs
  a sample rather than a run.
- **Whether `glm-5.3-flash` is a good critic** is unmeasured: it is chosen for being a
  different model that serves vision, not because its judgement has been compared with a
  human's. The model is a setting (`PI_RENDER_REVIEW_MODEL`, and the studio's own model
  parameter) so it can be changed without a code change.

## Definition of Done

- The adapter's loop is asserted offline: the sampling arguments per medium, the critic
  request's shape, the tolerant verdict parse, and the cycle bound — each failing without
  its change.
- The raster loop is asserted offline in the studio's own tests, and both graph copies carry
  it.
- A live authoring turn with a deliberately broken composition produces a critique, a fix
  turn, and a second render that no longer shows the defect; the findings are recorded on
  the asset.
- The turn's length with two cycles is measured, not assumed.
- `openspec validate --all` passes with this change present.
