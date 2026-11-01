# Spec Delta

## Purpose

What the coding agent is told, where that text lives, how it is loaded, and which
boundaries and permissions enforce it.

## ADDED Requirements

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
SHALL read the issue before coding, SHALL work one issue per branch, and SHALL open
the pull request in the repository that holds the change. The pull request body
SHALL carry `Refs datahub-local/datahub-local#<n>`. When no issue exists for an
arriving task, the agent SHALL create one before starting.

#### Scenario: A task arrives as a chat prompt
- **WHEN** Hermes calls the agent with work that has no issue
- **THEN** the agent creates the issue with the what, the why and the repository it touches
- **AND** the work proceeds against that issue

#### Scenario: The change lands in another repository
- **WHEN** the pull request is in a repository other than the taskboard
- **THEN** the body carries the `Refs` line and not `Closes`
- **AND** the issue records the pull request URL

### Requirement: The agent opens the pull request it is ready to review

The agent SHALL push a branch it created and SHALL open the pull request with the
GitHub credential the Pod already holds. It SHALL NOT push to `main`, force-push,
merge, or open a pull request without the repository's gate having passed. The
owner SHALL be mentioned once, in the pull request, and not per commit.

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
