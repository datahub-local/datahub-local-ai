# Tasks

## 1. The shared shape

- [x] 1.1 Add a `### Shape` section to `agents/sympozium/prompts/delivery/hook.md`: line one
  is the outcome under `**Status:**`; the whole report is at most 250 words; sections and
  their order come from the persona's own format; one fact appears once; a condition shared
  by N machines is one bullet with the machines listed; name the worst and count the rest;
  no reassurance, only readings; the drop order when over budget
- [x] 1.2 Keep the existing rules intact (no header, no clock, Markdown only, no tables, no
  padding) and delete nothing from `hook.md` — the shape is added to the contract, not
  substituted for it

## 2. The report formats

- [x] 2.1 Rewrite `db_steward_system.md`'s format: the same seven labels in the same order,
  a line budget per section, database sizes and volume claims as "worst + count", and the
  failed check stated once in `Status` rather than in three sections
- [x] 2.2 Rewrite `endpoint_warden_system.md`'s format: replace "none of them summarised
  away" with "one bullet per distinct condition, machines listed", collapse `Maintenance`
  to one count line plus the exceptions, keep `Fleet`, `Findings`, `Maintenance`, `Power`
- [x] 2.3 Tighten `service_janitor_system.md`: four labels unchanged, per-section line
  budget, freshness and expiry as counts with the exception named
- [x] 2.4 Confirm `sre_sentinel_system.md` and `gitops_auditor_system.md` need no format
  edit, and give `workload_watch_system.md` the `Status` lead it lacked — it opened on
  `Busiest`, so the verdict emoji landed on the wrong line

## 3. The code half

- [x] 3.1 Add `Verdict.CLEAN_SECTIONS` to `agents/sympozium/files/deliver-slack.py` beside
  `FINDING_SECTIONS`, so every label the prompts write is known to the classifier in one
  place, and say why in its docstring
- [x] 3.2 Add `agents/sympozium/tests/test_report_shape.py`: every reporter prompt declares
  the 250-word budget through the shared file, every bolded label in its format block is
  known to `Verdict`, a finding section is not renamed, and `endpoint_warden` no longer asks
  for an unsummarised dump
- [x] 3.3 Run `uv run pytest agents/sympozium/tests/` and confirm the new tests fail against
  the old prompts before the edits land

## 4. Rationale and gates

- [x] 4.1 Record the baseline table, the 250-word argument and the label-freeze trap in
  `agents/sympozium/MEMORY.md`, with a pointer from `README.md` if the delivery section
  needs it
- [x] 4.2 `helmfile template` in `agents/sympozium/` renders with the new prompt text
- [x] 4.3 `openspec validate --all` passes

## 5. Live verification (blocked on approval)

- [x] 5.1 Probe `db-steward` with a hand-applied `AgentRun` carrying the new prompt inline;
  record words, finding set and shape against the 05:30 report (blocked by: approval to post
  one Slack message)
- [x] 5.2 Probe `endpoint-warden` the same way against the 04:30 report (blocked by: same
  approval)
- [x] 5.3 Ship it — not `helmfile apply`: the chart is the ArgoCD app
  `datahub-local-ai-sympozium` tracking `https://github.com/datahub-local/datahub-local-ai.git`
  `HEAD`, so shipping is a commit on `main` (a local `helmfile sync` fails: no Helm release of
  that name exists). Pushed as `f548a19`; ArgoCD synced revision `f548a19` and the live
  Ensemble carries the new prompt and the new hook script
- [ ] 5.4 Read the next scheduled run per persona — the first live use of the `(*)` footnote
  shape, which no probe has exercised (blocked by: the next tick, 04:30-07:00 UTC)
