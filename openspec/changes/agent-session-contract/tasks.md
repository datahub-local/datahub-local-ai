# Tasks

- [x] 1.1 Rewrite the `## Taskboard` section of `agents/adapters/opencode/AGENTS.md`:
  the board has one writer and it is Hermes, the session prompt names the issue,
  every machine comment carries `<!-- taskboard:agent -->`.
- [x] 1.2 Add `## How work arrives` and `## Asking the owner` to the same file.
- [x] 1.3 Rewrite `agents/adapters/opencode/skills/taskboard/SKILL.md` to match: no
  Projects API, no `status:*` labels, marker on every comment, the agent opens the
  pull request, the owner is never paged by the agent.
- [ ] 1.4 `openspec validate --all` passes.
- [ ] 1.5 Publish a new adapter image and re-pin its digest in
  `datahub-local-core/values/_version.yaml`.
- [ ] 1.6 Confirm inside the live Pod that `/opt/opencode/AGENTS.md` and
  `/opt/opencode/skills/taskboard/SKILL.md` are the new text.
