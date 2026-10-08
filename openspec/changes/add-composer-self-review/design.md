# Design

## Context

See [proposal.md](proposal.md) — Why. The facts that shape the approach:

- **The composer cannot see images.** `authoring.md` says so explicitly and forbids
  screenshots and layout-measurement scripts, because an earlier run spent its whole
  turn writing seven puppeteer scripts to measure a layout it could never view. A
  review step must therefore be a **checklist over values the agent already knows**
  (the CSS it wrote, its scene durations), not visual inspection.
- **The engine's checks miss both observed defects.** `hyperframes check` audits
  runtime errors, failed requests, layout, motion assertions and WCAG contrast; it
  returned `0 layout errors` on both a composition whose content filled the top 40 %
  and one that overran its duration by 1.5 s. Contrast and overflow are covered;
  *fill* and *pacing versus the requested length* are not.
- **The brief already carries the budget.** `build_author_brief` sends the requested
  `durationSeconds`, `frames`, width, height and format, and asks for slow motion. The
  guide, not the brief, is the place for a generic method the type registry and every
  caller share.
- **The guide is baked into the image.** A prompt change is not live until the image is
  rebuilt and pinned; `publish-images.yaml` rebuilds an adapter when a non-`deploy/`
  file under it changes and the pin job commits the digest.

## Goals / Non-Goals

**Goals:**

- A composer turn self-corrects the four classes a human caught: wrong/added content,
  a frame that is not filled, type too small to read, and motion or length too fast.
- The review is checkable from the run record without the artifact.

**Non-Goals:**

- Making the engine's `check` detect fill or pacing (a CLI change, out of this repo).
- A deterministic post-render measurement of the artifact (image analysis; a separate
  idea, rejected below for now).
- Changing any type's budget, the session contract, or a workflow.

## Decisions

### D1. The review lives in `authoring.md`, and is mandatory and reported

The composer's operating guide is where a method that applies to every type belongs,
and it is the artefact the agent reads each turn. The review is stated as a required
step and its measured values (per-scene content coverage, minimum type size, total
duration) must appear in the report, so a reviewer can check the review itself and not
just the asset.

*Alternatives considered:* put the criteria only in the workflow brief
(`build_author_brief`) — rejected as the wrong home: it would be re-sent by every
caller and could drift from the guide, and it does not reach a non-workflow session
(the spike, a future caller). Put them in both — rejected as a second copy of one
decision, the failure mode this repository repeatedly warns about.

### D2. Proportion is a layout rule with a named failure

The observed defect was structural: padding on the clip, content in a second
absolutely-positioned wrapper that escaped it. The review names that pattern as the
defect and states the rule that avoids it (layout belongs on the element that contains
the content), rather than only saying "fill the frame" — which the composer already
believed it had done.

### D3. Pacing includes the total versus the brief's duration

The second defect was not speed but length: a 10.5 s composition sampled to the 9 s the
brief asked for loses its last scene. The review therefore bounds the **total** to the
requested duration as well as each scene and reveal.

### D4. Numbers, not adjectives

Legibility and pacing are stated as numbers (heading ≥ 34 px, body ≥ 18 px, label ≥
14 px, at the rendered width; scene 2.5–3.5 s, reveal 0.6–0.9 s, hold ≥ 1.5 s). A small
model acted on "animate slowly" for two turns and still produced sub-frame reveals; the
same model can compare two numbers.

## Risks / Trade-offs

- **A longer guide competes for the model's attention and the context window.** → The
  section is short and numeric; the existing "do not measure the layout" rule stays, so
  no tool budget is added.
- **A checklist is not enforcement.** The review is model-reported, so a run can still
  ignore it. It is the cheapest lever; a deterministic fill/pacing gate would need a
  CLI capability HyperFrames does not expose today.
- **A prompt change is only live after an image rebuild.** Stated in the proposal and
  in the tasks; the acceptance run must follow the pin, not the edit.

## Open Questions

- Should a future change add a deterministic post-render guard (e.g. reject an artifact
  whose content does not reach the lower third)? Deferred: it would misjudge a design
  that legitimately uses negative space, and it belongs with the engine's `check`.
