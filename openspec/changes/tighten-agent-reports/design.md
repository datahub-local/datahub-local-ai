# Design

## Context

Each `homelab-ops` persona is a YAML file plus two prompt files. The system prompt is
rendered into `Agent.spec.systemPrompt` at install and carries the persona's `{{ DELIVERY }}`
token, which `templates/_delivery.tpl` substitutes with `prompts/delivery/hook.md`. That
file is the only text all six reporters share: it says where the report goes, forbids a
header, provides the no-clock rule, and states the Markdown rules. It states no length and
no shape, so each persona's own "Write exactly once, in order" block is the only format
contract, and none of them bounds how much to write.

Delivery is `deliveryMode: hook`: `files/deliver-slack.py` runs as a `postRun` container,
receives the run's final text as `AGENT_RESULT`, converts Markdown to Slack mrkdwn, prepends
the `"<Agent> | <ensemble> | <cadence>"` header and an emoji, and posts once. Reader is a
Slack channel — `#monitoring-ai-health` by default, `#monitoring-ai-alerts` for
`sre-sentinel`, `#monitoring-ai-drift` for `gitops-auditor`. Slack has no tables, and
mrkdwn is what the hook emits.

## Gate findings

Read from the running cluster and the repository on 2026-10-30, not from documentation.

- **The baseline is measured, not felt.** Word counts over the last ten stored runs per
  persona are in the proposal. `db-steward` and `endpoint-warden` are 2–7× the length of
  the rest, and the two long reports are long for a structural reason, not a state reason:
  `db-steward`'s `Postgres` section prints "Sizes (each database printed once per
  instance)" and the model transcribes 16 databases; `endpoint-warden`'s `Findings` section
  says "Report every line the tool printed under `Readings that need a note` … none of them
  summarised away", so 16 bullets are mandatory by instruction, and `Maintenance` then
  repeats the same per-machine readings. The verbosity is written into the prompts.
- **`endpoint-warden` is long because its own instruction forbids summarising.** The line
  above is why the fix has to change the wording there and not add a cap beside it: a cap
  and "none of them summarised away" contradict each other, and the 2026-10-18 lesson (a
  rule the drafter cannot satisfy is unfixable by construction) applies to a report
  contract exactly as it does to a drafting gate.
- **The verdict is computed from the report's own labels.** `Verdict.classify` returns
  `🔴` on any `ERROR:` literal, `⚠️` when a section named in `FINDING_SECTIONS` is not one
  of its "nothing" forms, and `✅` otherwise. Renaming or inventing a section therefore
  changes the emoji silently: a finding written under a label the classifier does not know
  is a dirty run posted with a green check. The shape must keep the existing labels and a
  test must hold them together.
- **`FINDING_SECTIONS` is a closed set of 14 names** and every persona's finding sections
  are already inside it (`new`, `findings`, `escalating`, `drift`, `backups`, `expiring`,
  `accumulation`, `maintenance`, `short of pods`, `restarting`, `idle`, `filling up`, `room
  to grow`, `still firing` handled by its own rule). The clean-only labels the prompts also
  write (`fleet`, `busiest`, `changed`, `power`, `postgres`, `cache`, `object store`,
  `streams`, `metrics store`, `resolved`, `status`) are not in it and never warn, which is
  correct — but nothing in the repository records them as known.
- **The hook performs no length handling at all.** It converts, prefixes and posts; the only
  length constant is `DETAIL_LIMIT = 1500`, and it applies to a *failed* run's error, not to
  a report. A 5,223-character report posts as one message.
- **A probe `AgentRun` takes `systemPrompt` inline**, so the new shape can be measured
  without installing it: `kubectl apply` a one-off `AgentRun` naming an existing `Agent`,
  overriding the prompt. This matters because `helmfile apply` on `homelab-ops` queues one
  real run per persona (MEMORY: the Ensemble controller starts a run within the same second
  as every `SympoziumSchedule` it rewrites), which would post six messages to Slack.

## Goals / Non-Goals

**Goals:**

- One line at the top that says what a person has to do, or that nothing needs doing.
- One numeric budget per report, stated where the report is generated, that a model can
  check itself against.
