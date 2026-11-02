# Spec Delta

## ADDED Requirements

### Requirement: A report leads with its outcome

Every persona that posts a report to a channel SHALL begin the report with a single
outcome line stating what a person must act on, or that nothing needs action. The line SHALL
carry the persona's `Status` label, SHALL NOT exceed one sentence, and MUST NOT repeat
figures that appear again in the sections below.

#### Scenario: A run with something to act on
- **WHEN** a run finds a condition that needs a human
- **THEN** the first line names that condition and its action
- **AND** the sections below carry the evidence, not the headline again

#### Scenario: A clean run
- **WHEN** a run finds nothing to act on
- **THEN** the first line says so
- **AND** every section it is required to write is present in its clean form

### Requirement: A report fits one length budget

Every report SHALL fit a stated word budget, and the budget SHALL be stated once, in the
delivery contract every reporting persona receives, rather than restated per persona. The
budget SHALL be 300 words. A persona's own format section MUST NOT contradict it.

#### Scenario: A run would exceed the budget
- **WHEN** the figures a run gathered would not fit the budget
- **THEN** healthy sections are reduced to one line and the remaining figures to a count
- **AND** no finding, action or the outcome line is dropped to fit

#### Scenario: A persona keeps its own tighter budget
- **WHEN** a persona's format states a tighter cap than the contract
- **THEN** the tighter cap governs that report

### Requirement: A repeat of one reading across machines is one bullet

A report SHALL state each fact once, and a condition that holds on several machines or for
several members of a set SHALL be written as one bullet naming the members, its cause and
its action, rather than one bullet per member. A section MUST NOT restate a fact already
given in another section.

#### Scenario: The same condition on seven machines
- **WHEN** one condition holds for several machines
- **THEN** it is one bullet naming the machines
- **AND** its action is stated once

#### Scenario: A long column of readings
- **WHEN** a tool returns more readings than fit the budget
- **THEN** the worst reading is named with its value and the change
- **AND** the remainder is reported as a count with its range

### Requirement: Every report uses one layout

Every report SHALL use a single layout, so a reader who has skimmed one report can skim the
next: the outcome line, then one `##` heading per section on its own line, then `- ` bullets
under it. Each bullet SHALL carry exactly one fact and MUST NOT exceed two rendered lines; a
fact too long for that is split into two bullets rather than left to wrap. A fact SHALL NOT
be packed into a `;`-joined list. A name a reader may copy SHALL be a whole identifier in a
code span, MUST NOT be truncated in the middle, and MUST NOT be pasted whole above
roughly 40 characters — such an identifier SHALL be named as its object and its namespace.

#### Scenario: A long identifier
- **WHEN** an identifier is longer than a reader can scan on one line
- **THEN** it is written as the object and its namespace
- **AND** it is never shortened with an ellipsis

#### Scenario: A section holding several facts
- **WHEN** a section reports more than one fact
- **THEN** each fact is its own bullet
- **AND** no bullet runs past two rendered lines

#### Scenario: A section holding one fact
- **WHEN** a section reports a single fact
- **THEN** it is still one bullet under its heading, not an inline label
- **AND** `Status` remains the only label a sentence sits on

### Requirement: A gap is a footnote, not a clause in the outcome

A report SHALL state the outcome in its `Status` line and SHALL NOT put a failed check or a
figure no tool answered in that sentence. A report that carries such a gap SHALL end the
`Status` line with `(*)` and list every gap once, in one footnote block after its last
section. A failed check SHALL carry the literal `ERROR:` in that footnote, which is what
determines the report's error verdict. The footnote SHALL NOT be counted as content of the
section above it. A report with no gap MUST NOT carry the marker or a footnote block.

#### Scenario: A check failed
- **WHEN** a tool call fails or a figure is unavailable
- **THEN** the Status line names only the outcome and ends with `(*)`
- **AND** the footnote names the failing check with `ERROR:`
- **AND** the report posts with the error verdict

#### Scenario: No gap
- **WHEN** every check answered
- **THEN** the report carries no `(*)` marker and no footnote

### Requirement: Every section label a prompt writes is one the delivery hook classifies

The delivery hook derives a report's verdict from its `Status` line and from a fixed set of
finding section labels. Every label a reporting persona's format names SHALL be known to the
hook as `Status`, a finding section or a clean-only section, and a finding label MUST NOT be
renamed or invented in a prompt. This SHALL be held by a test over the committed prompts.

#### Scenario: A persona invents a section
- **WHEN** a prompt names a section the hook does not know
- **THEN** the test fails, naming the prompt and the label

#### Scenario: A finding section is renamed
- **WHEN** a prompt moves a finding to a label the hook does not treat as a finding
- **THEN** the test fails, because the report would post with a clean verdict
