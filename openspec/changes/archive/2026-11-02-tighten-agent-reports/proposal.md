# Proposal

## Why

The six scheduled reporters in `homelab-ops` post a report to Slack every run, and two of
them have grown into a wall of prose. Measured over the last ten runs each (live AgentRun
`status.result`, 2026-10-30):

| Persona         | words: min / median / max |
| --------------- | ------------------------- |
| db-steward      | 614 / 692 / 781           |
| endpoint-warden | 474 / 614 / 876           |
| service-janitor | 257 / 305 / 350           |
| sre-sentinel    | 163 / 217 / 295           |
| workload-watch  | 148 / 158 / 232           |
| gitops-auditor  | 18 / 30 / 207             |

Length is standing in for structure. `db-steward` prints one bullet per database size and
one per volume claim (16 databases, 31 claims) because its sections say "report the sizes";
`endpoint-warden` prints the same four conditions twice, once per machine under `Findings`
and again per machine under `Maintenance`, 32 bullets for four facts. Neither is a tool
output the reader can act on differently — the actionable fact in each is a single line
that is buried. Nothing in the fleet states a length budget, so the model decides each run
how much to write and the answer drifts with the day's state.

## What Changes

- **The shared delivery contract gains a shape**, in the one file every reporter already
  receives (`prompts/delivery/hook.md`): line one is the outcome, the whole report is at
  most 300 words, one fact appears once, the same condition on many machines is one bullet
  with the machines listed, name the worst and count the rest, and an over-budget report
  drops healthy detail before it drops a finding.
- **The three fat report formats are rewritten to that shape** — `db-steward`,
  `endpoint-warden` and `service-janitor` — each keeping its own section labels and order
  and gaining a per-section line budget. `sre-sentinel`, `workload-watch` and
  `gitops-auditor` change no section; they inherit the shared rule and already sit inside
  the cap.
- **One test holds the prompt half to the code half.** `deliver-slack.py` derives the
  report's verdict emoji from the `Status` line and from a fixed set of finding section
  labels, so a section renamed in a prompt silently turns a dirty run green. The new test
  fails on a label a reporter writes that the classifier does not know, on a missing
  length budget, and on a report format that contradicts the shared cap.

## Capabilities

### New Capabilities

- `agent-reports`: the shape of a report a persona posts to its channel — lead, sections,
  length cap, what is grouped and what is dropped — and how that shape stays consistent
  with the delivery hook that renders and classifies it.

### Modified Capabilities

None. The report formats live in prompt files this repository owns; no other capability's
behaviour changes.

## Impact

- `agents/sympozium/prompts/delivery/hook.md` — the shared shape, substituted into all six
  reporters at render time.
- `agents/sympozium/projects/homelab-ops/prompts/{db_steward,endpoint_warden,service_janitor}_system.md`
  — format rewritten, sections and labels unchanged.
- `agents/sympozium/tests/test_report_shape.py` — new.
- `agents/sympozium/MEMORY.md` — why the cap is 300 and what the baseline was.
- **Not applied by this change.** A prompt is rendered into the `Agent` at install, so a
  `helmfile apply` is what ships it, and the ensemble controller starts a run for every
  persona an apply touches. The apply and the live before/after probe are a separate,
  explicitly approved step.

## Non-Goals

- `renovate-reviewer`'s PR comment and repository-health block: GitHub is the reader there
  and the comment has its own required sections.
- `homelab-oracle`'s answers: a reply contract, already strict, and plain text by design.
- Any n8n notification (curator digest, article review, draft failed): a different renderer
  and a different family.
- Tool selection, schedules, thresholds, or what any persona investigates.
