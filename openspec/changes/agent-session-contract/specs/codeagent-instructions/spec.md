# Spec Delta

## MODIFIED Requirements

### Requirement: The taskboard is a central issue and the pull request links it

Work SHALL be tracked as a GitHub issue in `datahub-local/datahub-local`. The agent
SHALL read the issue named in the session prompt before coding, SHALL work one
issue per branch, and SHALL open the pull request in the repository that holds the
change. The pull request body SHALL carry `Refs datahub-local/datahub-local#<n>`.
When the owner asks for work in the browser and no issue exists, the agent SHALL
create one before starting. The agent SHALL NOT change Project board status, SHALL
NOT call the Projects API, and SHALL end every comment it writes on an issue with
`<!-- taskboard:agent -->`, because its token posts under the owner's name.

#### Scenario: A dispatched session starts

- **WHEN** the prompt names an issue
- **THEN** the agent reads the issue and its comments before touching a file
- **AND** it comments once that work started, with the branch name and the marker

#### Scenario: A task arrives as a chat prompt

- **WHEN** the agent is asked for work in the browser and no issue exists
- **THEN** it creates the issue with the what, the why, the acceptance and the repository
- **AND** the work proceeds against that issue

#### Scenario: The change lands in another repository

- **WHEN** the pull request is in a repository other than the taskboard
- **THEN** the body carries the `Refs` line and not `Closes`
- **AND** the issue records the pull request URL

#### Scenario: A status looks like the agent's to change

- **WHEN** the work reaches a state that has a board status
- **THEN** the agent comments the evidence and leaves the card alone
- **AND** Hermes, which owns the board, moves it

## ADDED Requirements

### Requirement: A decision the owner must make is asked once

When a decision is the owner's, the agent SHALL call the `question` tool once, with
concrete options and a recommendation, and SHALL end the turn. It SHALL NOT guess,
SHALL NOT pick a default, and SHALL NOT wait inside a shell prompt. The answer
SHALL arrive as the next prompt in the same session.

#### Scenario: Two repositories could hold the change

- **WHEN** the issue does not say which repository owns the change
- **THEN** the agent asks with the candidates as options
- **AND** it stops until the answer arrives

#### Scenario: The owner answers

- **WHEN** a later prompt carries the answer
- **THEN** the agent continues the same task without re-asking
