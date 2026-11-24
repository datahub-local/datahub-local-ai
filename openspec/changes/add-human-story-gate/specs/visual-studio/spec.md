# Spec Delta

## ADDED Requirements

### Requirement: The review judges the story before the pixels

The critic SHALL judge the artifact as a first-time viewer before it judges geometry. It SHALL
state, for every scene, the one idea the scene must leave with the viewer, and SHALL report a
scene whose idea cannot be stated, or which carries two ideas, as a finding. It SHALL judge the
whole clip's arc: the intro names the subject and the question, the middle explains the mechanism
or trade-off in an order a viewer can follow, the conclusion answers the question, and the Source
closes. A missing, repeated or misplaced beat SHALL be a finding. The critic SHALL be given the
composer's plan and the post text as evidence.

#### Scenario: A scene does not make its point
- **WHEN** the critic cannot state a scene's one takeaway, or the scene states two ideas
- **THEN** the verdict names that scene as a finding with the missing or split idea and a fix

#### Scenario: A technically clean but incomprehensible scene
- **WHEN** a scene has no overlap, no copy-budget breach and no missing arrow, but its idea is not
  clear without the post text
- **THEN** the review fails it as a story finding rather than passing it as clean

#### Scenario: The arc does not close
- **WHEN** the conclusion does not answer the question the intro raised
- **THEN** the review reports it before it reports any geometry defect

### Requirement: The person's requirements outrank every style rule

The critic SHALL read the brief's `Feedback from the person` block first and SHALL answer every
requirement in it. A finding that removes a line the person required is invalid, whatever style
rule it cites. The Source-alone default, the copy budget and a layout preference SHALL NOT justify
removing a required line.

#### Scenario: A required line conflicts with the copy budget
- **WHEN** the person requires a line that takes the scene over budget
- **THEN** the critic keeps the line and asks for a label to be cut instead

#### Scenario: A required close conflicts with the Source rule
- **WHEN** the person requires the conclusion and the Source on the closing frame
- **THEN** the critic treats the both-on-the-frame close as correct and does not ask for the Source alone

### Requirement: A plan is reviewed before the render

A first authoring turn SHALL return a structured plan before it renders. The plan SHALL name the
form, the subject, the question the clip answers, one beat per scene with its on-screen line, its
visual device and its transition, the closing line and Source, and the arc. A text critic SHALL
review the plan against the post, the content and the person's requirements and SHALL be able to
fail it. Only an approved plan SHALL reach the authoring turn; a failed plan SHALL be revised
within a bounded number of plan rounds. A correction turn SHALL NOT re-plan an existing
composition.

#### Scenario: The plan has a missing beat
- **WHEN** the plan has no conclusion, or the conclusion does not answer the intro
- **THEN** the plan critic fails it with the missing beat and a fix before any render is taken

#### Scenario: The plan passes
- **WHEN** every scene carries one idea and the arc closes
- **THEN** the approved plan is appended to the authoring brief and the render starts

#### Scenario: A human retry is correcting an existing composition
- **WHEN** the session already holds a composition and the turn is a correction
- **THEN** the plan gate is skipped and the existing plan and findings are used

### Requirement: The closing frame carries the conclusion and the Source

For a story clip whose content states a conclusion, the closing frame SHALL carry the conclusion
and the Source together, and the conclusion SHALL NOT fade out before the Source settles. A
Source-only close SHALL be used only when the clip has no conclusion.

#### Scenario: A fade removes the conclusion
- **WHEN** the closing frame fades the conclusion out before the Source settles
- **THEN** the review reports it as a severity-1 story finding

#### Scenario: The content has no conclusion
- **WHEN** the clip has no outcome line to close on
- **THEN** the closing frame prints the Source alone, exactly as given
