# Spec Delta

## ADDED Requirements

### Requirement: An authored composition follows the shared brand

Where a composition is authored from a brief rather than selected from a fixed
template, the brief SHALL carry the shared brand tokens and the authored
composition SHALL use them: the brand's flat UI language for its surface,
accents, typefaces and shapes. The authored path SHALL NOT be the one flow that
ignores the brand, and it SHALL NOT be asked to invent a palette.

#### Scenario: The brief carries the brand
- **WHEN** a composition is authored from a brief
- **THEN** the brief includes the shared brand tokens
- **AND** the authored composition uses them

#### Scenario: An authored diagram matches the deterministic one
- **WHEN** an authored composition and a deterministic asset are produced for the same brand
- **THEN** both use the same palette and typefaces
- **AND** neither is the only branded artefact
