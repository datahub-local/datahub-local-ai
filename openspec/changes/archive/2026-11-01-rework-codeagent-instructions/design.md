# Design

## Context

One long-lived OpenCode v2 server in `automation`, reachable from a browser
through oauth2-proxy and from Hermes through the `opencode` MCP shim. It carries
`GITHUB_TOKEN`, a full toolchain, and `/workspace` for checkouts. Hermes is a chat
agent with MCP clients and a Slack channel; the owner talks to Hermes, and Hermes
calls `run_task(prompt, directory?, session_id?, wait_seconds=120)`.

The instruction file is therefore read by a model that has no memory of the
conversation that produced the task, cannot see Slack, and cannot see the
cluster. Everything it needs must be in the text or in a tool.

Read off the running Pod on 2026-11-01: 33 lines in `/opt/opencode/AGENTS.md`,
`GITHUB_TOKEN` set, `gh 2.103.3`, one MCP server (`fc`), 12 permission rules.
The egress policy admits DNS, LiteLLM on 4000, every `mcpserver` pod on 8080, and
the `security` proxy on 3128. It does not admit the Kubernetes API server, so the
image's `kubectl` has no cluster to talk to.

## Decisions

### 1 — Three layers, and each one has a different lifetime

| Layer | Where | Changes when | Loaded |
| --- | --- | --- | --- |
| Contract | `/opt/opencode/AGENTS.md` | the agent's role changes | every turn |
| Skills | `/opt/opencode/skills/*/SKILL.md` | a workflow gains detail | on demand, by the `skill` tool |
| Repository rules | `<repo>/AGENTS.md` | that repository changes | every turn, for that repo only |

The first two are baked into the image, because the state volume is mounted over
`/opt/data` and anything under `$HOME` would be hidden. The cost is a rebuild and
a digest bump for a wording change, which is the path this repository already
takes for the adapter. A runtime fetch was rejected: it needs a bootstrap step
before the first turn, and it creates a second copy of the text that can drift
from the repository.

### 2 — The contract is a router; the skills carry the volume

OpenCode combines the baked `instructions` with the working repository's
`AGENTS.md` or `CLAUDE.md`. There is no override order between them, which means
the baked file cannot be enforced by precedence. It has to be short enough that a
repository rule never disagrees with it, and it has to name where the detail
lives.

The four skills are the detail:

- `repo-map`: what each of the fifteen public repositories is, which one owns a
  concern, and where to read first. This is the file that stops a plausible guess.
- `taskboard`: issue, branch, PR, labels, the `Refs` line, and when a mention of
  `@alvsanand` is warranted.
- `verify`: the gate command per repository, including the ones the agent cannot
  run from inside the cluster.
- `change-shape`: OpenSpec threshold, commit scopes, comment rules, PR body.

### 3 — The taskboard is central, the pull request is local

