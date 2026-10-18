# Spec Delta

## ADDED Requirements

### Requirement: A human retry is handed the post the human rejected

When a person asks for changes to a post they read, the drafting pass that regenerates it SHALL
receive the post they were reading, so the change is an edit rather than a new post. The post SHALL
be the one that was on screen when the feedback was written and not an earlier round's, the first
pass SHALL send none, and the pass SHALL prefer a post rejected inside the same invocation over the
caller's. The post lane stores no draft of its own, so the post SHALL travel in the run.

#### Scenario: A human asks for a change to the post

- **WHEN** a person answers the approval with feedback and the graph re-enters the drafting
  sub-workflow
- **THEN** the drafting prompt carries the post they were reading
- **AND** the parts of it the feedback does not name are kept

#### Scenario: A third round edits the second post

- **WHEN** a post is sent for review a second time and rejected again
- **THEN** the drafting prompt carries the most recently reviewed post
- **AND** it does not carry the first round's post

#### Scenario: The first authoring sends nothing

- **WHEN** the drafting sub-workflow is called for the first time in a run
- **THEN** no previous post is passed
- **AND** the prompt's previous-post block is empty
