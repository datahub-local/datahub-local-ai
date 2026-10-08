# Proposal

## Why

The composer (`agents/adapters/pi-render/`) gates a composition with the engine's own
checks (`hyperframes lint` / `check`) before rendering. Those checks catch runtime,
overflow, overlap and contrast faults, but they do **not** catch a composition that
fills only part of its frame or changes too fast for a viewer to read. The composer
also cannot see images, so it cannot look at its own output.

A live acceptance run on 2026-10-08 (`LinkedIn Post Sharing`, row 49, `POST_MEDIA=AGENT`)
took **three** composer turns to become acceptable, and every miss passed the engine's
checks:

- **Attempt 1** — studio run `12622`: scene content sat in the top ~40 % of the
  776×970 frame with the bottom ~60 % empty. The vertical padding/centering was on the
  outer `#s1`/`#s2` element while the content lived in an absolutely-positioned inner
  `.scene`, which escaped it. In-scene motion also read too fast. `check` reported
  `0 layout errors`.
- **Attempt 2** — studio run `12625`: the same proportion defect, and the composition
  overran the requested 9 s (built 10.5 s), so the GIF, sampled to 9 s, dropped most of
  the final scene. `check` reported `0 layout errors`.
- **Attempt 3** — studio run `12628`: accepted, after a human supplied explicit
  proportion and never-overshoot feedback.

Every correction came from a human rejecting the asset in Slack, which is slow and
costs a full composer turn each time. The engine cannot check what the composer most
needs checked, so the composer must review it itself.

The first run to carry the review still passed a layout it should have caught: studio
run `12645` reported "content spans 834 of 970px (86%)" while the rendered frames kept
every scene's visible content in the top third. The composer had measured a `flex: 1`
wrapper that stretches to fill the height, not the content inside it, so the proportion
rule has to name the **visible content** as the measure. The same run exposed a second,
smaller gap: a multi-scene composition gave the viewer no sense of position, so it
should carry a page indicator.

## What Changes

- **Add a mandatory review before rendering** to
  `agents/adapters/pi-render/prompts/authoring.md`, covering the four things the
  engine's checks do not: content fidelity, frame proportion, legibility, and pacing
  (including a total no longer than the brief's duration). The review's measured values
  are stated in the run report so the review is checkable offline.
- **State the layout rule that fills the frame**: put the padding and vertical layout
  on the element that directly contains the content; never put padding on a clip and
  the content in a second absolutely-positioned wrapper, which escapes it. Measure the
  **visible content's** coverage, not a wrapper that can flex to fill.
- **Require a page indicator on a multi-scene composition**: every scene carries the
  scene number in the same bottom-right position, so a viewer always knows where they
  are.
- **Add an offline test** (`agents/adapters/pi-render/test/authoring-prompt.test.mjs`)
  asserting the guide carries the review section, its checks, its thresholds and its
  page-indicator rule.
- **No change** to the session contract, the artifact endpoint, the type registry, or
  any workflow. This is the authoring guide alone.

## Capabilities

### Modified Capabilities

- `agent-authored-compositions`: an authored composition is reviewed for content,
  proportion, legibility and pacing before it is rendered and reported.

## Impact

- `agents/adapters/pi-render/prompts/authoring.md` — baked into the adapter image, so
  the change is live only after the image is rebuilt and its digest pinned
  (`publish-images.yaml` rebuilds on a change under `agents/adapters/<name>/` and the
  pin job commits the new digest; ArgoCD then syncs the session).
- `agents/adapters/pi-render/test/authoring-prompt.test.mjs` — new, run by CI's
  `pi-render-adapter` job.
