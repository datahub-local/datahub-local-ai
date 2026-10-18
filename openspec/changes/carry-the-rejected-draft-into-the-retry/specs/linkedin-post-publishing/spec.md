# Spec Delta

## ADDED Requirements

### Requirement: A rejected post is carried into the retry

A rejected post SHALL be passed back to the drafting pass that regenerates it, so the retry edits
the post the review just rejected rather than writing a new one from nothing. The retry SHALL carry
the most recent attempt's post and not an earlier one, and SHALL render an empty block on the first
attempt.

#### Scenario: The retry edits the rejected post

- **WHEN** the review rejects a post and the drafting prompt is rendered again
- **THEN** the prompt carries the post that was just rejected
- **AND** the drafting rules ask for that post to be edited rather than replaced

#### Scenario: A third attempt edits the second post

- **WHEN** a run reaches a second retry
- **THEN** the prompt carries the most recent rejected post
- **AND** it does not carry the first attempt's post

#### Scenario: The first attempt carries no post

- **WHEN** the drafting prompt is rendered for the first attempt
- **THEN** the previous-post block is empty
- **AND** the drafting rules are not told to edit a post that does not exist
