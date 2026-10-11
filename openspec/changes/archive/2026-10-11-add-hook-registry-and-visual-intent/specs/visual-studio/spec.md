# Spec Delta

## MODIFIED Requirements

### Requirement: Every trigger speaks one contract

The workflow SHALL expose the same parameter contract on every trigger — a sub-workflow call, an HTTP API webhook and a form — taking `CONTENT` (the source text, required), `ASSET_TYPES`, `FEEDBACK`, `FORCE` and `STYLE`, and MAY also take `SCENES`. `FORCE` SHALL be one of `auto`, `diagram`, `story`, `data`, `poster` or `image`, and `STYLE` SHALL name a brand scheme. `SCENES` SHALL be an optional positive integer requesting a sequence, and when it is blank the composer's own storyboard SHALL decide the scene count. The workflow MUST NOT read caller state from a table or sheet to decide what to produce; everything it needs arrives on the trigger.

#### Scenario: Same contract on every surface
- **WHEN** the same parameters arrive via the API webhook, the form or a sub-workflow call
- **THEN** the same asset set is produced

#### Scenario: Missing content
- **WHEN** a request arrives without `CONTENT`
- **THEN** the request fails naming the missing parameter

#### Scenario: An unknown force fails loudly
- **WHEN** a request carries a `FORCE` outside the enum
- **THEN** the request fails naming the value
- **AND** no asset is produced

## ADDED Requirements

### Requirement: A request may carry a scene plan

An authoring request SHALL be able to declare how many scenes the authored visual
should carry, and the brief delivered to the composer SHALL state that the content
be rendered as one item per scene. When the request declares no scene count, the
composer SHALL choose its own storyboard.

#### Scenario: A declared scene count is honoured

- **WHEN** a request declares a scene count
- **THEN** the brief asks for one item per scene
- **AND** the authored visual carries that many scenes

#### Scenario: No scene count leaves the storyboard to the composer

- **WHEN** a request declares no scene count
- **THEN** the composer plans its own scenes