- Four facts stay four facts: a condition repeated across machines costs one bullet, not
  one per machine per check.
- No finding, action or figure changed by dropping to the cap — only healthy detail.

**Non-Goals:**

- Rewriting the six personas' investigation, tool surface or schedules.
- A code-side truncation as a backstop (see D6).
- Any change to `renovate-reviewer`, `homelab-oracle`, or the n8n notifications.

## Decisions

### D1. The shared rules go in `hook.md`, the sections stay in the persona prompt

`hook.md` is already the one file substituted into every reporter, so the cap and the
cross-cutting rules live there once. Each persona keeps its own section list and order,
because that is the shape *per report type* and a persona is the only place that knows what
its report is about. The alternative — a single shared section template — would delete the
per-report structure the reader is meant to learn, which is the opposite of the issue.

### D2. 300 words, raised from 250 on the first one-bullet-per-fact measurement

The cap is a property of the reader, not of a persona: one Slack message, read on a phone,
one screen. 250 words is ~1.4 KB of mrkdwn and is roughly twice the median of the three
reports that already read well (`sre-sentinel` 217, `workload-watch` 158) — so it is
headroom for a bad day rather than a target. It cuts `db-steward` 64% and `endpoint-warden`
59% from their medians. `service-janitor` at 305 needs a real cut; `gitops-auditor`'s 30-word
clean run is untouched. A tighter cap (150) would force `sre-sentinel`'s five sections into
single clauses on a day with three new alerts, and losing the per-alert evidence is worse
than the length.

*Alternatives considered:* 150 — rejected above. No numeric cap, per-section line budgets
only — rejected: the model has no single number to count itself against, and the measured
failure is total length, not one runaway section. A cap per persona (e.g. 150 for gitops) —
rejected as six numbers to keep consistent for a report type whose clean run is 30 words
anyway; the shared cap is the ceiling, not the target.

### D3. A repeated condition is one bullet, and the rest is a count

Three rules, each answering a measured failure:

- **One fact appears once.** `endpoint-warden`'s 32 bullets for four conditions is the
  failure this kills; a later section that would repeat an earlier one omits it.
- **Same condition on N machines: one bullet, machines as a comma list, cause and action
  once.** `amd-1`, `amd-2`, `nas`, `orpi-0..3` all carry a stale apt cache; that is one
  line naming seven machines, not seven lines.
- **Name the worst, count the rest.** `db-steward`'s 16 database sizes and 31 volumes become
  `worst prometheus 81.9% (+1.9pp); 30 others 0.8–55.7%`. The reader's question is "is
  anything near a limit", not "what does every volume hold".

The one exception is a finding the reader must act on individually, which is already
per-item in the prompt (`workload - ready/wanted - verdict - action`).

### D4. A gap is a footnote, and the footnote is not a section

The outcome line is the one line a reader is meant to act on, so a failed check does not
belong in it: the probe run put a 40-word sentence on line one carrying both the storage
finding and a missing `pg_stat_statements`. A gap now ends the line with `(*)` and is listed
once under that marker after the last section, keeping the literal `ERROR:` so the red
verdict survives.

Two consequences in code, both in `deliver-slack.py`. `_sections` treats a `(*)` line as a
block boundary that belongs to no section — without it the footnote is appended to the last
section's content, and a clean `Power` section that only said "no UPS is monitored" would
read as populated and post a warning. And `Verdict.prefix` now puts the emoji *inside* the
Status line, after its label (`*Status:* ⚠️ …`), which is the shape the reader scans for;
prepending it made the symbol the first token and the label look like its value.

### D5. The section labels are frozen to the classifier's vocabulary, and a test holds them

Renaming a section is the one edit to this shape that fails silently in production, so the
new test parses each reporter's `Write exactly once, in order:` block, extracts every
bolded label, and fails when a label is neither `Status` nor one the hook knows as a finding
section nor one it records as clean-only. The clean-only labels gain a `CLEAN_SECTIONS`
constant in `deliver-slack.py` beside `FINDING_SECTIONS`, so the pairing is in code rather
than in a list inside a test that nobody reads when they add a section.

