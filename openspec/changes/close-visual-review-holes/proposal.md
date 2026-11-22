# Proposal

## Why

The studio's self-review is a vision critic over stills, and every hole it has found has been
closed by editing `prompts/visual_review_composition.md`. Six commits on that file, each sourced
from one live failure, have left a long checklist and the same classes of defect still reaching a
human. Execution 17510 is the current evidence:

- `Visual Studio` ran twice (17514, 17523), both ended `VERDICT: fix` at review round 3 with the
  budget exhausted, and both were reported `STATUS: COMPLETE` and posted to Slack for approval.
- 17514's critic named six real defects: arrows ending in empty space, two detached arrowheads,
  no Serving -> Agent arrow, a connector with no head, four labels plus two chips over the copy
  budget, and an extra sentence.
- 17523's composer found its own bug (quoted GSAP positions parsed as selectors, so nine
  connectors never drew), fixed it, ran `lint` clean and `check --at-transitions` passed — and the
  critic still saw a bare connector with no head. The human then cancelled for "too much text",
  a defect the critic had already named in the first run.

The loop cannot close this because it counts authoring turns, not resolved defects: findings have
no identity across rounds, nothing compares a correction with the render it was meant to fix, an
unreadable answer is a pass, and a `fix` verdict is still an approvable asset. Meanwhile the
framework already ships deterministic gates (`check --json`, motion sidecars, `measure`, `diff`)
that the workflow never reads.

## What Changes

- **Gate on the verdict.** An asset with open findings is `NEEDS_REVIEW`, never silently clean.
  The Slack approval names the open findings, and a reviewer can no longer be shown a `fix` asset
  as if the review had passed.
- **A finding ledger.** Findings get stable ids and carry `severity`, `source` (`critic` or
  `check`) and `seen` across turns. The critic must answer per open finding (`resolved` list plus
  re-reported findings) instead of returning a fresh global verdict. A finding that survives a
  correction turn is `stalled`: the loop stops spending cycles and the human decides.
- **The critic ranks.** Every finding carries severity 1-3, and the correction brief lists the
  findings in that order.
- **Deterministic checks before the critic.** The adapter runs `hyperframes check --json
  --at-transitions` on the render, probes freeze/black frames and cuts with ffmpeg, and returns
  the result as data on the asset. Check errors become ledger findings; a check that could not
  run is recorded, not read as clean.
- **Stills are sampled by scene, not by uniform offsets.** Cut detection gives scene intervals;
  each scene contributes a still, so a seven-scene clip can no longer be seen in three moments.
- **Connectors are declared data, not hand-placed geometry.** A composition declares
  `connectors.json` (`{id, from, to}`) and draws each with the staged `connectors.js` helper,
  which computes endpoints from the live boxes and always draws the head. The adapter verifies
  the helper ran clean; a hand-drawn arrow with no declaration is a defect for every `diagram`
  brief.
- **Unreadable is `needs_review`.** A critic call that errors twice, or answers something
  unparseable, records `verdict: unread` and blocks auto-approval — the direction the
  `visual-studio` spec already states and the code contradicts.
- Update the `visual-studio` capability, the two review prompts, the composer's authoring guide,
  the LinkedIn approval message, and `docs/agent/n8n.md`.

## Capabilities

### New Capabilities

<!-- None. -->

### Modified Capabilities

- `visual-studio`: the review is a ledger with a bounded budget, an unreadable answer is recorded as
  unread and blocks approval, the critic ranks findings, deterministic checks are part of the
  review's evidence, and an asset's record carries its open findings.
- `linkedin-post-publishing`: an animated asset with open findings is presented for human approval with
  those findings named, not as a completed asset.

## Impact

- **`agents/n8n/workflows/visual_studio.workflow.json`** (both graph copies): `agent_result` carries
  the adapter's `check`, `signals` and `connectors`; `prepare_stills` and `encode_stills` carry the
  ledger; `parse_verdict` and `parse_raster_verdict` merge statuses and rank; `review_feedback`
  emits the ordered correction; `set_result` reports the review.
- **`agents/n8n/workflows/linked_in_post_sharing.workflow.json`** (both graph copies):
  `check_animation_result` exposes the review state and `notification_accept_animation` prints the
  open findings.
- **`agents/n8n/prompts/visual_review_composition.md`** and
  **`agents/n8n/prompts/visual_review_raster.md`**: the ledger protocol, severity, and the
  evidence requirement.
- **`agents/adapters/pi-render/`**: `session-lib.mjs` (check, signals, scene-aware stills,
  connector validation), `session-server.mjs` (run and return them), `prompts/authoring.md`
  (connector declaration), `runtime/connectors.js`, staged beside the composition, and the unit tests.
- **`docs/agent/n8n.md`**: the Visual Studio review section.
- **Not changed**: the type registry, the brand, `visual_scene.md`'s copy budget (it stays the
  rule the check and the critic enforce), and the session transport.
