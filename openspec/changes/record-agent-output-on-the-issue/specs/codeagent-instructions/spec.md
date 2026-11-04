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

### Requirement: A fix on an open pull request is reported on the issue

When the agent changes code on a branch whose pull request is already open, because
the owner asked, a review found something, or the gate failed, it SHALL push to
that branch and SHALL comment the issue once per round with what changed and the
gate result. The comment SHALL carry the `<!-- taskboard:agent -->` marker. A merged
pull request SHALL NOT be pushed to: a later change SHALL start a new branch from
`main` and a new pull request.

#### Scenario: The owner asks for a fix

- **WHEN** the owner's comment reaches the session while its pull request is open
- **THEN** the agent pushes the fix to the same branch
- **AND** it comments the issue with what changed and the gate result

#### Scenario: A review finding is fixed

- **WHEN** the agent fixes a finding the reviewer raised
- **THEN** it re-runs the gate and pushes
- **AND** the issue gets the same one-comment report, not a second review request

#### Scenario: The pull request already merged

- **WHEN** the owner asks for more after the merge
- **THEN** the agent cuts a new branch from `main`
- **AND** it opens a new pull request that references the issue

### Requirement: A decision made in the web UI is recorded on the issue

When the `question` tool returns an answer, the agent SHALL comment the issue with
the question and the answer before continuing, because that answer may never have
reached the issue. When the answer arrives as a prompt, it was relayed from the
issue or Slack, and the agent SHALL NOT repeat it. The comment SHALL carry the
`<!-- taskboard:agent -->` marker.

#### Scenario: The owner picks an option in the web UI

- **WHEN** the question tool returns the chosen option
- **THEN** the agent comments the issue with the question and the answer
- **AND** it continues the turn without waiting for Hermes

#### Scenario: The owner answers on the issue

- **WHEN** the answer arrives as `The owner wrote: …`
- **THEN** the agent does not post a second copy of the decision

