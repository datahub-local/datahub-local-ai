# Tasks

- [x] 1.1 Rewrite the `## Taskboard` section of `agents/adapters/opencode/AGENTS.md`:
  the board has one writer and it is Hermes, the session prompt names the issue,
  every machine comment carries `<!-- taskboard:agent -->`.
- [x] 1.2 Add `## How work arrives` and `## Asking the owner` to the same file.
- [x] 1.3 Rewrite `agents/adapters/opencode/skills/taskboard/SKILL.md` to match: no
  Projects API, no `status:*` labels, marker on every comment, the agent opens the
  pull request, the owner is never paged by the agent.
- [x] 1.4 `openspec validate --all` passes.
- [x] 1.3a Add four skills split by moment: `code-shape`, `testing`, `debugging`
  and `ship-it`. No skill restates another; the format and per-repo comment rules
  stay in `change-shape`, the gate commands in `verify`, the lifecycle in
  `taskboard`.
- [x] 1.3c Add a `router` skill: the moment-to-skill table, the load-when-the-moment-
  arrives rule, the disagreement order, and the skill-authoring rule.
- [x] 1.3f Sharpen the OpenSpec trigger in `change-shape` (a documented capability
  needs a delta; a fix does not) and add `openspec validate --all` to the
  `datahub-local-core` and `datahub-local` gates in `verify`.
- [x] 1.3g Archive in the same branch: `change-shape` says when to run
  `openspec archive`, `ship-it` checks the delta is in the diff, and `AGENTS.md`
  places the capability spec below the code in the authority order.
- [x] 1.3e Turn `AGENTS.md` into a pointer: role, boundaries, report, the two rules
  that hold before a skill is loaded, and "load `router` first".
- [x] 1.3d Assert each new skill in the Dockerfile and list all of them in the
  adapter README, `router` first.
- [x] 1.3b Add the "start inside a checkout" rule to the taskboard skill: reuse the
  working directory when it is the named repository, never clone inside it.
- [x] 1.4b Add the `reviewer` subagent and the `review` skill: env-driven models,
  read-only reviewer, the review posted on the pull request, two rounds maximum.
- [ ] 1.5 Publish a new adapter image and re-pin its digest in
  `datahub-local-core/values/_version.yaml`.
- [ ] 1.6 Confirm inside the live Pod that `/opt/opencode/AGENTS.md` and
  `/opt/opencode/skills/taskboard/SKILL.md` are the new text.
