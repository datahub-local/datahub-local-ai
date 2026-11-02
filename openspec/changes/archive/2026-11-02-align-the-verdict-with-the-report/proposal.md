# Proposal

## Why

A clean run posted a warning. `gitops-auditor` at 07:00 UTC on 2026-10-31 read
`Status: All ten applications are Synced and Healthy; nothing needs action this run` and
carried `⚠️`, and it was not an isolated case: over the last eight stored runs per persona,
the emoji contradicted the report's own `Status` line in 3 of 3 clean `gitops-auditor`
runs, 4 `workload-watch` runs and 2 `service-janitor` runs.

The cause is a contract with one half missing. `files/deliver-slack.py` derives the emoji
from section labels, and a section in `FINDING_SECTIONS` warns unless its content is one of
its `Nothing…`/`None`/`No <x>` forms. `NOTHING` matches the opening of a line, so a clean
section that states its reading and then its evidence warns: run 203's `Drift` opened
`- No drifting application: …` and added `- Every row shows runs drifted as -` and
`- datahub-local-ai-superset, …`, and its `Escalating` added
`- Worth watching, not a finding: …`. Nothing in `hook.md` or in any persona format said
what a finding section looks like when nothing is wrong, and nothing forbade commentary
inside one.

The same review found two adjacent defects. `workload-watch`'s `Idle` section is defined by
its own prompt as never a finding and was classified as one, so any run reporting the idle
count warned. And `gitops-auditor` told the model to never repeat a call while its primary
facts tool timed out twice in that same run — obeying the rule produces no data at all.

## What Changes

- **`hook.md` states the empty form**, in the one file every reporter already receives: a
  finding section with nothing to act on holds one bullet opening with `Nothing`, `None` or
  `No <thing>`, the reading may follow after a colon, and commentary — `worth watching`,
  `not a finding`, `recurring`, a tool-timeout note — never belongs there.
- **Each persona format states its own empty form** for every finding section it writes.
  Six sections across five personas had none: `gitops-auditor`'s `Drift` and `Escalating`,
  `sre-sentinel`'s `New` and `Filling up`, `endpoint-warden`'s `Findings` and
  `Maintenance`, `db-steward`'s `Room to grow`, `service-janitor`'s `Backups` and
  `Accumulation`, `workload-watch`'s `Short of pods` and `Restarting`.
- **`Idle` moves to `CLEAN_SECTIONS`** in the classifier, because its prompt already says an
  idle service is never a finding on one reading. **`Restarting` stays a finding** and gains
  a threshold: above 2 restarts in 24h, so the firecrawl loop that restarted 103 times still
  warns while an occasional controller-manager restart does not.
- **`gitops-auditor` may retry its primary facts call once** after a timeout; a second
  failure is reported as a gap. Investigation calls still never repeat.
- **A test holds the prompt half to the code half**: every finding section a reporter writes
  must state an empty form, and `Idle` must classify clean.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `agent-reports`: a finding section gains a required empty form, and the label sets move —
  `Idle` is clean-only, `Restarting` is a finding with a stated threshold.

## Impact

- `agents/sympozium/prompts/delivery/hook.md` — the empty-form contract.
- `agents/sympozium/projects/homelab-ops/prompts/{gitops_auditor,sre_sentinel,endpoint_warden,db_steward,service_janitor,workload_watch}_system.md`
  — empty forms; `gitops_auditor` also gains the retry rule and loses the "what is growing
  or persistent" wording that invited commentary.
- `agents/sympozium/files/deliver-slack.py` — `idle` moves between the label sets.
- `agents/sympozium/tests/test_report_shape.py` — two new tests.
- `agents/sympozium/MEMORY.md` — the measurement and the partition.
- Shipping is a push to `main`; the sync fires no run, so the next scheduled tick is the
  first report under the new contract.

## Non-Goals

- `endpoint-warden`'s stale apt cache, which warns on every run because it is permanent on
  all seven nodes. A permanent finding is a bug, but the accept/raise/silence decision is
  the owner's and is left open.
- Any threshold beyond `Restarting`'s: a volume at warn, a stale backup and an expiring
  certificate stay findings on any non-empty reading.
- The `homelab-oracle` answer contract and `renovate-reviewer`'s PR comment, which carry no
  verdict emoji.
