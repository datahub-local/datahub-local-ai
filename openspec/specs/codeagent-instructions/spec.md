# codeagent-instructions Specification

## Purpose
What the coding agent is told, where that text lives, how it is loaded, and which
boundaries and permissions enforce it.

## Requirements

### Requirement: The contract is always loaded and the detail is loaded on demand

The code agent SHALL receive a short contract on every turn and SHALL load the
detail through skills. The contract SHALL name the agent's role, the precedence
of its sources, the repository map, the taskboard flow, the hard boundaries, the
MCP-first rule, the verification rule and the report shape. Detail that applies
to one kind of task SHALL live in a skill, not in the contract.

The contract and the skills SHALL be part of the adapter image, because the state
volume hides anything baked under the home directory. A wording change therefore
takes effect on a rebuilt digest and not on a merge.

#### Scenario: A turn that needs no detail pays for no detail
- **WHEN** a session edits one file in one repository
- **THEN** the contract is in context and the skills it did not need are not
- **AND** the repository's own rule file is also in context

#### Scenario: A rule change reaches the agent only by rebuild
- **WHEN** the contract or a skill changes in the repository
- **THEN** the running Pod keeps the previous text until the image is rebuilt and its digest re-pinned

#### Scenario: Every skill is discoverable and well-formed
- **WHEN** the adapter is built or tested
- **THEN** each skill directory holds a `SKILL.md` whose `name` matches the directory and whose `description` is present
- **AND** the image's `skills.paths` names the directory that holds them

### Requirement: The agent's sources have a stated precedence

The contract SHALL state, in order, what wins when two sources disagree: the code
and its tests, the working repository's own rule file, the GitHub issue that
carries the task, and everything else as context. The agent SHALL stop and ask
rather than reconcile a disagreement by guessing.

#### Scenario: A repository rule contradicts the contract
- **WHEN** the working repository's rule file states something the contract does not
- **THEN** the repository rule governs the repository-specific detail
- **AND** a conflict over a boundary or the process is raised as a question

#### Scenario: The issue and the code disagree
- **WHEN** an issue describes behaviour the code does not have
- **THEN** the agent reports the mismatch instead of implementing either reading silently

### Requirement: The agent never reaches a private repository

The contract SHALL name `datahub-local-secrets` and `datahub-local-private-config`
as out of scope, and the agent SHALL NOT read, clone, reference or infer their
contents. The agent SHALL NOT run a bootstrap playbook or apply anything to the
homelab; a bootstrap change SHALL be proposed as a patch in an issue and applied
by the owner on the homelab machine. The agent SHALL NOT write a token, key,
credential file or `.netrc`, and credential-shaped paths SHALL be unreadable.

#### Scenario: A task needs a value that lives in the secrets repository
- **WHEN** a task cannot be completed without a value from a private repository
- **THEN** the agent asks for the single setting it needs and stops
- **AND** it does not read the repository to find it

#### Scenario: A task needs a host change
- **WHEN** a task requires a bootstrap playbook to run
- **THEN** the agent publishes the patch and the procedure in the issue
- **AND** it does not execute the playbook

### Requirement: Cluster and web access is MCP, and the shell cannot substitute

The agent SHALL reach the cluster through the read-only k8s MCP server and the web
through the Firecrawl MCP server. The contract SHALL state that `kubectl` has no
route or credential in the Pod, and the permission rules SHALL deny `curl` and
`wget`. The k8s server SHALL expose no write tool and SHALL NOT return Secrets.

#### Scenario: The agent inspects a workload it changed
- **WHEN** the agent reads a deployment, a pod or an event after a change
- **THEN** the answer comes from a `k8s_*` tool
- **AND** `kubectl` is not used as an alternative

#### Scenario: A page has to be read
- **WHEN** the agent needs the content of a URL
- **THEN** it uses a Firecrawl tool
- **AND** a `curl` or `wget` invocation is refused by the permission rules

#### Scenario: A cluster write is attempted
- **WHEN** the agent calls a mutating cluster operation
- **THEN** no such tool exists on the server and the call fails
- **AND** the agent reports the boundary instead of retrying through the shell

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

### Requirement: The agent verifies with the repository's own gate

The agent SHALL run the checks the working repository defines for itself and SHALL
report each command with its result. It SHALL NOT report success it did not
observe, and SHALL mark what it could not run `[UNVERIFIED]` with the reason.

#### Scenario: The Pod cannot run a check
- **WHEN** a gate needs the cluster or a tool the Pod cannot reach
- **THEN** the report names the check as `[UNVERIFIED]` and says who can run it

