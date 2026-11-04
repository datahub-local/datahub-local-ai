# Proposal

## Why

The issue is the record the owner reads, but a fix round leaves no trace there. The
agent pushes to the pull request, replies in the session, and the only comment on
the issue is the tick's pull-request announcement, which the agent never writes
again. On #99 the owner asked for a change, the agent pushed a fix, and the issue
sat unchanged until the owner asked whether anything had happened.

The detail belongs on the pull request, where the reviewer reads it. What the owner
needs on the issue is one short line: what changed, and that the gate still passes.

The same hole swallows a decision. The tick publishes a `needs_input` question on
its next poll, but the owner can answer in the web UI before that poll runs. The
question then never reaches the issue, and the answer only exists in the session.
That happened on #99: the agent asked what the owner saw, the owner answered in the
UI, and the issue thread showed neither.

## What Changes

- The `taskboard` skill gains a section for a fix on an open pull request: push to
  the same branch, then comment the issue with what changed and the gate result,
  marked `<!-- taskboard:agent -->`.
- The `review` skill says the same after acting on review findings, so both routes
  into an open pull request report the same way.
- An answer picked in the web UI is recorded on the issue by the agent, because the
  tick only publishes questions it polls before the answer arrives.
- The tick stops re-posting the pull request URL when the card returns to review:
  a fix on an already-announced pull request is reported by the agent's comment,
  not by a second copy of the URL.

Not changed: the tick still announces a new pull request, and still moves the card
to `Code Review` after a fix.

## Impact

- `agents/adapters/opencode/skills/taskboard/SKILL.md`
- `agents/adapters/opencode/skills/review/SKILL.md`
- `openspec/specs/codeagent-instructions/spec.md`
- `datahub-local-core`: `releases/automation/files/agent/taskboard-loop/SKILL.md`
