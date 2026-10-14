# Tasks

## 1. Adapter: the session server uploads

- [x] 1.1 `session-lib.mjs`: a pure `signS3Request` — canonical request, signed headers, `x-amz-content-sha256`, the `amzDate` shape and a key-prefix guard. Verified two ways: its canonical request and string-to-sign match **botocore's `S3SigV4Auth`** for the same pinned request, and the headers it produces were exercised **live against Garage** from a pod holding the credential — `PUT 200`, `GET 200` with the exact body, `DELETE 204`. The published AWS `get-vanilla` vector is the wrong reference for S3: it does not sign `x-amz-content-sha256`, so it is deliberately not used
- [ ] 1.2 `session-lib.mjs`: `uploadArtifact()` — PUT the finished file to the destination the request names, bounded retries, returns `{key, bytes}` or an error. Refuses a key outside `visual-studio/`
- [ ] 1.3 `session-server.mjs`: after a turn, upload the artifact the run produced; put the key and byte count in the response, or the failure's reason
- [ ] 1.4 `session-server.mjs`: a blank destination means no upload (a local-first run keeps working); a configured destination that fails fails the turn's report, never a silent success
- [ ] 1.5 Env: `PI_RENDER_S3_ENDPOINT`, `_REGION`, `_BUCKET`, and the key from a mounted secret; nothing hardcoded
- [ ] 1.6 Tests in `agents/adapters/pi-render/test/`: vectors, prefix refusal, and a failure that is reported rather than swallowed

## 2. Cluster: reach and credential

- [ ] 2.1 Add an egress rule on the session pod for TCP 3900 to the `data` namespace, beside the existing two additive policies
- [ ] 2.2 Mount the Garage credential on the session (env from a secret) and render it from the chart's values, not inline
- [ ] 2.3 Create the live Garage key: write on `datahub-local-temp` only, no bucket creation; record the key id in `MEMORY.md`, never the secret
- [ ] 2.4 Verify from inside the session pod that a PUT to the exact key shape succeeds and a PUT to another bucket is refused
- [ ] 2.5 `helmfile template` renders clean, and the pod starts with the credential mounted

## 3. Studio graph

- [ ] 3.1 `build_author_brief`: emit the destination (`S3_KEY`, bucket) into `AUTHOR_BODY`, keeping the existing `visual-studio/<RUN_ID>-<ASSET_TYPE>.<ext>` shape and the paired key for a deck
- [ ] 3.2 `agent_result`: drop the base64 data URL entirely; read `S3_KEY`/`S3_BYTES` from the author response and keep the composer's report as `STORYBOARD`
- [ ] 3.3 Remove `fetch_artifact` and `fetch_paired_artifact`, and rewire the artist branch to the upload's own result
- [ ] 3.4 The raster branch keeps a binary-to-S3 step (its bytes are made inside n8n) and stops emitting a data URL
- [ ] 3.5 `merge_branches -> prepare_uploads -> upload_assets` is removed for the animated path; `set_result` keeps its shape
- [ ] 3.6 `--require-edge` guards on each step, applied live, then re-read and diffed; `activeVersion` carries the same graph

## 4. Publish path

- [ ] 4.1 `check_animation_result` branches on the asset's `S3_KEY` and `STATUS`, not on `IMAGE`
- [ ] 4.2 `linked_in_post_sharing`: an S3 download node (`Garage` credential, `datahub-local-temp`, key from the asset) feeding `convert_animation`, which becomes a naming step
- [ ] 4.3 The still path: `linked_in_image_creator` stops building `omImage` as a data URL and returns the image as binary; `convert_image` becomes a naming step
- [ ] 4.4 No node in the publish path holds an asset as a data URL, asserted by test
- [ ] 4.5 Applied live with `--require-edge`, re-read and diffed, both copies

## 5. Recording

- [ ] 5.1 Set `saveDataSuccessExecution` to `all` on `Visual Studio`, `Visual Studio Test`, `Visual Studio Prune` and `LinkedIn Post Sharing`
- [ ] 5.2 **Measure the bound**: one image run and one composer run, with `execution_data` and `binary_data` before and after. A composer run must move neither by an asset's size
- [ ] 5.3 Record the measured numbers in this change, and the invariant in `AGENTS.md`

## 6. Still path

- [ ] 6.1 Pick the still path's byte source: the model's `b64_json` decoded to binary, or a URL fetched as a file
- [ ] 6.2 Gate: does the image gateway accept `response_format: url`? If not, 6.1 is decided for us and the outcome is recorded in `design.md`'s still-path section
- [ ] 6.3 Assert the resulting per-post cost in `binary_data` is the expected ~0.9 MB, not more

## 7. Tests and docs

- [ ] 7.1 `test_storage_retention.py`: rewritten — no workflow emits an asset as a data URL; the success-data setting is on the four; the invariant is stated as an assertion rather than a comment
- [ ] 7.2 `test_visual_studio_graph.py`: the destination reaches the request; no data URL is built; the raster branch still stores
- [ ] 7.3 `test_linkedin_animated_media.py`: the publish path reads the key and the credential is wired
- [x] 7.4 `apply_workflow_changes.py`: warn when a node field does not resolve — `get_path` returns `None` for a mistyped path, so a spec writing `jsCode` instead of `parameters.jsCode` created a stray top-level key and the read-back then verified it as success. Hit while applying the continuation fix on 2026-10-14. Two warnings (a parameter missing its prefix; a path that resolves nowhere) and three tests; verified against the live workflow, where the first now fires on `build_author_brief:jsCode` and a real node field stays quiet
- [ ] 7.5 `AGENTS.md`: the storage paragraph, the invariant, the credential's accepted risk, and the fresh-instance procedure
- [ ] 7.6 Full suites green: `pytest agents/n8n/scripts/`, `pytest agents/sympozium/tests/`, `node --test agents/adapters/pi-render/test/*.test.mjs`, `ruff`, `openspec validate --all`

## 8. Carried from the archived change

- [ ] 8.1 Watch the first 04:00 `Visual Studio Prune` that meets a stale object: the delete is proven by probe, not yet by the schedule
- [ ] 8.2 `TemporalFiles` still holds bytes in a DataTable for `Visual Studio Test`; bounded by `File Webhook`'s one-hour rule, left alone
