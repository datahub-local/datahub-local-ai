# Spec Delta

## MODIFIED Requirements

### Requirement: A request may carry a scene plan

An authoring request SHALL be able to declare how many scenes the authored visual
should carry, and the brief delivered to the composer SHALL state that the content
be rendered as one item per scene. WHEN the request declares more than one scene,
the brief SHALL also ask for an opening title scene that names the subject, placed
before the declared scenes, so the authored visual carries the declared count plus
the title. WHEN the request declares exactly one scene, the brief SHALL NOT ask for
a title scene.

When the request declares no scene count, the composer SHALL choose its own
storyboard. If the requested type declares that it sequences content
(`introScene`), the brief SHALL still ask for an opening title scene that names the
subject — the company, product or technology the post is about — before the content
scenes; the content scene count remains the composer's. A type that does not declare
`introScene` SHALL NOT be asked for one.

#### Scenario: A declared scene count is honoured

- **WHEN** a request declares a scene count
- **THEN** the brief asks for that many items, one per scene

#### Scenario: A multi-scene count opens on a title scene

- **WHEN** a request declares a scene count greater than one
- **THEN** the brief also asks for an opening title scene that names the subject
- **AND** the authored visual carries the declared count plus the title

#### Scenario: A single-scene count has no title scene

- **WHEN** a request declares a scene count of one
- **THEN** the brief asks for no title scene

#### Scenario: No scene count leaves the storyboard to the composer

- **WHEN** a request declares no scene count
- **THEN** the composer plans its own content scenes

#### Scenario: An animated clip introduces its subject

- **WHEN** a request declares no scene count and the type declares `introScene`
- **THEN** the brief asks for an opening title scene that names the subject
- **AND** the content scenes remain the composer's

#### Scenario: A type that is not a sequence gets no title

- **WHEN** a request declares no scene count and the type does not declare
  `introScene` (a tiling loop, an SVG, a still, a deck)
- **THEN** the brief asks for no title scene
