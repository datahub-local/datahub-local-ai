# Proposal

## Why

The rendered artifact travels through the workflows as a base64 `data:` URL, and that
one decision means the same bytes are persisted **three times**: the run row, the
execution payload, and n8n's binary store. Measured on the live instance:

| relation | size | rows |
| --- | --- | --- |
| `execution_data` | 1058 MB | 1444 |
| `binary_data` | 183 MB | 796 |
| `visual_studio_table` | 136 MB | **9** |
| `TemporalFiles` | 38 MB | 19 |

- **`visual_studio_table` is 136 MB in nine rows** — up to 18.2 MB per row (a deck and
  its paired video, base64). The `Visual Studio Prune` window is seven days, so the
  table can hold a week of multi-megabyte rows.
- **The execution payload is the same bytes again.** `Visual Studio Test` alone is
  511 MB across 46 runs, `Visual Studio` 377 MB across 92. n8n saves every node's
  output on success by default, and the studio's output *is* the artifact.
- **`Visual Studio Prune` contributes to its own problem** (44 MB / 15 runs):
  `deleteRows` returns the deleted rows, base64 and all, and that output is persisted.
- **`TemporalFiles` holds 36 MB from a single hour on 2026-10-07.** Its cleanup
  (`updatedAt < now - 1h`) runs only when `File Webhook` is called, and nothing has
  called it since, so the rows never expire.
- **Four workflows are dead**: `My workflow 668`, `Test Form`,
  `ZZ Daily Check Probe (temp)` and `zz_probe_assets_dbg` are all inactive and
  referenced by nothing (checked across `executeWorkflow` and `errorWorkflow`
  references in every export).

## What Changes

- **The run row is kept for two days, not seven.** The bytes stay in the row — a caller
  can still fetch a run's content — but the window is short enough that the table
  cannot hold a week of decks.
- **Successful executions of the artifact-carrying workflows do not persist their
  payloads.** `saveDataSuccessExecution: "none"` on `Visual Studio`,
  `Visual Studio Test`, `LinkedIn Post Sharing` and `Visual Studio Prune`. Error
  executions are still saved, which is what a failure needs.
- **`Visual Studio Prune` also clears `TemporalFiles`**, applying the same one-hour
  rule `File Webhook` applies on request, so a quiet week cannot leave stale rows.
- **The four dead workflows are deleted** from the live instance and from the exports.

## Capabilities

### Modified Capabilities

- `visual-studio`: a recorded run is retained for a bounded window (two days) and then
  pruned, rather than kept indefinitely.

## Impact

- `agents/n8n/workflows/visual_studio_prune.workflow.json` — the window, the
  `TemporalFiles` step, and the execution-save setting.
- `agents/n8n/workflows/{visual_studio,visual_studio_test,linked_in_post_sharing}.workflow.json`
  — the execution-save setting.
- `agents/n8n/workflows/{my_workflow_668,test_form,zz_daily_check_probe_temp,zz_probe_assets_dbg}.workflow.json`
  — deleted.
- `agents/n8n/scripts/test_storage_retention.py` — new guard over the exports.
- `openspec/specs/visual-studio/spec.md` — the retention window.
- Live: four workflow deletes, four settings PUTs, one prune-workflow apply, and the
  stale `TemporalFiles` rows cleared.