Issues live in `datahub-local/datahub-local` (the org's home repository): one
queue for Hermes to scan, one place a task exists, one place a session's outcome
is recorded. The pull request stays in the repository that holds the change,
because that is where review, CI and the merge happen. The link is a line in the
PR body, `Refs datahub-local/datahub-local#<n>`.

`Closes` is deliberately not used across repositories. GitHub only closes an issue
from a PR in the same repository, so a cross-repo `Closes` is a promise nothing
keeps. The agent comments the PR URL on the issue, and the issue is closed when
the work is merged and reported.

### 4 — The agent opens the pull request

`gh` is installed, authenticated by the credential helper, and the egress proxy
allowlists GitHub. The old rule to stop at a pushed branch was written when the
constant-credential path did not exist, and it is now a rule that costs a round
trip through Hermes for something the agent already holds the credential for.

Hermes still owns the words the owner reads: the PR is the record, the Slack
message is Hermes'.

### 5 — Cluster and web access are MCP, and that is enforced by the network

The Pod cannot reach the Kubernetes API and cannot reach the internet directly.
That is not a policy the prompt has to defend, it is the topology:

- `kubectl` has no credentials (`automountServiceAccountToken: false`) and no
  route. It is dead, so `k8s_*` is the only cluster surface.
- `curl` and `wget` would go through the proxy and reach only its allowlist, but
  they bypass Firecrawl's reviewed surface. The `bash` permission denies them so
  the rule is mechanical, not a sentence a model may skip.
- `git` and `gh` are the exception by design: repository work is the job.

The k8s server is registered with `toolsPrefix: k8s`, read-only RBAC
(`get/list/watch`) and a server-side deny list that removes `pods_exec`,
`pods_run`, `pods_delete`, `resources_create_or_update`, `resources_delete` and
`resources_scale`, plus Secret reads. The agent gets the cluster's state, not its
control plane.

The URL arrives as `OPENCODE_K8S_MCP_URL`, beside `OPENCODE_FIRECRAWL_MCP_URL`.
The image already refuses to bake a Service address; a second one does not get to
break that rule.

### 6 — Private repositories are named, not merely discouraged

`datahub-local-secrets` and `datahub-local-private-config` are private and the
Pod's token can reach them. A rule that says "be careful with secrets" is not a
boundary. The contract names both repositories and says never read, clone or
reference them; the failure mode is a session that stops and asks, which is the
correct outcome.

Bootstrap is the same shape. The agent may read `datahub-local-bootstrap`, may
propose a playbook change as a patch in an issue, and never runs a playbook:
applying it needs a person and a machine that is not in this cluster.

### 7 — The 2,157-line file is split by path, not by topic

`datahub-local-ai/AGENTS.md` holds four bodies of knowledge with different
audiences: repository-wide rules, n8n operations, the MCP servers, and the
Sympozium fleet. Only the first applies to every session.

The split moves whole sections, verbatim, into `docs/agent/{n8n,mcp-servers,
sympozium}.md` and leaves the root file with the rules plus a table of pointers.
The pointer is imperative and path-scoped ("before editing anything under
`agents/n8n/`, read ..."), because OpenCode reads one rule file per directory and
the agent works at the repository root, so a nested `AGENTS.md` would never be
loaded.

Headings shift one level so each moved document reads as a top-level file. No
sentence is rewritten in the move: this is a relocation, reviewable as such.

## Risks

- **The split loses a lesson.** Mitigated by moving verbatim and keeping every
  section present, only relocated. A reader diffs the old file against the union
  of the new ones.
- **The agent does not read the deep dive.** Mitigated by the imperative pointer
  and by the fact that the n8n rules are only needed when editing n8n, which is
  exactly when the path names it.
- **A skill goes stale against a repository.** Skills name commands, not
  versions; `verify` points at each repository's own documented gate. Nothing
  checks it automatically: a unit test over prompt text was written and dropped,
  because it pins the wording and fails every legitimate rewrite. Review is the
  gate, and the Dockerfile build is what catches a file that does not load.
- **Registering k8s raises schema cost on every call.** Accepted: it is the only
  cluster surface, and the server is read-only. It is the one server worth its
  tokens.
- **The image is baked, so the live agent keeps the old rules until the digest
  moves.** Stated in the tasks; the rebuild is the last step, not the first.

## Open questions

- Whether a repository-level `skills.paths` in a project `opencode.json` appends
  to the machine paths or replaces them. The one project config that carried the
  key (this repository) pointed at `.claude/skills`, which does not exist here, so
  it is removed rather than reasoned about. [UNVERIFIED]
- Whether `{env:...}` substitution applies to MCP `headers`, which is why the
  GitHub MCP server is a non-goal rather than a deferred item.

## Definition of done

- The contract, the four skills and the config are in the adapter image, the
  build asserts that the config parses and that a skill exists at the baked path,
  and no unit test pins the wording of the rules.
- `datahub-local-core` and `datahub-local` answer an `AGENTS.md` with the same
  content as their `CLAUDE.md`.
- `datahub-local-ai/AGENTS.md` is under 300 lines and every moved section is
  reachable from it.
- `openspec validate --all` passes in `datahub-local-ai`.
- The image digest is re-pinned in `datahub-local-core` and the live Pod answers
  the new rule count.
