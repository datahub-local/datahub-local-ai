# Tasks

## 1. The contract

- [x] 1.1 Rewrite `agents/adapters/opencode/AGENTS.md` as the short contract (106
  lines, and the adapter test fails above 120):
  role and decision rights, source precedence, repository map summary, taskboard
  flow, hard boundaries, MCP-before-shell, verification, writing, report shape
- [x] 1.2 Delete the false "this container has no GitHub token" sentence and
  state that the agent opens the pull request with `gh`
- [x] 1.3 Name both private repositories and the bootstrap rule in the contract
  itself, not only in a skill, because a boundary that is loaded on demand is not
  a boundary

## 2. The skills

- [x] 2.1 `skills/repo-map/SKILL.md`: the fifteen public repositories, which one
  owns which concern, and where to read first
- [x] 2.2 `skills/taskboard/SKILL.md`: issue in `datahub-local/datahub-local`,
  branch naming, `Refs` line, labels, when to mention `@alvsanand`, the `gh`
  commands
- [x] 2.3 `skills/verify/SKILL.md`: the gate command per repository, including
  the checks the Pod cannot run
- [x] 2.4 `skills/change-shape/SKILL.md`: OpenSpec threshold, commit scopes,
  comment rules, PR body

## 3. The config and the image

- [x] 3.1 Register the k8s MCP server through `{env:OPENCODE_K8S_MCP_URL}` in
  `agents/adapters/opencode/opencode.json`
- [x] 3.2 Add `skills.paths: ["/opt/opencode/skills"]` to the same file
- [x] 3.3 Deny `curl` and `wget` in the `bash` permission rules, and deny reads
  of credential-shaped paths
- [x] 3.4 `COPY` the skills into `/opt/opencode/skills` in the Dockerfile and
  assert one of them exists at build time
- [x] 3.5 Remove the dead `skills.paths` entry from this repository's
  `opencode.json` (it points at `.claude/skills`, which does not exist here)
- [x] 3.6 Update `agents/adapters/opencode/README.md` with the new file table

## 4. The test (dropped)

- [x] 4.1 A unit test over the rule files was written and removed on the owner's
  call. It asserted skill frontmatter, the skill names in the contract,
  env-substituted MCP URLs, the denied permissions, the private-repository names
  and the absence of an em dash. Every one of those is a property of prompt text:
  a legitimate rewording of a rule fails it, which makes the test a second copy of
  the wording rather than a check on behaviour. The rules are reviewed, and the
  Dockerfile asserts the one fact a broken file would otherwise hide (the config
  parses, the skills path is registered, a skill exists at the baked path).
- [x] 4.2 No `Test Agents` job was added. The workflow is unchanged.

## 5. The repositories around it

- [x] 5.1 `datahub-local-core`: rename `CLAUDE.md` to `AGENTS.md`, leave
  `CLAUDE.md` as a symlink, add the repository identity and the render gate at the
  top
- [x] 5.2 `datahub-local-core`: add `OPENCODE_K8S_MCP_URL` to the opencode
  server's environment
- [x] 5.3 `datahub-local`: rename `CLAUDE.md` to `AGENTS.md`, leave `CLAUDE.md`
  as a symlink, add the repository identity, the site gate and the taskboard
  convention
- [x] 5.4 `datahub-local-ai`: move the n8n, MCP-server and Sympozium sections
  verbatim into `docs/agent/`, shift headings one level, and replace them in the
  root file with an imperative pointer table
- [x] 5.5 Confirm the root file is under 300 lines and every moved section is
  reachable from it

## 6. Gates

- [x] 6.1 No unit test to run; the Dockerfile assertions run at image build
- [x] 6.2 `openspec validate --all` in `datahub-local-ai`
- [x] 6.3 `uv run ruff check` on the touched sub-projects: no Python file changed
- [x] 6.4 `helmfile template` in `datahub-local-core/releases/automation`: the
  opencode release renders with the new env var. The full file needs a working OCI
  credential helper, which this machine lacks
- [ ] 6.5 Rebuild and re-pin the adapter digest in `datahub-local-core`, then
  confirm the live Pod answers the new rule count. This is the deployment half,
  tracked as `datahub-local/datahub-local#114`; the live Pod keeps the old rules
  until it lands
