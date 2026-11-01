# Proposal

## Why

The coding agent that works these repositories is governed by a 33-line
`agents/adapters/opencode/AGENTS.md` baked into its image. It names three rules
(work inside `/workspace`, use the toolchain, create a branch) and no contract:
nothing says which repository owns which concern, how work is tracked, what the
agent may not touch, how a task arrives from Hermes, or how the result is
reported back.

It is also wrong in one place, and the wrongness is load-bearing. It says *"Do
not open pull requests: this container has no GitHub token, and the caller opens
the PR through the GitHub MCP server."* Read off the running Pod on 2026-11-01:
`GITHUB_TOKEN` is set and `gh 2.103.3` is installed and authenticated by the same
helper. The rule survives on a reason that stopped being true when the token path
landed, so the agent is told to stop one step short of a pull request for no
reason at all.

Four things are missing, and each one has a cost measured elsewhere in this
repository:

- **A repository map.** The agent is asked to improve "the datahub-local repos"
  and has no statement of what each one is. The fleet already learned this
  lesson: a wrong name fails silently, and a guessed repository is the same
  failure one level up.
- **A taskboard.** Work arrives as a chat prompt from Hermes and leaves as a
  branch. Nothing links the two, so a session that ends is a task that cannot be
  found again.
- **A boundary.** `datahub-local-secrets` and `datahub-local-private-config` are
  private repositories the Pod's token can reach. Nothing in the current file
  says they are out of scope, and nothing says bootstrap is applied by a person
  on the homelab machine rather than by the agent.
- **The verification contract.** "Report what you changed" is not a gate. The
  repository already requires a test that fails without the change and a lint and
  typecheck run before "done"; the agent is not told that, so it cannot comply.

There is a second, larger file: `datahub-local-ai/AGENTS.md` is **2,157 lines**
and OpenCode loads it whole on every session started in this repository. That is
the repository's accumulated operational knowledge, and it is genuinely needed
when editing n8n exports. It is not needed when editing a dbt model, and it is
charged to every session either way.

## What Changes

- **`agents/adapters/opencode/AGENTS.md` becomes a contract, not a note.** About
  80 lines: who decides what (Hermes orchestrates, the agent implements), the
  precedence of sources, the repository map, the taskboard flow, hard boundaries,
  MCP-before-shell, the verification rule and the report shape. The false GitHub
  token sentence is deleted.
- **Cross-repository detail moves into four skills** under
  `agents/adapters/opencode/skills/`, baked at `/opt/opencode/skills` and
  registered through `skills.paths` in the image's `opencode.json`:
  `repo-map`, `taskboard`, `verify`, `change-shape`. Loaded on demand, so the
  cost is paid by the task that needs it.
- **The k8s MCP server is registered.** The Pod has no route to the Kubernetes
  API (the egress policy admits DNS, LiteLLM, `mcpserver` pods on 8080 and the
  proxy, nothing else), so `kubectl` in the image is inert. The read-only
  `k8s_*` server is the only way for the agent to see the cluster it changed.
  It is a config change, not a network change: the policy already admits the
  `mcpserver` pods.
- **Permissions state the boundaries the prose states.** `curl` and `wget` are
  denied so the web surface stays Firecrawl, and credential-shaped paths are
  unreadable.
- **`datahub-local-core` and `datahub-local` gain an `AGENTS.md`.** Both ship
  only `CLAUDE.md` today, which OpenCode reads as a fallback and which loses to
  any `AGENTS.md`. The content is kept, the canonical name becomes `AGENTS.md`
  and `CLAUDE.md` points at it, so one file serves both readers.
- **`datahub-local-ai/AGENTS.md` is split.** The n8n, MCP-server and Sympozium
  sections move verbatim into `docs/agent/`, the root file keeps the rules that
  apply to every sub-project and gains an imperative pointer to the deep dive
  that matches the path being edited.

## Capabilities

### New Capabilities

- `codeagent-instructions`: what the coding agent is told, where that text
  lives, how it is loaded, and which boundaries and permissions enforce it.

### Modified Capabilities

None. No runtime behaviour of a pipeline, a dashboard or an agent fleet changes.

## Impact

- `datahub-local-ai`: the adapter (`AGENTS.md`, `skills/`, `opencode.json`,
  `Dockerfile`, `README.md`) and this repository's own `AGENTS.md` split into
  `docs/agent/`. No test is added: a unit test over prompt text pins its wording,
  so every legitimate rewrite fails it.
- `datahub-local-core`: `OPENCODE_K8S_MCP_URL` on the opencode server, and
  `AGENTS.md` renamed from `CLAUDE.md`.
- `datahub-local`: `AGENTS.md` renamed from `CLAUDE.md`, plus the taskboard
  convention at the top of it.
- The image must be rebuilt and its digest re-pinned before any of this reaches
  the running agent; the rules are baked, so merging the repository alone changes
  nothing live. That is the same rebuild path every adapter change already takes.

## Non-goals

- Registering the GitHub MCP server. `gh` and `git` are the repository path and
  already authenticated; the server's ~40 tool schemas are a large permanent
  context cost for a surface the shell already covers.
- Registering every namespace MCP server. `argocd`, `grafana`, `postgres`,
  `trino` and `slack` answer questions this agent is not asked, and each one
  charges its schemas to every call.
- Giving the agent a route to the cluster or the public internet. The isolation
  is the design; MCP is how work crosses it.
- Any write action on the homelab. Bootstrap and cluster changes stay with the
  owner.
