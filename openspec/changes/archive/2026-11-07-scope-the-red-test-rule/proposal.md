# Proposal

## Why

On 2026-11-07 the owner ruled that no unit test is created for an n8n workflow, and the
remaining `agents/n8n/scripts/test_*.py` were deleted. Two of those tests were red on `main` for
reasons unrelated to any pull request, so CI was red on every branch.

`openspec/specs/codeagent-instructions` says, in **A test is red**, that the agent "does not skip,
relax or delete the failing check". Read literally, the ordered removal is exactly the behaviour
that scenario forbids, so the next agent reading the spec would refuse a rule the owner set. The
same requirement's first paragraph already says a test SHALL NOT assert a YAML value, a chart
option, a prompt's wording or a file's presence; the scenario was written for a test that covers
behaviour and never said so.

## What Changes

- **The red-test scenario is scoped to behaviour.** It requires the agent to fix or report a red
  test that covers behaviour, and forbids skipping, relaxing or deleting that test.
- **A configuration test that is red is deleted with the rule that forbade it.** The new scenario
  says the build or the live run is the check the test was standing in for.
- The requirement text says which deletion is forbidden and which is the requirement's own
  conclusion.

## Capabilities

`codeagent-instructions`.

## Out of scope

- The n8n tests themselves and the CI job: that is `datahub-local/datahub-local#132`.
- Adapter tests: they cover code the image runs and are unaffected.
