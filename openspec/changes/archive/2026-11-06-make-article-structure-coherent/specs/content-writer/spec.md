# Spec Delta

## ADDED Requirements

### Requirement: An article is one spine, one path and the names it created

The drafting pass SHALL write one article around one outcome rather than a tour of everything the
sources hold. Every shape SHALL inherit the same contract: one outcome named before the first
sentence; one path, with an alternative demoted to a sentence outside the numbered steps; every name
a later step uses created by an earlier step and spelled the same; one job per section; numbered
step headings as one sequence 1..n with no gap, duplicate or sub-step, and an unnumbered close; and a
step that ends on what the reader sees when a source carries it. The body SHALL NOT narrate the
article or the work of writing it.

The drafting gate SHALL reject a draft that breaks the contract, naming the step and the name, so the
retry receives the failure instead of passing it to the improvement pass. The structure aspect SHALL
report the same defects on the improvement pass.

#### Scenario: A later step uses a name the article never created

- **WHEN** a walk-through step names a cluster, namespace, Secret, ensemble, persona, run or URL that
  no earlier step created
- **THEN** the draft is rejected, naming the step and the name
- **AND** the retry is told to use the name the article created

#### Scenario: An alternative install sits inside the numbered path

- **WHEN** a numbered step carries a second installation route, a second tool or another page's
  example object as a sub-step
- **THEN** the draft is rejected as a second path
- **AND** the alternative is demoted to a sentence outside the steps or cut

#### Scenario: A second teaching section follows the walk-through

- **WHEN** a section after the walk-through explains material the article did not explain where it
  first appeared
- **THEN** the draft is rejected as a second job
- **AND** the explanation moves to the step that first shows the thing, or is cut

#### Scenario: Numbered steps are not one sequence

- **WHEN** the step headings are numbered and one is skipped, duplicated, or joined by a numbered
  sub-step, or the close is numbered
- **THEN** the draft is rejected
- **AND** an article that is not a walk-through numbers no heading

#### Scenario: The close narrates the writing

- **WHEN** the body says it did not run something, refers to "this section", or notes that a sample
  is missing
- **THEN** the draft is rejected
- **AND** an unknown stated as a fact about the software is accepted

#### Scenario: A coherent draft passes

- **WHEN** every section serves the one outcome, every name is created before it is used, and the
  steps are one sequence
- **THEN** the gate does not reject the draft for structure
- **AND** the comparison, the numbers and the asset markers are judged by their own checks
