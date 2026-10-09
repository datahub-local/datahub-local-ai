# Spec Delta

## Purpose

The scheduled pipeline that turns a queued source article into a published LinkedIn post, and specifically the internal review gate that decides whether a generated draft may go on to human review: which rules it may reject on, how a rejected draft is regenerated, how many attempts it is given, and how a gate failure is recorded and reported.

## ADDED Requirements

### Requirement: Every rejection reason is a rule a compliant draft can satisfy

The gate's compliance rules and the drafting rules SHALL be jointly satisfiable for every source. A rule MUST NOT reject a draft for using a word that another rule requires the draft to contain. In particular, the AI-speak rule SHALL apply to a listed word in its hype usage, and MUST NOT reject a draft that uses the word as the name of the technology, component or product the draft is about.

#### Scenario: Listed word is the subject of the draft

- **WHEN** the source content is about a component the drafting rules require the draft to name, and that component's name is on the AI-speak list
- **THEN** the gate does not reject the draft on the AI-speak rule
- **AND** the draft proceeds to the remaining checks

#### Scenario: Listed word is used as hype

- **WHEN** a draft uses a listed word as filler or hype rather than as the name of its subject
- **THEN** the gate rejects the draft on the AI-speak rule
- **AND** its explanation names the word

### Requirement: A rejected draft is regenerated from the rejection reason

When the gate rejects a draft, the next attempt SHALL be produced from a prompt that includes the gate's explanation of that rejection, and MUST NOT be a resampling of the unchanged prompt. The first attempt for an entry carries no gate explanation.

#### Scenario: Second attempt applies the rejection reason

- **WHEN** the gate rejects a draft with an explanation
- **THEN** the next attempt's instructions include that explanation
- **AND** the next attempt is submitted to the gate again

#### Scenario: First attempt

- **WHEN** no draft has been submitted yet for the entry
- **THEN** the drafting instructions carry author-supplied feedback only

#### Scenario: Author feedback and gate feedback are both present

- **WHEN** a submission carries human feedback for the entry and the gate has rejected a previous attempt
- **THEN** the next attempt's instructions carry both, and the human feedback keeps its precedence

#### Scenario: Rejected for a reason the explanation cannot fix

- **WHEN** every attempt is rejected for the same reason
- **THEN** the pipeline stops on the attempt bound rather than repeating attempts indefinitely

### Requirement: The attempt bound counts drafts

The pipeline SHALL produce at most `MAX_TRIES` drafts for one entry, where `MAX_TRIES` is the configured maximum number of drafts. A rejected final attempt SHALL end the run as a gate failure without producing a further draft.

#### Scenario: Bound reached

- **WHEN** the gate rejects the `MAX_TRIES`-th draft
- **THEN** no further draft is produced
- **AND** the run ends as a gate failure

#### Scenario: Accepted before the bound

- **WHEN** the gate accepts a draft before the bound is reached
- **THEN** no further draft is produced
- **AND** the accepted draft is returned as the run's result

#### Scenario: Review disabled for a call

- **WHEN** the caller disables the internal review
- **THEN** the first draft is returned without any gate call

### Requirement: A gate failure names its reason and reaches a human

A run that ends without an accepted draft SHALL publish nothing, SHALL record an error state on the queue row carrying the gate's reason for the final rejection, and SHALL send a notification that names both the article and that reason. A generic marker that discards the reason MUST NOT be recorded or reported in place of it.

#### Scenario: Gate failure is recorded

- **WHEN** the run ends as a gate failure
- **THEN** the queue row's state is an error state
- **AND** the recorded reason identifies the failure and carries the gate's explanation for the final rejection

#### Scenario: Gate failure is reported

- **WHEN** the run ends as a gate failure
- **THEN** a notification is delivered naming the article the run was working on and the reason
- **AND** no post is published

#### Scenario: Nothing is published on any failed run

- **WHEN** any step of the run fails
- **THEN** no post is published to LinkedIn
- **AND** the failure reaches a human
