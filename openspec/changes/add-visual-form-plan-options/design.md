# Design

## Context

Execution 17958 is the gate finding. The post announced that Genie Migrate for Lakehouse
is generally available and listed seven sources, a check-and-revise loop, lineage-aware
conversion, 90%+ files correct per source and 25% less median migration time. The studio
rendered a 6-second `poster_gif` whose headline was "Review, not rewrite.", with the GA
only implied by a subline. The form came from `NEWS_REACTION`'s registry default
(`visual: {form: "poster", scenes: 0}`) and the type pinned it (`poster_gif` declares
`form: poster`), so neither the content nor a second reading could change it.

The current plan gate is one turn: `build_plan_brief` → `execute_plan` (`task: plan`) →
`parse_plan` → `review_plan` → `parse_plan_verdict` → approve/retry once → author. The
composer picks the form and the storyboard inside the same JSON, and the critic judges the
single plan it receives. There is no stage that proposes **which kind of visual** the
content needs, and no stage that proposes **more than one storyboard** for that kind.

## Decisions

### D1 — Two stages, each with options

The studio gains two text-only stages before authoring:

1. **Form options.** The composer returns 2–3 candidate forms from `visual_forms.md`, each
   with `id`, `form`, `why` (one line on why the content needs that shape) and `sketch`
   (one line on the composition). The forms are the vocabulary the plan schema already
   validates (`story`, `diagram`, `chart`, `data`, `poster`, `timeline`, `code`, `ui`,
   `quote`, `launch`, `sketch`, `manga`, `retro`, `tiles`).
2. **Plan options.** For the chosen form, the composer returns 2–3 structured plans, each
   the existing plan object with an `id`. The plan critic ranks them and names one; the
   chosen plan is the one the authoring turn renders.

Both stages are one composer call and one critic call. The options travel on the asset so
the choice can be read back without the execution record.

### D2 — A critic picks; the human still approves the media

The form critic and the plan critic are text-only calls to the same gateway model as the
existing plan critic. They return `{"choice": "<id>", "why": "..."}`. No Slack card is added:
the existing media approval remains the human decision, and the chosen form, plan and
options are in the asset's record so the approval message can name them.

*Rejected:* a Slack card per stage. It would add two waits to a lane whose active part
already runs 14 minutes, and the human's leverage is better spent on the final asset than
on two intermediate rankings.

### D3 — The type's form and a human row pin skip the form stage

A type that declares `form` (e.g. `svg_wide` → `diagram`, `poster_gif` → `poster`) has
already chosen the shape; the form stage is skipped. A non-empty `FORCE` from a human row
pin also skips it. The form stage runs only when neither exists (`FORCE=auto`, type form
empty), so the article's `svg_wide` and `figure` visuals keep their declared form.

### D4 — The writer's form is a hint; the post lane owns the type

`VISUAL_FORM` from the post writer is passed to the studio as `SUGGESTED_FORM`. It is one
signal the form critic reads, not a force. The post lane stops writing the writer's
`VISUAL_FORM`/`SCENES` back to the row: a non-empty row cell is then a human pin, not a
writer auto-write that becomes a pin on the next run. `update_hook_columns` keeps writing
`HOOK` only.

For `POST_MEDIA=ANIMATED` the post lane requests `animation_linkedin_video` (30 s, 4:5)
rather than mapping `VISUAL_FORM=poster` to `poster_gif`. The 6-second poster remains a
supported type for an explicit request, but it is no longer what the `NEWS_REACTION`
default silently selects.

### D5 — A failed stage falls back to the first valid option

An unreadable composer answer, a choice id that names no option, or a critic that answers
nothing leaves the first valid option as the result and sets `OPTIONS_FALLBACK=true` and
`NEEDS_REVIEW=true` on the asset. The media approval names the fallback; the render is not
blocked. This mirrors `parse_verdict`'s unread-answer rule: a stage that could not decide is
not reported as a clean decision.

### D6 — The article text is untouched; its visuals get the plan options

The article outline already offers three shapes with section lists. It is unchanged. The
article's **visuals** are agent types rendered by Visual Studio: `svg_wide` and `figure`
declare a form, so the form stage is skipped, but the plan-options stage runs and gives
their diagrams multiple storyboards. The same applies to a caller's pinned `FORCE`: the pin
is the fixed form, so the form stage is skipped and the plan-options stage runs with it.
`if_needs_form` owns only the form-stage gate; its false branch goes to
`if_plan_options_start`, which starts the plan-options stage when a first authoring turn has
a fixed form (`FORM` non-empty or `FORCE` not `auto`) and otherwise routes to
`if_needs_plan`. The single-plan path starts there only when a stage could not decide; a
correction turn or an approved/exhausted plan goes straight to authoring. That is the same
gate, applied where the studio owns the composition.

## Graph

```
build_author_brief -> if_needs_form
if_needs_form --(true, no form, FORCE auto)--> build_forms_brief -> execute_forms
  -> parse_forms -> review_forms -> parse_form_choice -> if_form_options
  --(true)--> build_plans_brief -> execute_plans -> parse_plans -> review_plans
  -> parse_plan_choice -> if_plan_options --(true)--> build_author_brief
if_needs_form --(false)--> if_plan_options_start
if_plan_options_start --(true, type form or pinned FORCE)--> build_plans_brief
if_plan_options_start --(false)--> if_needs_plan
if_form_options --(false)--> if_needs_plan
if_plan_options --(false)--> if_needs_plan
if_needs_plan --(true)--> build_plan_brief -> execute_plan -> parse_plan
  -> review_plan -> parse_plan_verdict -> if_plan_ok/if_plan_retry -> build_author_brief
if_needs_plan --(false)--> execute_author
```

`parse_plan_choice` sets `PLAN_APPROVED=true` and the chosen `PLAN`/`FORM`; the re-entered
`build_author_brief` then skips the plan gate and reaches `execute_author`. The correction
turn (`REVIEW_ROUND > 0`) still skips both stages.

## Risks

- **Latency.** Two extra text calls per agent asset, each returning 3 options. The composer
  calls are plan-sized, not render-sized; the critic calls are short. Expect 1–3 minutes,
  not another 14.
- **Tokens.** Three plans in one answer is roughly three times the plan tokens. The plan is
  text; the cost is bounded by the plan prompt and the option count.
- **Choice quality.** The critic can pick a bad option. The existing plan critic's checks
  (person's requirements, arc, one idea per scene, close, metaphor) are the ranking rubric;
  an unreadable answer falls back and is marked, never silently passed.
- **Data cleanup.** Rows written by older runs may hold a writer's form in `VISUAL_FORM`.
  A non-empty cell is read as a human pin after this change; the migration is to clear
  those cells once, then a human edit is the only way a pin appears.

## Open Questions

- Should the form options include **asset types** as well as forms (e.g. 6 s poster vs
  30 s video), or stay composition forms inside a caller-chosen type? This design keeps the
  type the caller's: the post lane always asks for the 30 s video.
- Three options for both stages, or two for forms and three for plans? This design uses
  three for both; the composer may return two when the content clearly admits only two.
