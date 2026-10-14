# Proposal

## Why

`visual_studio_table` is **202.5 MB against a 200 MB cap** and holds only 12 rows. Four
of them are 32-34 MB because `RESULT` carries every asset as a base64 data URL, so a
single 50-second MP4 costs a sixth of the table. On 2026-10-13 run `13256` authored,
rendered and fetched its asset correctly and then failed at `record_run`:

```
Validation error with data table request: Data table size limit exceeded: 204MB used, limit is 200MB
```

Every later run fails the same way, and the failure is invisible in the table: the
`Visual Studio Error` workflow ran, posted to Slack and reported `success`, but
`record_failed` carries `onError: continueRegularOutput`, so its write failed silently
and no `FAILED` row exists for `13256`. The prune window (two days) frees about 31 MB —
one more manga-sized run.

Garage is already the object store for this stack, and `datahub-local-temp` already
exists. The asset belongs there, not in a row.

## What Changes

- The studio SHALL upload each rendered asset to the Garage bucket
  `datahub-local-temp` at `visual-studio/<RUN_ID>-<ASSET_TYPE>.<ext>` before the run row
  is written.
- The run row's `RESULT` SHALL carry the object key, the byte count and the storyboard,
  and SHALL NOT carry the base64 bytes.
- The studio's response SHALL keep the asset itself (`ASSETS[].IMAGE`), so the in-run
  consumers (`LinkedIn Post Sharing`, the webhook caller) are unchanged.
- `Visual Studio Prune` SHALL delete the bucket's objects on the same two-day window it
  applies to the rows.
- `record_failed` SHALL NOT swallow its own failure: a `FAILED` row that cannot be
  written must fail the error workflow.

## Capabilities

### Modified Capabilities

- `visual-studio`: the rendered asset is stored in object storage and referenced from
  the run row, instead of being persisted in the row; the retention window covers both.

## Impact

- **`agents/n8n/workflows/visual_studio.workflow.json`**: `prepare_uploads` (Code) and
  `upload_assets` (S3) are added; `merge_branches -> prepare_uploads -> upload_assets ->
  run_record`; `run_record` drops `IMAGE` from `RESULT` and adds `S3_KEY`/`S3_BYTES`.
- **`agents/n8n/workflows/visual_studio_prune.workflow.json`**: `list_assets` (S3) ->
  `filter_old_assets` (Code) -> `delete_assets` (S3), after `delete_expired_files`.
- **`agents/n8n/workflows/visual_studio_error.workflow.json`**: `record_failed` loses
  `onError`.
- **`agents/n8n/scripts/test_storage_retention.py`**: the row carries no data URL; the
  upload precedes the row; the prune covers the bucket on the same window.
- A new n8n credential of type `s3` pointing at Garage (live only — credentials are not
  in git).
- Applied live with `scripts/apply_workflow_changes.py --changes` (a graph edit adds
  nodes, so it is not a field-level `--set`).

## Non-goals

- `TemporalFiles`. It holds the same bytes for `Visual Studio Test`, but `File Webhook`
  deletes its rows on every request, so it is bounded at ~11 MB. Left alone.
- A presigned or public URL for a human. The row names the object; fetching it is a
  Garage client's job.
- Changing the asset contract (`ASSET_TYPE`, `STATUS`, `CONTENT_TYPE`). Only where the
  bytes live changes.
