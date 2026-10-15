# Tasks

## 0. Reverted: the producer uploads

- [x] 0.1 The adapter's uploader is **removed**. `session-server.mjs` no longer reads
      `s3_key`/`s3_key_paired`, calls `@aws-sdk/client-s3` or reports `artifacts`;
      `session-lib.mjs` no longer carries `UPLOAD_PREFIX`, `isUploadKeyAllowed` or
      `artifactUploads`; `@aws-sdk/client-s3` is out of `package.json` and the lockfile.
      It was written, tested (48 tests) and deployed before the credential channel was
      measured to be closed, and it was left dormant for one step as the record of that
      dead end. It is a second, unreachable way to write to the bucket, and the policy it
      enforced now lives where it is actually used: `mcp_runner/s3.py` in the MCP
      repository. Adapter tests: 41, all green

## 1. The temp-bucket server (`datahub-local-ai-mcp`)

- [x] 1.1 `mcp_runner/s3.py`: `TempBucket` over `boto3` — path-style, the deployment's
      endpoint/region/bucket/prefix, `put_stream` (streamed, not held in memory),
      `head` and `presign_get` clamped to S3's seven-day maximum. The SDK signs; SigV4 is
      not reimplemented here
- [x] 1.2 The key policy lives in the client, not in the caller: a key outside the
      configured prefix is refused, and so is a nested one — the deployment prunes by
      listing the prefix with a `/` delimiter, so a nested object is never deleted
- [x] 1.3 Every destination value is read from the environment with **no default**, and
      all missing ones are named in one failure: a guessed endpoint or bucket writes to
      somewhere nobody prunes and reports a key no reader can resolve
- [x] 1.4 `servers/utils/tools/temp.py`: `temp_store(source_url, key, content_type?)`
      streams the fetch to a spooled file, refuses a non-200, refuses a body over the cap,
      and **refuses a zero-byte source** — an empty asset is a failed render, not a stored
      object
- [x] 1.5 `temp_retrieve(key, expires_seconds?)`: a signed URL, the size from a `HEAD` and
      the media type. The URL is credential-bearing while it lasts, and the description
      says so
- [x] 1.6 The answers are one line of `key=value` pairs and every failure is one line
      beginning `ERROR:`, so a workflow parses them rather than matching prose
- [x] 1.7 Budgets in `config.py`'s sizing table (`temp_store` 1024, `temp_retrieve` 1536 —
      a signed URL is the longer line), which the table refuses to start without
- [x] 1.8 Tests: the key policy, the refusals before any fetch, the declared-length cap, an
      empty body, a missing object, the seven-day clamp, and that the answer is one
      parseable line. `boto3` is faked for its *effects* — the object exists holding the
      bytes that were fetched
- [x] 1.9 `boto3` joins the dependency union, `servers/utils/` is picked up by the
      parameterised Dockerfile and by both CI lists, and the README carries the server and
      why it is the one server here that holds a credential
- [x] 1.10 Verified live: the server stored a real 60,629,049-byte render from the session
      and the signed URL returned it with the **same md5** (`dad4822b8499…`)
- [x] 1.11 The CI gate that would have caught a latent lint failure: `uv.lock` is
      gitignored in that repository, so CI re-resolves and picked up ruff 0.17.0, which
      reports a pre-existing unused `# noqa: DTZ007` in `servers/semantic/query.py` as
      RUF100. Fixed there (two commits: the directive, then the comment that itself
      contained the `# noqa:` sequence ruff parses)

## 2. Cluster: deployment, credential and reach

- [x] 2.1 `sympozium_mcp_servers.utils` in the values: the image, `toolsPrefix: utils`, no
      observability env and no Kubernetes reader
- [x] 2.2 `envSecret` in `mcpservers.yaml` — one `envFrom`, so a server that needs a
      credential takes it from one Secret rather than a key-per-knob list in the chart
- [x] 2.3 The live Garage key is read+write on `datahub-local-temp` **only** and lives in
      the Secret `mcp-utils-s3`; the key id is recorded in `MEMORY.md`, never the secret.
      Widened from write-only because `temp_retrieve` signs with the same key and Garage
      refuses a signed GET made with a key that cannot read
- [x] 2.4 The session's callers policy admits `mcpserver` / `<release>-mcp-utils` on 8080,
      named by instance rather than by `mcpserver` generally: the artifacts are readable by
      the caller and by this one server, and by nothing else
- [x] 2.5 `helmfile template` renders clean and the pod runs: `serving server=utils
      tools=2`, `1/1 Running`
- [x] 2.6 `MCP_UTILS_URL` on the n8n deployment in `datahub-local-core`, beside
      `PI_RENDER_URL` — the workflow reads it as `$env.MCP_UTILS_URL` rather than baking an
      address into an export

## 3. Studio graph

- [x] 3.1 `build_author_brief`: emits `ARTIFACT_KEY`, `PAIRED_ARTIFACT_KEY` and
      `STORE_URL` beside the URLs it already computed, keeping the
      `visual-studio/<RUN_ID>-<ASSET_TYPE>.<ext>` shape
