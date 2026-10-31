# Tasks

## 1. The shared contract

- [x] 1.1 Add the empty-form rule to `agents/sympozium/prompts/delivery/hook.md`: a finding
  section with nothing to act on holds one bullet opening with `Nothing`, `None` or
  `No <thing>`, the reading follows after a colon, and commentary never belongs there
- [x] 1.2 State the two reasons in the same place: the verdict emoji is computed from those
  openings, and judgement is the `Status` line while a failed check is a `(*)` footnote

## 2. The persona formats

- [x] 2.1 `gitops_auditor_system.md`: an empty form for `Drift` and `Escalating`, replace
  "what is growing or persistent" with "whose run count grew", and allow one retry of the
  primary facts call while investigation calls still never repeat
- [x] 2.2 `sre_sentinel_system.md`: an empty form for `New` and `Filling up`
- [x] 2.3 `endpoint_warden_system.md`: an empty form for `Findings` and `Maintenance`
- [x] 2.4 `db_steward_system.md`: an empty form for `Room to grow`
- [x] 2.5 `service_janitor_system.md`: an empty form for `Backups`, `Expiring` and
  `Accumulation`
- [x] 2.6 `workload_watch_system.md`: a threshold for `Restarting` (above 2 restarts in
  24h) with its empty form, and an empty form for `Short of pods`

## 3. The code half

- [x] 3.1 Move `idle` from `FINDING_SECTIONS` to `CLEAN_SECTIONS` in
  `agents/sympozium/files/deliver-slack.py`, and say in its docstring that the persona's own
  prompt already calls it a non-finding
- [x] 3.2 Record the empty-form half in `Verdict`'s docstring, with the 2026-10-31 run that
  proves why the classifier cannot infer it
- [x] 3.3 `test_every_finding_section_states_an_empty_form` over every reporter prompt
- [x] 3.4 `test_idle_is_a_reading_not_a_finding` and
  `test_a_restart_above_the_stated_threshold_still_warns`
- [x] 3.5 Confirm the new shape classifies clean for all six personas on a report written to
  their new empty forms, and that the old run 203 text still warns (the prompt fixes future
  runs, not past text)

## 4. Rationale and gates

- [x] 4.1 Record the measurement, the split and the open `endpoint-warden` question in
  `agents/sympozium/MEMORY.md`
- [x] 4.2 `uv run pytest agents/sympozium/tests/` passes
- [x] 4.3 `helmfile template` renders in `agents/sympozium/`
- [x] 4.4 `openspec validate --all` passes

## 5. Live verification

- [ ] 5.1 Read the next scheduled run per persona and confirm the emoji matches its `Status`
  line (blocked by: the next tick, 04:30-07:00 UTC)
