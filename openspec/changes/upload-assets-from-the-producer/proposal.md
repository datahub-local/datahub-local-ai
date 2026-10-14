# Proposal

## Why

`Visual Studio`, `Visual Studio Test`, `Visual Studio Prune` and `LinkedIn Post Sharing`
carry `saveDataSuccessExecution: "none"`, so a **successful** run leaves no record at all
in n8n. That was set because the workflow's payload *is* the artifact: `agent_result`
builds `IMAGE: 'data:' + mime + ';base64,' + …`, and run `13356` returned
**80,838,754 characters** for a 60.6 MB file.

The S3 change moved the bytes to Garage, but not out of the workflow — the base64 string
is still a node output, so it is still what n8n persists. And n8n persists *binary* data
too: measured on this instance, `binary_data` is **249 MB across 903 rows** and
`execution_data` **1060 MB across 1405 rows**, in a 1335 MB database. Enabling success
recording with the bytes still passing through n8n therefore adds ~60 MB per video run,
which is the same wall as before, just moved.

The goal is therefore achievable only if the asset's bytes never enter an execution n8n
saves — and the same measurement says why the signer cannot be n8n: a probe Code node
doing `require('crypto')` failed with `Module 'crypto' is disallowed`, so n8n cannot mint
a presigned URL. Garage accepts one (presigned PUT and GET both answered 200), so the
only missing piece is a signer, and the producer already holds the bytes.

## What Changes

- The **composer session server** SHALL upload each rendered artifact to object storage
  itself, as part of the turn that produced it, and SHALL report the object key in its
  response. n8n SHALL NOT fetch, decode or upload the bytes.
- The **session pod** SHALL reach Garage's S3 endpoint through an added egress rule, and
  SHALL hold a Garage key limited to writing `datahub-local-temp`.
- `agent_result` SHALL stop building a data URL; the asset SHALL carry the key, the byte
  count, the content type and its own status.
- The **still-image path** SHALL stop returning the model's image as a data URL in
  `omImage`, and SHALL carry it as binary.
- `saveDataSuccessExecution` SHALL return to `all` on the four workflows, with a measured
  bound on what a run then costs.
- `apply_workflow_changes.py` SHALL warn when a node field does not resolve, because
  `get_path` returns `None` for a mistyped path and the read-back then verifies the stray
  key it wrote.

## Capabilities

### Modified Capabilities

- `visual-studio`: the producer stores the asset and names it; the run is recorded again
  and no execution data carries an asset's bytes.
- `linkedin-post-publishing`: the approved asset's bytes are read from the object the run
  recorded, not from the response.

## Impact

- **`agents/adapters/pi-render/session-server.mjs`**, `session-lib.mjs`: an S3 PUT after
  the turn, driven by the request's destination; a failure is reported, never swallowed.
- **`agents/sympozium/`**: an egress rule for 3900 to `data`, and the credential's env
  and mount on the session.
- **`agents/n8n/workflows/visual_studio.workflow.json`**: `fetch_artifact`,
  `fetch_paired_artifact`, `prepare_uploads` and `upload_assets` are removed for the
  animated path; the raster branch keeps a binary-to-S3 step.
- **`agents/n8n/workflows/linked_in_post_sharing.workflow.json`** and
  `linked_in_image_creator.workflow.json`: the asset travels as binary; the publish path
  reads Garage by key.
- **`agents/n8n/scripts/test_storage_retention.py`**: rewritten around the new invariant.
- A live Garage key (live only — credentials are not in git).

## Non-goals

- The run table. It stays removed; the response plus the recorded execution are the
  record.
- `TemporalFiles`, still bounded by `File Webhook`'s one-hour rule.
- Changing what an asset *is*. Only where its bytes live and who writes them.

## Supersedes

`store-visual-studio-assets-in-s3` (archived 2026-10-14) put the upload inside n8n. Its
key convention, its two-day prune and its response contract all stay; the writer moves.