#### Scenario: A change ships without its test
- **WHEN** the agent changes behaviour and adds no test that would fail without it
- **THEN** the report states that the change has no test
- **AND** the pull request body says so

### Requirement: The agent's report is a fixed shape

The agent SHALL end every task with the same report: a status of `DONE`, `BLOCKED`
or `FAILED` with one sentence of reason, the repository, branch and pull request,
the changed files one line each, the checks and their results, and what it could
not verify or left out. It SHALL NOT paste diffs and SHALL NOT narrate the
process.

#### Scenario: A task ends
- **WHEN** the agent stops working on a task
- **THEN** the report carries the five parts in order
- **AND** Hermes can relay it to Slack without editing it

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
`change-shape` for a commit, `ship-it` before the pull request, `review` once the
pull request exists, `verify` before a completion claim. Each skill SHALL cover one
moment, so a session loads the two or three it needs and not the rest, and no rule
SHALL be stated in two skills.

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
a gate pass by skipping a test, widening a lint rule or loosening an assertion. A test
that asserts configuration SHALL be deleted with the rule that forbade it; deleting a
test that covers behaviour to make a gate pass remains forbidden.

#### Scenario: A rule file changes

- **WHEN** the change is to instructions, documentation or configuration
- **THEN** no test asserts their wording
- **AND** the repository's render or build gate is the check

#### Scenario: A test is red

- **WHEN** the gate fails on a test that asserts what the code does
- **THEN** the agent fixes or reports it
- **AND** it does not skip, relax or delete that test

#### Scenario: A configuration test is red

- **WHEN** a test asserts a prompt, a dataset, a config value or a committed workflow export
- **THEN** it is deleted with the rule that forbade the test
- **AND** the behaviour it was standing in for is checked by the build or the live run

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

### Requirement: A second model reviews the change before it is reported done

After the gate passes and the pull request exists, and before reporting `DONE`, the
agent SHALL invoke the `reviewer` subagent, which runs on a different model than the
one that wrote the change, and SHALL post its findings on the pull request verbatim.
The agent SHALL act on every finding, SHALL re-run the gate after fixing, and SHALL
review at most twice. A finding it rejects SHALL be answered with the reason, in the
report and on the pull request.

#### Scenario: The reviewer finds a blocking bug

- **WHEN** the review returns `VERDICT: changes-required`
- **THEN** the agent fixes the blocking findings, re-runs the gate and pushes
- **AND** it runs the reviewer once more

#### Scenario: The reviewer approves

- **WHEN** the review returns `VERDICT: approve`
- **THEN** the agent posts it and reports `DONE`
- **AND** it does not start a third round

#### Scenario: The agent disagrees with a finding

- **WHEN** the agent believes a finding is wrong
- **THEN** it says why on the pull request and in the report
- **AND** it does not silently ignore the finding

### Requirement: The two models are configuration, not code

The model that writes and the model that reviews SHALL come from environment
variables read by the image's config (`OPENCODE_MODEL`, `OPENCODE_REVIEW_MODEL`), so
changing either is a values change in `datahub-local-core` and a rollout, never an
image rebuild.

#### Scenario: The reviewer model changes

- **WHEN** `OPENCODE_REVIEW_MODEL` is set to another declared model
- **THEN** the next rollout reviews with it
- **AND** no image is rebuilt

### Requirement: A session is bounded to one issue and its context stays small

A session SHALL carry one issue. The agent SHALL NOT run a second issue in it and
SHALL read an n8n workflow as `structure` or `filtered`, never `full`, and SHALL
NOT re-fetch one already in context. The adapter SHALL expose MCP tools through
Code Mode and SHALL summarize in the background as the default compaction
threshold approaches. The reviewer subagent SHALL return at most five findings,
one line each.

#### Scenario: A second issue arrives in a live session

- **WHEN** a prompt names an issue other than the session's issue
- **THEN** the agent reports the mismatch and does not start that work
- **AND** Hermes dispatches it in a new session

#### Scenario: The agent needs a workflow definition

- **WHEN** an n8n tool can answer the question
- **THEN** the request uses `structure` or `filtered`
- **AND** a workflow already in context is not fetched again

#### Scenario: The session reaches the compaction threshold

- **WHEN** the estimated context nears the default threshold
- **THEN** the summary is produced in the background
- **AND** the turn does not wait for it

#### Scenario: The reviewer reports

- **WHEN** the review subagent finishes
- **THEN** it returns at most five one-line findings and a verdict

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
