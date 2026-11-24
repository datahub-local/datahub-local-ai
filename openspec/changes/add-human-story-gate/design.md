# Design

## Context

The last five executions on row 48 are one post, not five topics:

| Execution | Form | Renders | Human outcome |
|---|---|---|---|
| 17438 | `ARCHITECTURE` → `diagram` | 3 | rejected: source slide, text out of box, arrows before shapes |
| 17498 | `ARCHITECTURE` → `diagram` | 1 | cancelled |
| 17510 | `ARCHITECTURE` → `diagram` | 2 | rejected: arrows/connections, too much text |
| 17539 | `ARCHITECTURE` → `diagram` | 1 | cancelled |
| 17575 | `TRADE_OFF` → `story` | 3 | two retries on the close and two scenes; published |

The studio reviews behind the last run are the gate findings for this change:

- **17579 round 1** told the composer to move the conclusion off the closing scene and print
  the Source alone. The human then said the last slide must contain both. **17587 round 1**
  told the composer to fade the headline out before the Source. The human rejected again.
- **17587 round 0** told the composer to cut "So nobody notices." and "No dual write." as
  over budget. The human then asked to keep both and cut labels instead.
- **17579** ended with two open findings and `RETRY: false`; the sharing workflow's live
  `check_animation_result` dropped them, so the approval never named them.
- **17595** (after the second human note) caught the false `database → serving` arrow and
  the ambient sheen that looked like a connector, then passed. The critic can reason about
  meaning when the evidence and the priority put it there.

The form was the first decision and the last one to change: four diagram attempts, then a
manual row override to `story`. `TRADE_OFF`'s registry default is still `diagram`.

## Decisions

### D1 — The person's requirements outrank every style rule

The review's first pass is to read the brief's `Feedback from the person` block and list its
requirements. A style rule — the Source-alone default, the copy budget, the layout
preference — never justifies a finding that removes a required line. The 17579/17587 rounds
are the failure: the critic applied the Source-alone rule against an explicit human
instruction, twice. The review prompt states this at the top and the answer requires the
critic to answer each requirement.

### D2 — The review judges the story before the pixels

The order is: person's requirements → plan → per-scene takeaway → arc → attention and
metaphor → geometry → arrows → legibility → copy → fit → fidelity → brand.

- **Per-scene takeaway.** The critic names the one idea each scene should leave. If it
  cannot, or the scene carries two ideas, that is a finding. This is the check the old
  rubric never had.
- **Arc.** The intro names the subject and the question; the middle explains the mechanism
  or the trade-off in an order a viewer can follow; the conclusion answers the question; the
  Source closes. A missing, repeated or misplaced beat is a finding.
- **Standalone.** A scene must be understood without the post text. A scene that needs a
  word the post carries is a finding: put the word on screen or split the scene.
- **Motion.** The critic still judges stills, but the contact sheet and the plan give it the
  order and the transitions. A fade that removes the conclusion, or an arrow that appears
  before both shapes, is a finding even though it is a timing defect.

### D3 — The close is a declared beat, not a default

For a story clip with a conclusion, the closing frame carries the conclusion and the Source
together, and the conclusion does not fade before the Source. A Source-only close is for a
clip that has no conclusion. This is a `visual_scene.md` rule and a review rule, so the
composer and the critic cannot disagree about it.

### D4 — Clarity is the budget's purpose, not its enemy

The budget stays: one claim line, up to three labels, one figure. It gains one exception:
when the shapes alone do not make the idea, one explanatory line of eight words or fewer is
allowed, and when a scene is over, a label is cut before that line. A line the person
required is never excess. The old rubric cut the line that made the scene make sense; that
is how "It IS a moment behind" became a wall of labels.

### D5 — A shape, icon and attention vocabulary

The composer has forms and motion rules but no semantics for the devices it uses. The new
rules are compact:

- **Shape is a claim.** Stacked = hierarchy; side by side = peers; arrow = cause or
  direction; loop = recurrence; dashed = eventual; filled = present; outline = absent; size
  = importance. A shape that states a relationship the content does not is severity 1.
- **Icon and emoji name things.** A technical object gets a shape or a label, not an emoji;
  the brand defines no emoji. No generic icon collage, no app icon or logo, nothing
  decorative. An icon whose removal loses no meaning is decoration.
- **Attention.** Every scene has one focal point and one emphasis device that lands on the
  point: a highlight, a pulse, a counter, a build, a camera move. Animate the one thing the
  viewer should look at, not everything. A title card that only names the subject is not a
  hook; the opening gives a reason to stop.
- **Order follows the argument.** Cause before effect, the connector after both shapes, the
  number after the thing it measures.

### D6 — The writer chooses the form from the post

The writer answers `<form>ID</form>` beside `<hook>ID</hook>`, from the vocabulary in
`visual_forms.md`. The post creator writes it to `VISUAL_FORM` unless the row already pins
one; the row still wins, because a human editing the row is the override. The hook's
`visual` becomes the fallback, not the decision. The mapping is by the post's argument, not
the article's topic: a sequence, a mechanism or a failure over time is `story`; a structure
is `diagram`; a measured comparison is `chart` or `data`; one claim is `poster`; a change
over time is `timeline`.

