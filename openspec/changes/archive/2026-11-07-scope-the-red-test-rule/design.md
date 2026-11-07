# Design

## Decision: the red-test rule protects behaviour tests, not configuration tests

The scenario exists so an agent cannot make a gate green by deleting the test that caught its
bug. That is a real failure mode and it stays forbidden. A test that asserts a prompt's wording, a
dataset's contents or a committed workflow export is a different object: the requirement's own
first paragraph forbids it, the repository removed its n8n guards on 2026-11-05, and the owner
removed the last three on 2026-11-07. Deleting such a test is the requirement being applied, not
the gate being gamed.

Rejected alternative: keep the broad wording and require a person to overrule the spec on every
removal. That is what happened here: a one-line owner instruction had to be reconciled against a
scenario that never distinguished the two kinds of test. The spec should say what it means.

## Decision: the scenario names both files

The repository rule lives in `datahub-local-ai/AGENTS.md`, and the agent contract lives in
`openspec/specs/codeagent-instructions`. They change together: the AGENTS rule names the files
(`agents/n8n/`), and the spec scenario says what happens when one of those tests is red. A reader
who starts from either one finds the other.

## Risk: a behaviour test is deleted and called configuration

The first paragraph defines configuration narrowly (a YAML value, a chart option, a prompt's
wording, a file's presence) and a behaviour test asserts what the code does, so the distinction is
reviewable. The pull request diff is where the reviewer sees which test went. No new automation
can tell the two apart, and adding one would be a test about tests.

## Verification

- `openspec validate --all` after the delta is applied.
- The review of the removal diff, which names each deleted file and what it asserted.
