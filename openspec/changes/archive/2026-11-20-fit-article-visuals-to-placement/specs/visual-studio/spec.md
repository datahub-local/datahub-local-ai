# Spec Delta

## MODIFIED Requirements

### Requirement: A figure is authored from its section

The registry SHALL declare a `figure` type for a section illustration in an article:
authored by the composer agent, a static SVG at 16:9. A request for that type SHALL carry
the heading and text of the section the slot sits in, and the type's brief SHALL illustrate
that section rather than the source as a whole — the page's lead image already states the
article's thesis, so the figure SHALL illustrate the section's flow, step or comparison row
and SHALL NOT restate the thesis. The brief SHALL compose for the width the figure is
rendered at, inline in the text column: one idea, labels legible at that size, and no code
text used as imagery. The type SHALL be authored once per requested slot, so a caller that
needs several figures requests the type several times with different section briefs.

#### Scenario: Two figures, two sections

- **WHEN** the caller requests two figure slots with different section briefs
- **THEN** each is authored from its own section
- **AND** each returns its own SVG

#### Scenario: A figure slot has no section

- **WHEN** a figure request carries no section text
- **THEN** the request is refused with a reason naming the missing brief
- **AND** no figure is authored

#### Scenario: A figure does not repeat the lead

- **WHEN** a figure is authored for an article that already has a lead image
- **THEN** its brief excludes the article's thesis
- **AND** the figure shows its section's own mechanics

#### Scenario: A figure reads inline

- **WHEN** a figure is rendered inside the text column
- **THEN** its labels and single idea remain legible at that width
