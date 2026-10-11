# Tasks

## 1. Prune workflow (`agents/n8n/workflows/visual_studio_prune.workflow.json`)

- [ ] 1.1 Shorten `delete_expired`'s window from seven days to two, and say so in the
  node's expression.
- [ ] 1.2 Add a `delete_expired_files` node after `delete_expired` that deletes
  `TemporalFiles` rows with `updatedAt < $now.minus({ hours: 1 })` — the same rule
  `File Webhook` applies on request — and wire `delete_expired -> delete_expired_files`.
- [ ] 1.3 Set `settings.saveDataSuccessExecution = "none"` in both export copies, so the
  prune's own `deleteRows` output (the rows it just deleted, base64 included) is not
  persisted.

## 2. Execution payloads

- [ ] 2.1 Set `settings.saveDataSuccessExecution = "none"` on `visual_studio`,
  `visual_studio_test` and `linked_in_post_sharing`, in both export copies, leaving
  `saveDataErrorExecution` at its default.

## 3. Dead workflows

- [ ] 3.1 Delete `my_workflow_668.workflow.json`, `test_form.workflow.json`,
  `zz_daily_check_probe_temp.workflow.json` and `zz_probe_assets_dbg.workflow.json`,
  and delete the four live workflows.

## 4. Guard test (`agents/n8n/scripts/test_storage_retention.py`)

- [ ] 4.1 Assert the prune workflow deletes `visual_studio_table` rows with a window of at
  most two days, and that it also deletes `TemporalFiles` rows with the one-hour rule.
- [ ] 4.2 Assert each artifact-carrying workflow sets `saveDataSuccessExecution: "none"`
  in both export copies, and that no such workflow is missing it.
- [ ] 4.3 Verify each assertion fails without its change.

## 5. Verify

- [ ] 5.1 Run the `agents/n8n/scripts/` suite.
- [ ] 5.2 Live: delete the four workflows and confirm they are gone from
  `GET /api/v1/workflows`.
- [ ] 5.3 Live: apply the four settings and the prune workflow with `--require-edge`
  guards, publish, re-read `activeVersion` and diff the export against live.
- [ ] 5.4 Live: clear the stale `TemporalFiles` rows and confirm the table is empty.
- [ ] 5.5 Re-measure `execution_data`, `binary_data`, `visual_studio_table` and
  `TemporalFiles`, and record before/after here.

## 6. Documentation

- [ ] 6.1 `AGENTS.md` § Visual Studio: the two-day run-row window, the `TemporalFiles`
  cleanup, and why successful payloads are not persisted for the artifact workflows.
