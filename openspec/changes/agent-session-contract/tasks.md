# Tasks

- [x] 1.1 Rewrite the `## Taskboard` section of `agents/adapters/opencode/AGENTS.md`:
  the board has one writer and it is Hermes, the session prompt names the issue,
  every machine comment carries `<!-- taskboard:agent -->`.
- [x] 1.2 Add `## How work arrives` and `## Asking the owner` to the same file.
- [x] 1.3 Rewrite `agents/adapters/opencode/skills/taskboard/SKILL.md` to match: no
  Projects API, no `status:*` labels, marker on every comment, the agent opens the
  pull request, the owner is never paged by the agent.
- [x] 1.4 `openspec validate --all` passes.
- [x] 1.3a Add `skills/practices/SKILL.md`: the shape of a change, tests, debugging,
  git, comments and docs, the pre-pull-request read-through, and the checkpoint
  rule. Keep `AGENTS.md` a router: four non-negotiables plus a pointer.
- [x] 1.3c Assert the new skill in the Dockerfile and list it in the adapter README.
- [x] 1.3b Add the "start inside a checkout" rule to the taskboard skill: reuse the
  working directory when it is the named repository, never clone inside it.
- [ ] 1.5 Publish a new adapter image and re-pin its digest in
  `datahub-local-core/values/_version.yaml`.
- [ ] 1.6 Confirm inside the live Pod that `/opt/opencode/AGENTS.md` and
  `/opt/opencode/skills/taskboard/SKILL.md` are the new text.
