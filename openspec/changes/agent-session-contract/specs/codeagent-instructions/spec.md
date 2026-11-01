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

### Requirement: The agent opens the pull request it is ready to review

The agent SHALL push a branch it created and SHALL open the pull request with the
GitHub credential the Pod already holds. It SHALL NOT push to `main`, force-push,
merge, or open a pull request without the repository's gate having passed. It SHALL
NOT mention the owner and SHALL NOT request review: Hermes sees the pull request,
requests the owner's review and posts the notification, so the owner is paged once,
from one place.

#### Scenario: The gate passes

- **WHEN** the repository's own checks pass on the branch
- **THEN** the agent opens the pull request with the checks and their result in the body

#### Scenario: The gate fails

- **WHEN** a check fails and the agent cannot fix it within the task
- **THEN** no pull request is opened as ready
- **AND** the report names the failing check and its output

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

### Requirement: A session that starts inside a checkout uses it

When the session's working directory is already a checkout of the repository the
issue names, the agent SHALL work in it and SHALL NOT clone a second copy inside it.
When the directory belongs to another repository, the agent SHALL leave it and clone
the named one under the workspace root.

#### Scenario: The session starts in the right checkout

- **WHEN** `git remote -v` in the working directory names the repository the issue names
- **THEN** the agent fetches and cuts the branch there
- **AND** it does not create a nested clone

#### Scenario: The session starts in another repository's checkout

- **WHEN** the working directory belongs to a different repository
- **THEN** the agent clones the named repository under the workspace root
- **AND** it leaves the current checkout untouched

### Requirement: One router skill, loaded first, maps a moment to one skill

The always-loaded contract SHALL state the role, the boundaries, the report shape
and the two rules that hold before any skill is loaded, and SHALL name the `router`
skill as the first thing to load. The router SHALL map each moment to exactly one
skill: `repo-map` before choosing a repository, `taskboard` for the task,
`code-shape` before editing, `testing` for a test, `debugging` for a failure,
`change-shape` for a commit, `ship-it` before the pull request, `verify` before a
completion claim. Each skill SHALL cover one moment, so a session loads the two or
three it needs and not the rest, and no rule SHALL be stated in two skills.

#### Scenario: A session reads one file and answers

- **WHEN** the task needs no edit
- **THEN** the contract alone is enough
- **AND** no practice skill is loaded

#### Scenario: A session starts

- **WHEN** a session needs to do more than answer a question
- **THEN** the agent loads `router` before any other skill
- **AND** it loads only the skills the current moment names

#### Scenario: A session fixes a failing test

- **WHEN** the agent is investigating a failure
- **THEN** it loads `debugging`
- **AND** it does not load `ship-it` or `change-shape` before it has a cause

#### Scenario: A practice appears in two skills

- **WHEN** a rule would be stated in two skills
- **THEN** one owns it and the other points at it

### Requirement: The smallest change that works is the default

The agent SHALL prefer deletion to addition, SHALL reuse an existing pattern before
creating a second one, and SHALL NOT rewrite working code to improve it, add a
speculative abstraction, add a dependency or config knob the repository already
covers, add a compatibility shim, or make a change outside the issue without
reporting it as its own issue.

#### Scenario: A helper already does the job

- **WHEN** the repository already has a function or pattern for the task
- **THEN** the agent uses it instead of writing a second one

#### Scenario: A working module looks improvable

- **WHEN** a refactor is unrelated to the issue
- **THEN** the agent leaves it and names it in the report

### Requirement: Tests cover behaviour, never configuration

A test SHALL assert what the code does, SHALL fail without the change, and SHALL NOT
assert a YAML value, a chart option, a prompt's wording or a file's presence. The
agent SHALL run the gate the repository's own `AGENTS.md` names, and SHALL NOT make
a gate pass by skipping a test, widening a lint rule or loosening an assertion.

#### Scenario: A rule file changes

- **WHEN** the change is to instructions, documentation or configuration
- **THEN** no test asserts their wording
- **AND** the repository's render or build gate is the check

#### Scenario: A test is red

- **WHEN** the gate fails
- **THEN** the agent fixes or reports it
- **AND** it does not skip, relax or delete the failing check

### Requirement: The agent never destroys work it did not write

The agent SHALL treat uncommitted edits, stashes, untracked files and branches it
did not create as the owner's, and SHALL ask before any reset, clean, checkout or
branch deletion that would discard them.

#### Scenario: The tree is dirty

- **WHEN** the working tree has changes the agent did not make
- **THEN** the agent leaves them in place
- **AND** it stages only the paths it touched

### Requirement: A merged pull request is not a deployed change

The agent's report SHALL state which part landed: code merged, image rebuilt, digest
re-pinned, or workload synced, and SHALL NOT claim a step it did not observe.

#### Scenario: Only the code landed

- **WHEN** the pull request is merged but the image is not rebuilt
- **THEN** the report says the new code is not running yet
