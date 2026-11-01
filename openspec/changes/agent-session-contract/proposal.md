# Proposal

## Why

The adapter's `AGENTS.md` and `taskboard` skill describe a lone agent that finds its
own work. That stops being true now that Hermes dispatches issues from the Project
board: the prompt names an issue, the owner answers questions as issue comments,
and Hermes owns every status change. Nothing in the image says so, and two rules
contradict the new loop:

- the skill tells the agent to create an issue when none exists, which is wrong for
  a dispatched session;
- nothing says the agent must not touch the Projects API, so a model that reads
  "move it to Testing" in an issue would try and fail.

There is also a silent trap. The Pod uses the owner's PAT, so its comments appear
under the owner's name. Any later automation that distinguishes the owner from the
agent by author will answer itself. A marker is the only reliable discriminator,
and it has to be written by the agent, so it belongs in the rules shipped in the
image.

## What Changes

- `AGENTS.md` gains the session contract: the prompt names an issue, read it first,
  claim it with a marker, do the work, open the pull request, report; and the
  board is Hermes', not the agent's.
- `AGENTS.md` gains the help protocol: one `question` call with concrete options
  and end the turn, because the answer arrives as the next prompt in the same
  session.
- The `taskboard` skill drops the "create an issue from a chat prompt" path in
  favour of "create one only when the owner asks in the browser", states that only
  Hermes writes board state, and ends every machine comment with
  `<!-- taskboard:agent -->`.
- The pull request stays the agent's, which is what both files already said and
  what the image toolchain makes possible.

Not changed: the tool surface, the permissions, the model path, and the MCP
servers. This is a rules change, and the image is rebuilt only because the rules
ship inside it.

## Impact

- `agents/adapters/opencode/AGENTS.md` and
  `agents/adapters/opencode/skills/taskboard/SKILL.md`.
- A rebuilt `datahub-local-ai-opencode-adapter` digest, re-pinned in
  `datahub-local-core/values/_version.yaml`.
- No new test. The rule files have none by design (issue #113): a test that asserts
  their wording fails every legitimate rewrite, and the Dockerfile already asserts
  that each skill is present and readable.
