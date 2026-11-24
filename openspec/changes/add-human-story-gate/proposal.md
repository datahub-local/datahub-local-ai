# Proposal

## Why

The review catches geometry and copy volume, but not whether a clip makes sense. Five
executions on one post (row 48, 2026-11-21/22) are the evidence:

- Four runs forced `ARCHITECTURE` → `diagram`; the same content shipped only when the row's
  form was changed to `story`. The writer chooses the hook, not the form; the form is the
  hook's default or a human edit.
- The critic told the composer to move the conclusion off the closing frame and leave the
  Source alone (17579), then to fade the conclusion out before the Source (17587). The human
  had asked for both on the last slide, and rejected both renders. The human then asked to
  keep two explanatory lines the critic had cut as over budget, cutting labels instead.
- The critic has no check for "what does this scene make the viewer understand", no
  whole-clip arc, no attention or metaphor rule, and it judges stills but not motion. A
  scene can pass every criterion and still be incomprehensible.
- The critic never sees the composer's plan, only the brief and the stills, so it cannot
  judge whether a scene delivers the idea it was meant to carry.
- The composer plans and renders in one turn. The plan is where "the intro and conclusion
  do not fit" and "the slides do not make sense as a whole" are cheapest to fix.

`close-visual-review-holes` already built the ledger, the deterministic checks and the
approval that names open findings; its task 7.4 (apply live) is not done, so the human never
saw the findings in these runs. This change adds the missing story gate on top of that work.

## What Changes

- **The critic judges the story first.** A new order: the person's requirements, the plan,
  the scene-by-scene takeaway, the whole-clip arc, attention and metaphor, then geometry,
  copy, fidelity and brand. A finding that removes a line the person required is invalid.
- **A scene must carry one idea.** The critic states the takeaway of each scene; if it
  cannot, the scene is a finding. The clip must be understandable without the post text.
- **The close is explicit.** A story clip's closing frame carries the conclusion and the
  Source together; the conclusion does not fade before the Source. Source-only is for a clip
  with no conclusion.
- **Clarity outranks the copy budget.** When a scene is over, cut a label before the line
  that states the point. One explanatory line is allowed when the shapes alone do not make
  the idea.
- **A shape, icon and attention vocabulary.** Shapes mean relationships; icons and emoji
  name things rather than decorate; every scene has one focal point and one emphasis device.
- **The writer chooses the form from the post it wrote**, and the post creator uses that
  choice unless the row pins one. The hook's `visual` becomes the fallback.
- **A pre-render plan gate.** The composer returns a structured storyboard before it
  renders; a text critic reviews the plan; only an approved plan reaches the authoring turn.
  This catches a bad arc, a wrong metaphor or an overstuffed scene before a render is paid
  for.

## Capabilities

### New Capabilities

<!-- None. -->

### Modified Capabilities

- `visual-studio`: the review judges the story and the plan before geometry; a scene must
  carry one idea; the close carries the conclusion and the Source; the form is chosen from
  the post's argument; a structured plan is reviewed before the render.
- `linkedin-post-publishing`: the writer answers the visual form beside the hook, and the
  row's pinned form still wins.

## Impact

- `agents/n8n/prompts/visual_scene.md`, `visual_review_composition.md`,
  `visual_forms.md` and a new `visual_review_plan.md` — the story rules, the review order,
  the form map and the plan critic.
- `agents/adapters/pi-render/` — a `task: "plan"` turn, `prompts/plan.md`, `parsePlan` and
  `planInstruction` in `session-lib.mjs`, the server's plan path, and tests.
- `agents/adapters/pi-writer/` — the form vocabulary on the post brief, `parsePostForm`,
  and tests. The writer image is rebuilt and pinned.
- `agents/n8n/workflows/visual_studio.workflow.json` — the plan nodes and the approved plan
  on the authoring brief; `encode_stills` carries the plan and the story criteria.
- `agents/n8n/workflows/linked_in_post_creator.workflow.json` — parse `<form>` and write
  `VISUAL_FORM`; `linked_in_post_sharing.workflow.json` — no new logic, the existing
  `build_hook_columns` already reads it.
- `agents/n8n/workflows/linked_in_post_sharing.workflow.json` and the visual studio export
  — finish `close-visual-review-holes` task 7.4 so the approval names the findings.

## Non-goals

- No feedback store, no engagement-metric poller, no auto-tuning of prompt weights.
- No new visual type and no carousel format.
- No deterministic semantic judge: the story and metaphor checks are model judgments, and
  the plan gate is text-only.
