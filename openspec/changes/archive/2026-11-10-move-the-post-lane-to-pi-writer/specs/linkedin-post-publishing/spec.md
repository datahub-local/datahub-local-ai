# Spec Delta

## ADDED Requirements

### Requirement: The post lane's model turns run in the writer session

The drafting turn and the review gate SHALL be session turns served by the `pi-writer` adapter, not
model nodes in the n8n workflow. The request SHALL name the post lane and the turn, and SHALL carry
the entry's values — source text, URL, post type, word range, extra rules, human feedback, the
previous post and the resolved hook opening — never prompt text.

#### Scenario: A first draft

- **WHEN** an entry reaches the drafting turn
- **THEN** the workflow posts the entry's fields to the writer session
- **AND** the session renders the post prompts from its own image and answers the draft text

#### Scenario: A caller from the old contract

- **WHEN** a request carries no lane
- **THEN** the session serves it as an article turn
- **AND** the existing article tasks and their prompts are unchanged

### Requirement: The writer session owns the post prompts

The post's drafting instructions, persona, rules, review checklist, variety option sets and AI-speak
list SHALL live in the adapter's image, and SHALL NOT be fetched by the workflow at run time. A draft
and its gate that share a rule SHALL read one copy of it.

#### Scenario: A rule shared by the drafter and the gate

- **WHEN** the AI-speak list or the subject/attribution rule changes
- **THEN** one edit in the adapter's prompt directory changes both turns
- **AND** the workflow carries no second copy

### Requirement: The writer session chooses the variety directives

The session SHALL choose one format, one length band and one closing from the weighted option sets,
SHALL format the row's hook opening into the directive block, and SHALL keep the chosen set for the
post so later turns of the same session read it. The length target SHALL fall inside the requested
minimum and maximum.

#### Scenario: A draft and its review

- **WHEN** the gate reviews a draft in the same session
- **THEN** it judges the directives the drafter was given
- **AND** it does not draw a second set

#### Scenario: A session with no stored directives

- **WHEN** the session directory no longer carries the chosen set
- **THEN** the session draws a set and records it

### Requirement: The gate's verdict and the retry contract are preserved

The review turn SHALL answer a pass or fail verdict with a short explanation, and the workflow SHALL
retry a rejected draft within the existing attempt bound, carrying that explanation into the next
draft's instructions. The gate SHALL remain conditional on the existing check flag.

#### Scenario: A rejected draft

- **WHEN** the gate rejects a draft with an explanation
- **THEN** the next attempt is produced from that explanation
- **AND** the attempt bound is unchanged

#### Scenario: The check is disabled

- **WHEN** the entry disables the check
- **THEN** the first draft proceeds without a review turn

### Requirement: The post session receives its source and fetches nothing

The post session SHALL have no research tools, no source allowlist and no outbound fetch path. The
source text SHALL arrive in the brief, because the post lane's material is already fetched and the
post adds no evidence of its own.

#### Scenario: A draft needs a page re-read

- **WHEN** the source text in the brief is judged insufficient by the model
- **THEN** it drafts from the material it was given
- **AND** it cannot reach the page or any other host

### Requirement: The creator's n8n contract is unchanged

The `LinkedIn Post Creator` sub-workflow SHALL keep its trigger inputs, its `MAX_TRIES` bound, its
`ENABLE_CHECK` gate, its answer (`text`, `omImage`) and its error path. The draft answer SHALL still
carry the post in an `<output>` block, and the review answer SHALL still carry `<output>` and
`<explanation>`, so the existing parsers and the publish path are unchanged.

#### Scenario: An approved post

- **WHEN** the gate passes a draft
- **THEN** the workflow returns the same `text` the publish path read before
- **AND** the source line is rewritten from the entry's URL as before