### D6. The drop order is stated, because a cap with no order loses the wrong thing

"At most 300 words" on a day with six findings is unsatisfiable unless the prompt says what
to cut. The order is: healthy sections to one line, then the smaller figures inside a
section, then the machine lists shortened — never a finding, an action, or the status line.
The precedent is `endpoint-warden`'s own `unavailable` rule and `sre-sentinel`'s `cause not
determined`: absence has to be expressible, or a mandatory format gets filled with invented
content.

### D7. One layout, because six shapes is six things to learn

The 17:17 live run settled it: four personas wrote a bold heading on its own line and two
wrote `**Label:** text…` inline, in the same fleet. Measured over the same six reports, the
longest single line was **509 characters** (`sre-sentinel`'s `Still firing`, ~6 wrapped
lines of undifferentiated text), and three more passed 400. Bullets were used by accident —
`endpoint-warden` had them under `Findings` and inline prose under `Fleet` and `Maintenance`
in one report.

So the layout is fixed: `Status` is the one label a sentence sits on (it carries the verdict
emoji, and `Verdict.prefix` inserts it there), and every other section is a `##` heading on
its own line followed by `- ` bullets, one fact per bullet, at most two rendered lines,
split rather than wrapped, no `;`-joined enumerations, and a copyable name always a whole
identifier in a code span — `monitoring/…-prometheus-0` was the counter-example, a name
nobody can paste.

This is also why the shared layout lives in `hook.md` and not in six formats: the one thing
all six had in common was that they disagreed.

### D8. The cap is enforced by the prompt, not by truncating the message

The hook already truncates a failed run's error at 1,500 characters because that text is
not a report. Truncating a report would cut at an arbitrary point and could delete the one
finding the report exists to carry — the worst possible failure mode for a monitoring
channel, and invisible to every test. The prompt owns the budget; the test owns the
consistency of the prompts; the live probe owns whether the model obeys.

### D9. Verification is a probe run against the same state, not a re-read of the old reports

Acceptance asks for the same underlying event, before and after. The before is the stored
run (`db-steward` 05:30, `endpoint-warden` 04:30 UTC, both today). The after is a
hand-applied `AgentRun` with the new prompt inline over the same cluster, minutes apart, so
the findings are the same conditions rather than the same words. A probe costs one Slack
message per persona and no apply; the apply itself stays a separate, approved step.

## Risks

- **A model under a cap drops a finding to fit.** Mitigated by D5's explicit drop order and
  the probe, which compares the finding set before and after rather than only the length.
- **The `endpoint-warden` rewrite removes "none summarised away"** and the tool's note
  lines are then summarised into a count. That is the intent, but a note that only appears
  on one machine must still reach the reader, so the rewritten format keeps a `Findings`
  bullet per distinct *condition*, not per distinct machine.
- **Prompt text is only gated by the render.** The new test covers the label vocabulary and
  the presence of a budget; nothing offline can prove the model obeys a cap.

## Open Questions

- Should `endpoint-warden`'s permanently-stale apt cache (7/7 machines, 9–59 days) be a
  finding at all? It is a permanent condition that forces a ⚠️ verdict every run, which is
  the "a permanent finding is a bug in the prompt" lesson. Out of scope here — recorded so
  the next change does not re-derive it.

## Definition of Done

- `hook.md` states the shape, the 300-word cap, the one layout, the grouping rules, the
  gap footnote and the drop order.
- All six personas write `**Status:**` plus `##` headings with bullets; no persona states a
  competing cap.
- `agents/sympozium/tests/test_report_shape.py` passes and fails without the change.
- `helmfile template` in `agents/sympozium/` renders.
- `openspec validate --all` passes.
- A probe `AgentRun` for `db-steward` and `endpoint-warden` returns ≤250 words, keeps every
  finding the old report carried, and reads as a lead plus sections; the measured
  before/after is recorded in `MEMORY.md`.
- Shipped: the commit is on `main` and ArgoCD synced it; the six scheduled runs that follow
  are the first live use of the gap footnote and the layout.
