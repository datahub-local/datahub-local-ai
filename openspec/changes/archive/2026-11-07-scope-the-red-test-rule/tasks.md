# Tasks

## 1. Spec

- [x] 1.1 `codeagent-instructions`: scope the red-test scenario to a test that covers behaviour.
- [x] 1.2 `codeagent-instructions`: add the configuration-test scenario, where deletion is the
      rule being applied and the build or live run is the check.
- [x] 1.3 `codeagent-instructions`: state in the requirement text which deletion is forbidden.

## 2. Repository rule

- [x] 2.1 `AGENTS.md`: no unit tests for n8n workflows; the review, the live apply and the run are
      the check.
- [x] 2.2 `agents/n8n/README.md` and `docs/agent/n8n.md`: the same rule, dated.

## 3. Tests

- [x] 3.1 Delete `agents/n8n/scripts/test_*.py` (three files).
- [x] 3.2 Remove the n8n job and the `agents/n8n/**` triggers from
      `.github/workflows/test-agents.yaml`.

## 4. Gate

- [x] 4.1 `openspec validate --all`.
- [x] 4.2 Delta applied to `codeagent-instructions` and archived.
