# Tasks

## 1. Prune workflow (`agents/n8n/workflows/visual_studio_prune.workflow.json`)

- [x] 1.1 Window shortened from seven days to two in `delete_expired`, in both copies:
  `new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString()`.
- [x] 1.2 Added `delete_expired_files` after `delete_expired`, deleting `TemporalFiles` rows
  with `updatedAt < $now.minus({ hours: 1 })` — the rule copied from `File Webhook`'s own
  cleanup — and wired `delete_expired -> delete_expired_files` in both copies.
- [x] 1.3 `settings.saveDataSuccessExecution = "none"` (top level only: the export's
  `activeVersion` carries no `settings` key, which the first pass got wrong and the live
  diff caught).

## 2. Execution payloads

- [x] 2.1 `saveDataSuccessExecution = "none"` on `visual_studio`, `visual_studio_test` and
  `linked_in_post_sharing`; `saveDataErrorExecution` left at its default.

## 3. Dead workflows

- [x] 3.1 Deleted `my_workflow_668`, `test_form`, `zz_daily_check_probe_temp` and
  `zz_probe_assets_dbg` from the repository (19 exports remain) and from the live instance
  (`DELETE /api/v1/workflows/{id}`, all HTTP 200).

## 4. Guard test (`agents/n8n/scripts/test_storage_retention.py`)

- [x] 4.1 Asserts the prune deletes `visual_studio_table` rows on a window of at most two
  days and `TemporalFiles` rows on the one-hour rule, and that the second delete runs after
  the first, in both copies.
- [x] 4.2 Asserts each of the four artifact workflows sets `saveDataSuccessExecution: "none"`
  while leaving `saveDataErrorExecution` recording, and that the four dead exports stay
  deleted.
- [x] 4.3 Verified: all 14 assertions fail against the previous exports and pass now.

## 5. Verify

- [x] 5.1 `agents/n8n/scripts/` — **194 passed**.
- [x] 5.2 All four workflows deleted; the live list is 19 workflows, all active.
- [x] 5.3 Applied the three settings and the prune workflow with `--require-edge` guards
  satisfied (`schedule_trigger -> delete_expired`), published in place, re-read
  `activeVersion` (equal to the top level) and diffed: export == live for all four.
- [x] 5.4 `TemporalFiles` cleared: 19 rows / 36 MB → **0 rows / 512 kB**.
- [x] 5.5 Measured after the change:

  | relation | before | after |
  | --- | --- | --- |
  | `execution_data` | 1058 MB / 1444 rows | 1058 MB / 1426 rows |
  | `binary_data` | 183 MB / 796 rows | 183 MB / 775 rows |
  | `visual_studio_table` | 136 MB / 9 rows | 136 MB / 9 rows |
  | `TemporalFiles` | 38 MB / 19 rows | **512 kB / 0 rows** |
  | `n8n` database | 1439 MB | 1402 MB |

  The two large relations did not move yet, and that is expected rather than a miss:
  the setting bounds *new* executions, while the existing ones age out under n8n's 14-day
  retention, and all nine run rows are from today, inside the new two-day window. Immediate
  relief needs the existing executions and rows deleted (see the follow-up note in the
  change's report).

## 6. Documentation

- [x] 6.1 `AGENTS.md` § Visual Studio *Failure and retention*: the two-day window, the
  `TemporalFiles` cleanup and why it exists, and why the four artifact workflows do not
  persist successful payloads.
