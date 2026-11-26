# Spec Delta

## ADDED Requirements

### Requirement: The form is selected from options before the plan

For an agent-authored type that declares no form, and when the caller does not pin a form,
the studio SHALL ask the composer for two or three candidate forms from `visual_forms.md`
before it asks for a storyboard. Each option SHALL carry an id, the form id, one line on
why the content needs that shape, and one line on the composition. A text critic SHALL rank
the options and name one. The chosen form, the options and whether the choice fell back
SHALL be recorded on the asset.

#### Scenario: An announcement with features
- **WHEN** the post announces a service's general availability and lists its features, and the type declares no form
- **THEN** the form options include the shapes that can carry an announcement and its feature set, and the critic picks the one that does
- **AND** the plan stage receives the chosen form

#### Scenario: The type or a human already chose the form
- **WHEN** the type declares a form, or the caller pins one
- **THEN** the form stage is skipped and the declared or pinned form is used

### Requirement: The plan is selected from options

For the chosen form, the studio SHALL ask the composer for two or three structured plans.
Each option SHALL be a valid plan for that form, with the plan's subject, question, scenes,
close and arc. A text critic SHALL rank the options against the post, the content and the
person's requirements, and name one. The chosen plan SHALL be the one the authoring turn
renders. The options, the chosen option and whether the choice fell back SHALL be recorded
on the asset.

#### Scenario: A stronger storyboard is not the first one
- **WHEN** the composer returns three plans and the first has a missing beat the second carries
- **THEN** the critic names the second and the authoring turn uses it

#### Scenario: The stage cannot decide
- **WHEN** the composer answer is unreadable, the critic names no valid option, or every option is invalid
- **THEN** the first valid option is used
- **AND** the asset records the fallback and the media approval names it

### Requirement: A selected plan is approved for authoring

A plan chosen by the plan-options critic SHALL count as approved. The single-plan revision
loop SHALL NOT run for it, and the authoring turn SHALL receive the chosen plan and its
form.

#### Scenario: The chosen plan is authored
- **WHEN** the critic names a valid plan option
- **THEN** `PLAN_APPROVED` is true, the plan and form are on the brief, and the render starts
