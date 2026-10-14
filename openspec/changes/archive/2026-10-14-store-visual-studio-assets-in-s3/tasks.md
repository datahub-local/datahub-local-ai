# Tasks

## 1. Studio graph

- [x] 1.1 Add `prepare_uploads` (Code, both copies): one item per rendered asset, base64 data URL to binary, `S3_KEY` = `visual-studio/<RUN_ID>-<ASSET_TYPE>.<ext>`
- [x] 1.2 Add `upload_assets` (`n8n-nodes-base.s3`, `file:upload`, both copies): bucket `datahub-local-temp`, `fileName` = `{{ $json.S3_KEY }}`, binary `data`; no `onError`, so a failed upload fails the run
- [x] 1.3 Rewire `merge_branches -> prepare_uploads -> upload_assets -> run_record` (both copies)
- [x] 1.4 `run_record` (both copies): `RESULT` drops `IMAGE` and gains `S3_KEY`/`S3_BYTES`; the storyboard stays. It reads the keys from `prepare_uploads` — the S3 node's own output is `{success: true}` only, measured on the first live run, where the object landed and `S3_KEY` came back empty

## 2. Prune graph

- [x] 2.1 Add `list_assets` (`n8n-nodes-base.s3`, `file:getAll`, both copies): bucket `datahub-local-temp`, `options.folderKey` = **`visual-studio/`**
- [x] 2.2 Add `filter_old_assets` (Code, both copies): keep `LastModified` older than the same two-day window
- [x] 2.3 Add `delete_assets` (`n8n-nodes-base.s3`, `file:delete`, both copies): `fileKey` = `{{ $json.Key }}`
- [x] 2.4 Rewire `delete_expired_files -> list_assets -> filter_old_assets -> delete_assets` (both copies)

## 3. Error graph

- [x] 3.1 `record_failed` (both copies): `onError` is `stopWorkflow`, not `continueRegularOutput`. The API rejects an explicit `null` (measured: `nodes/0/onError Expected string, received null`), and an absent key is indistinguishable from one never set

## 4. Test

- [x] 4.1 `test_storage_retention.py`: the row carries no `data:` URL; the upload runs before the row; the prune lists and deletes the bucket on the row's window
- [x] 4.2 `test_visual_studio_graph.py`: the response still carries `ASSETS[].IMAGE` (the row is separable)
- [x] 4.3 `uv run -- pytest agents/n8n/scripts/ -q` — 335 passed; `node --test 'agents/adapters/pi-render/test/*.test.mjs'` — 40 passed
- [x] 4.4 Fix `apply_workflow_changes.py`'s connections read-back: it parsed the type as `main>` out of `<connections:main>`, so **every** connections change reported a false `MISMATCH` against a graph that had been written correctly. The new test fails without the fix

## 5. Credential

- [x] 5.1 Created the `s3` credential `ZwoiEY6W4mSYnTmW` (renamed live to `Garage`) — endpoint `datahub-local-core-data-garage.data.svc.cluster.local:3900`, region `homelab`, path-style, key from `mcp-s3-token`, verified read+write on all five buckets before use

## 6. Apply

- [x] 6.1 Applied the three workflows live with `scripts/apply_workflow_changes.py --changes --require-edge`, then re-read and diffed
- [x] 6.2 `active: true` on all three, and the new nodes and edges are in **both** the draft and `activeVersion`
- [x] 6.3 Verified the prune's S3 path end to end with a throwaway webhook probe over the same three nodes and a widened window: `{"success":true}`, bucket **9 objects / 17.42 MB -> 7 / 17,936 bytes**. The probe was deleted afterwards

## 7. Recover the table

- [x] 7.1 Emptied `visual_studio_table` through the supported path (a DataTable `deleteRows` probe, since the public API answers 405 on `DELETE /rows`): **202.5 MB / 12 rows -> 2.33 MB / 0 rows**
- [x] 7.2 Re-ran the studio twice. Run `13288` (new session, full composer turn, 24 min): row **7,799 bytes**, `STATUS=COMPLETE`, no data URL, response still 23 MB with the asset. Run `13294` (the cheap image path, after the `prepare_uploads` fix): row **1,840 bytes**, `S3_KEY='visual-studio/13294-image.png'`, `S3_BYTES=128260`, and the bucket gained the matching 128 KB

## 8. Docs

- [x] 8.1 `AGENTS.md`: the key layout, the four load-bearing properties, the measured prefix trap and the `record_failed` finding, replacing the sentence that said `RESULT` holds the data URL

## Follow-ups

- [ ] The 04:00 prune has run once since the apply and deleted its rows without error, but its S3 half matched nothing that night; 6.3 is what proves the delete. Watch the first night with a stale object in the bucket.
- [ ] `TemporalFiles` (0.83 MB) still holds bytes in a DataTable for `Visual Studio Test`. Bounded by `File Webhook`'s one-hour rule, so left alone.
