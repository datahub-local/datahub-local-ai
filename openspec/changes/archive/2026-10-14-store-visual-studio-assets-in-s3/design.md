# Design

## Context

The studio's asset travels as a base64 data URL in the item stream. `run_record` builds
the row's `RESULT` from the merged asset items (`JSON.stringify(items)`), `record_run`
writes it with `autoMapInputData`, and `set_result` builds the **response** separately
from `$('merge_branches').all()` as `{RUN_ID, STATUS, ASSETS}`. So the row and the
response are already separable: `record_run` is not terminal, and no consumer reads the
row. `LinkedIn Post Sharing` calls the studio with `executeWorkflow` and reads
`ASSETS[].IMAGE`, so the response must keep the bytes.

## Gate findings

- **The response does not depend on the row.** `set_result` reads `merge_branches` by
  name, so shrinking `RESULT` cannot change what the caller receives. Verified by
  reading both nodes.
- **`record_run` is not terminal.** `record_run -> set_result`; the terminal node is
  `set_result`.
- **`file:getAll` sets `qs.delimiter = '/'`.** Read off the installed node
  (`n8n-nodes-base/dist/nodes/S3/S3.node.js`), so a listing is one level deep: a key
  nested under two prefixes comes back as a `CommonPrefix`, not as an object with a
  `LastModified` to prune on. The key layout is therefore
  `visual-studio/<RUN_ID>-<ASSET_TYPE>.<ext>` — exactly one `/`.
- **The S3 node's parameter names**, read off the installed node's own description:
  `file:upload` takes `bucketName`, `binaryData`, `fileName`, `binaryPropertyName`;
  `file:delete` takes `bucketName`, `fileKey`; `file:getAll` takes `bucketName`,
  `returnAll`, `options.folderKey` (mapped to `qs.prefix`).
- **`datahub-local-temp` exists and the key can write it.** Listed through Garage's
  admin API: five buckets, and the key in `automation/mcp-s3-token` has `read=True
  write=True` on all five.
- **`continueRegularOutput` forwards the input unchanged**, so a failed upload would
  still hand `run_record` a key for an object that was never written. That is why the
  upload is not marked with it (see Decisions).
- **The measured cost.** 12 rows, 195 MB of payload: four rows of 32-34 MB (the manga
  and deck runs) against eight of 4-10 MB.

## Decisions

- **Upload before the row, and let a failed upload fail the run.** The row is the
  record; a run whose record cannot be written is a broken run, and the stack already
  depends on Garage for bronze/silver/gold, so the studio failing with it is the
  coupling that exists rather than a new one. `continueRegularOutput` would need a
  success marker the node does not set, and would hide the failure exactly the way
  `record_failed` hid this one.
- **The row keeps the storyboard.** `RESULT` exists so a bad visual is diagnosable, and
  that text is cheap; only `IMAGE` and the byte count move out.
- **`record_run` keeps `autoMapInputData`.** The row shrinks because `run_record` stops
  putting bytes in `RESULT`, not because the mapping changes — one less thing to keep
  in step.
- **The prune lists one level and deletes on `LastModified`.** Same two-day window as
  the rows, so an object never outlives its row.
- **A new `s3` credential rather than the HTTP node with SigV4.** The credential is one
  object with the endpoint, region and key; signing by hand in a Code node is the same
  work with more places to be wrong.

## Risks

- **The bucket grows if the prune stops running.** The prune is a scheduled workflow
  with `settings.errorWorkflow` unset at the time of writing; the objects are deleted by
  `LastModified`, so a prune that never runs leaves them. The row window is unchanged, so
  the table is safe either way.
- **`prepare_uploads` builds binary in a Code node.** This instance keeps binaries out of
  band (`binary.data` is a `database:<id>` reference), which is why `agent_result` reads
  bytes with `getBinaryDataBuffer`. `this.helpers.prepareBinaryData` is the supported
  way to create one, and the upload is the only consumer.
- **An empty stream.** A run where every asset failed has no bytes to upload;
  `prepare_uploads` returns nothing and the upload node is skipped. `run_record` must
  read the keys by name and tolerate their absence.

## Open questions

- None. The response contract, the row contract and the retention rule are all
  unchanged in shape.

## Definition of done

- The row for a rendered run carries no `data:` URL and names the object.
- The object is in `datahub-local-temp` and the response still carries the asset.
- The prune deletes an object older than the window and leaves a fresh one.
- `visual_studio_table` is under its cap and a run records again.
- `uv run -- pytest agents/n8n/scripts/ -q` passes.
