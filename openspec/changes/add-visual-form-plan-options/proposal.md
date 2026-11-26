# Proposal

## Why

The post on Genie Migrate for Lakehouse is the evidence. Row 49 carried
`HOOK=NEWS_REACTION`, whose registry default is `visual: {form: "poster", scenes: 0}`, and
the writer's own form answer was never the decision the studio used. Execution 17958
rendered a 6-second, one-card `poster_gif` whose headline was "Review, not rewrite." — a
claim — while the thing the post announced, that the service is GA, and the features that
make the GA worth reading did not fit. The owner rejected it: a poster cannot carry a GA
plus three features, and the form was chosen before the content was read.

The current gate has one plan turn. It picks the form and the storyboard in the same JSON,
one critic judges that single plan, and a failed plan is revised once. There is no stage
where the studio proposes **what kind of thing this is** (poster, story, launch, diagram,
data, timeline) and no stage where it proposes **more than one storyboard** for the chosen
kind. The form is therefore the hook's default, the row's pin or the writer's guess; the
storyboard is the first thing the composer thought of.

## What Changes

- **A form-options stage inside Visual Studio.** When the requested type declares no form
  and the caller does not pin one, the studio asks the composer for 2–3 candidate forms
  from `visual_forms.md`, each with a one-line rationale and a one-line composition sketch.
  A text critic ranks them and picks one. The choice is recorded on the asset.
- **A plan-options stage inside Visual Studio.** For the chosen form, the composer returns
  2–3 structured storyboards (the existing plan schema, one option per entry). A text critic
  ranks them and picks one; the chosen plan is the one the authoring turn renders. The
  options and the choice are recorded on the asset.
- **The post writer's form becomes a hint, not the decider.** `VISUAL_FORM` from the writer
  is passed to the studio as `SUGGESTED_FORM`; the studio's form stage owns the decision. A
  human edit of the row still pins the form and skips the stage.
- **The studio no longer forces the 6-second poster on an animated post.** The post lane
  requests `animation_linkedin_video` for `POST_MEDIA=ANIMATED`; `poster_gif` remains a
  supported type for an explicit poster request, not the `NEWS_REACTION` default.
- **The article lane is unchanged.** Its `svg_wide`, `figure` and other types declare a
  form, so the form stage is skipped; its outline turn already offers three shapes.

## Capabilities

### Modified Capabilities

- `visual-studio`: the form is selected from options before the plan; the plan is selected
  from options; a text critic picks each; the options and choices are recorded on the asset.
- `linkedin-post-publishing`: the writer's form answer is a hint; the studio owns the form
  decision; a row pin still wins; an animated post requests the 30-second video type.

## Non-goals

- No new article outline or draft step. The article's outline already offers three shapes
  with section lists; generating three full drafts would triple the writer cost for no
  additional form decision.
- No human approval card inside Visual Studio. The critic picks each stage; the existing
  media approval remains the human gate.
- No new visual type. `poster_gif` and `animation_linkedin_video` stay; only which one an
  animated post requests changes.