- [x] 3.2 `agent_result`: no data URL and no binary read; it parses each store answer
      (`key=… bytes=…`) into `S3_KEY`/`S3_BYTES`, keeps the composer's report as
      `STORYBOARD`, and reports a failed store as **that asset's** ERROR
- [x] 3.3 `store_artifact` and `store_paired_artifact` (HTTP → `temp_store`) replace
      `fetch_artifact` and `fetch_paired_artifact`, keeping their `onError`, their notes
      and their positions
- [x] 3.4 `set_result` prefers an asset's own key, so the raster path's upload cannot blank
      a key the store already reported
- [x] 3.5 `prepare_uploads` and `upload_assets` are **removed from the studio**, and
      `merge_branches` feeds `set_result` directly. Keeping them looked like the small
      change — they skip any asset without a data URL, which after 3.2 is every agent
      asset — and it broke the run: with nothing left to convert, `prepare_uploads`
      emitted **zero items**, `upload_assets` and `set_result` never ran, and the webhook
      answered `No item to return was found` (execution 13401). A raster asset keeps the
      data URL the image model returned, because those bytes are made inside n8n and no
      store can fetch them; nothing read its key, and the LinkedIn image path takes its
      bytes from the image creator's `omImage`, not from the studio's copy
- [x] 3.6 Applied live with `--require-edge` on all six premises, re-read and diffed: draft
      and `activeVersion` both 31 nodes, `saveDataSuccessExecution: all`, still active

## 4. Publish path

- [x] 4.1 `check_animation_result` accepts the asset on `S3_KEY` and `STATUS`, and carries
      the key
- [x] 4.2 `presign_animation` (HTTP → `temp_retrieve`) and `animation_url` (the signed URL,
      split the way a caller does) feed `download_animation`, which fetches the URL as
      binary `data` under the name the four downstream nodes already reference
- [x] 4.3 The media type is read from `check_animation_result`, not from the download: a
      file response carries no JSON of its own, so asking the download node would always
      fall through to the image path
- [x] 4.4 No node in the publish path holds an asset as a data URL, asserted by test
- [x] 4.5 Applied live with `--require-edge`, re-read and diffed: draft and `activeVersion`
      both 50 nodes, still active

## 5. Recording

- [x] 5.1 `saveDataSuccessExecution: all` on `Visual Studio`; it stays `none` on
      `Visual Studio Test`, `LinkedIn Post Sharing` and `Visual Studio Prune`, whose
      payload still is an asset
- [ ] 5.2 **Measure the bound**: one composer run with `execution_data` and `binary_data`
      before and after. The run must move neither by an asset's size — the studio's
      execution is recorded and holds no bytes
- [ ] 5.3 Record the measured numbers in this change, and the invariant in `AGENTS.md`

## 6. Still path (open, and now explicitly a non-goal of the animated change)

- [ ] 6.1 Pick the still path's byte source: the model's `b64_json` decoded to binary, or a
      URL fetched as a file — there is no URL for the store to fetch today
- [ ] 6.2 Gate: does the image gateway accept `response_format: url`? If not, 6.1 is decided
      for us and the outcome is recorded in `design.md`'s still-path section
- [ ] 6.3 Assert the resulting per-post cost in `binary_data` is the expected ~0.9 MB, not
      more. Until then a still run inside a recording workflow costs its asset's bytes, and
      `LinkedIn Post Sharing` stays `none`

## 7. Tests and docs

- [x] 7.1 `test_storage_retention.py`: the workflows whose payload is an asset must not
      persist a successful one; the studio must record; and the studio's graph must carry
      no bytes, which is what makes recording safe
- [x] 7.2 `test_visual_studio_graph.py`: the agent branch reaches the store nodes, the
      result names an object rather than carrying one, and a deck stores both artifacts
- [x] 7.3 `test_linkedin_animated_media.py`: the publish path presigns and downloads, the
      media type comes from the check, and no data URL is required
- [x] 7.4 `apply_workflow_changes.py`: warn when a node field does not resolve — `get_path`
      returns `None` for a mistyped path, so a spec writing `jsCode` instead of
      `parameters.jsCode` created a stray top-level key and the read-back then verified it
      as success. Hit while applying the continuation fix on 2026-10-14. Two warnings and
      three tests; verified against the live workflow
- [ ] 7.5 `AGENTS.md`: the storage paragraph, the invariant, the credential's accepted risk,
      and the fresh-instance procedure
- [ ] 7.6 Full suites green: `pytest agents/n8n/scripts/`, `pytest agents/sympozium/tests/`,
      `node --test agents/adapters/pi-render/test/*.test.mjs`, the MCP repo's
      `pytest`/`ruff`, `openspec validate --all`

## 8. Carried from the archived change

- [ ] 8.1 Watch the first 04:00 `Visual Studio Prune` that meets a stale object: the delete
      is proven by probe, not yet by the schedule
- [ ] 8.2 `TemporalFiles` still holds bytes in a DataTable for `Visual Studio Test`;
      bounded by `File Webhook`'s one-hour rule, left alone