*Rejected:* changing the `TRADE_OFF` default to `story`. It would fix this post and
mislabel the next trade-off that really is a two-pan diagram. The argument decides.

### D7 — Plan before render

The composer returns a structured plan before it renders:

```json
{"form":"story","subject":"Kafka + database truth","question":"which system is truth?",
 "scenes":[{"n":1,"beat":"three systems","line":"one decision, three systems",
            "device":"stacked boxes with a flow","motion":"boxes arrive, connectors follow",
            "transition":"cut"}],
 "close":{"line":"quiet failures cost the most","source":"kai-waehner.de"},
 "arc":"question -> three systems -> lag -> write discipline -> close"}
```

A text critic reviews the plan against the post, the content and the person's requirements
before the authoring turn. It fails on a missing beat, a scene with two ideas, an intro that
could open any post, a conclusion that does not answer the intro, a misleading metaphor, or
an attention plan that is a wall of labels. The approved plan is appended to the authoring
brief, so the composer writes to a plan the critic and the human have seen.

The plan turn is text-only and bounded (two plan rounds). It costs one short model call; a
render costs 30–60 minutes and, in the last five runs, two human rejections.

### D8 — Plan the first authoring, not every correction

The plan gate runs when `REVIEW_ROUND === 0` and the session has no composition. A human
retry or a critic correction already carries a plan in the composition and a specific
finding; re-planning it would pay twice for the same decision. The approved plan travels on
the asset (`PLAN`) and the brief, so a retry can still read it.

## Interfaces

### Plan request / response

`POST /v1/chat/completions` with `{task: "plan", messages: [{role: "user", content: brief}],
session_id}` returns:

```json
{"plan": {"form":"story","subject":"...","question":"...","scenes":[...],
          "close":{"line":"...","source":"..."},"arc":"..."},
 "raw":"the model's answer"}
```

`plan` is `null` with an `error` string when the answer carries no parsable object. The
server runs the plan turn without tools, so it cannot write or render. The authoring path is
unchanged.

### Post form

The post draft answers `<form>story</form>` after `</output>`, beside `<hook>`. The adapter
returns `post.form`; an id outside the brief's `forms` list is a named error, never a blank
cell. The post creator writes `VISUAL_FORM` from it when the row is empty.

### Asset and brief

The asset carries `PLAN` (the approved JSON, serialized) beside `STORYBOARD`. The critic
receives the plan, the storyboard and the brief; the authoring brief carries the approved
plan as a titled block before the content.

## Risks

- **The critic over-reports story defects and burns the three review cycles.** The review
  already ships with open findings named at approval; the story findings are severity 1–2
  and the composer gets the plan first. If the critic still stalls, the human sees the
  findings instead of a silent pass.
- **The plan critic is another model judgment and can be wrong.** The plan is cheap to
  revise and the human sees the approved plan in the run record. A bad plan that passes is
  still caught by the post-render story pass.
- **The form choice needs the writer image rebuilt and pinned.** Until the image is
  deployed, the writer returns no `<form>` and the hook default applies, so the change is
  additive and safe.
- **Model variance.** The critic answered `fix` and `ok` on the same stills before the
  contact sheet. The plan gate adds a text-only judgment, which is more stable, and the
  story pass is measured against the five labelled runs rather than a single live run.
- **Cost.** One plan turn (short) plus one plan review (text) per first authoring. The
  last five runs spent four failed renders and two human retries; the trade is favourable.

## Open Questions

- Should the plan be shown to the human in Slack before the render, in addition to the
  critic? It is cheap to add later; this change keeps the critic as the gate.
- Should a severity-1 plan finding be able to force a different form (for example, a
  `diagram` plan that the critic says is really a `story`)? The critic may name the form in
  its fix; the composer decides within the row's pinned form.
- Does the writer need the full form definitions or only the mapping? The brief carries the
  mapping and the vocabulary ids; the detailed definitions stay in `visual_forms.md`.

## Definition of Done

- The review prompt states the new order and a finding that removes a human-required line is
  invalid; the plan and the per-scene takeaway are part of the critic's evidence.
- A story clip's close carries the conclusion and the Source together, and the review can
  fail a render that fades the conclusion.
- The composer can use one explanatory line when the shapes alone do not make the idea, and
  cuts a label before that line.
- The writer answers `<form>` and the post creator writes it to `VISUAL_FORM` unless the row
  pins one; an unknown id fails by name.
- A `task: "plan"` turn returns the structured plan without writing or rendering; a plan
  reviewer can fail it; only an approved plan reaches `execute_author`.
- The five labelled runs replay through the new plan/story criteria and the expected
  failures are named: 17579's missing conclusion, 17587's fade-out and cut lines, and the
  four diagram runs' wrong form.
- `close-visual-review-holes` task 7.4 is applied so the approval names the open findings.
- `openspec validate add-human-story-gate --strict` passes and the adapter tests pass.
