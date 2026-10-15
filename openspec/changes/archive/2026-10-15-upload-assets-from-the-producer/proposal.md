# Proposal

## Why

`Visual Studio` carries `saveDataSuccessExecution: "none"`, so a **successful** run leaves
no record at all in n8n. That was set because the workflow's payload *is* the artifact:
`agent_result` builds `IMAGE: 'data:' + mime + ';base64,' + …`, and run `13356` returned
**80,838,754 characters** for a 60.6 MB file.

The archived S3 change moved the bytes to Garage, but not out of the workflow — the base64
string is still a node output, so it is still what n8n persists. And n8n persists *binary*
data too: measured on this instance, `binary_data` is **249 MB across 903 rows** and
`execution_data` **1060 MB across 1405 rows**, in a 1335 MB database. Enabling success
recording with the bytes still passing through n8n therefore adds ~60 MB per video run,
which is the same wall as before, just moved.

**Three routes were closed by measurement on 2026-10-15, and they are why this change is
shaped the way it is:**

- **A session pod cannot be given a credential.** `AgentRuntime.spec` has no `env` field,
  `HarnessSession.spec` has four fields and none of them is one, and
  `Agent.spec.session` is `port`/`protocol`. `Agent.spec.agents.default.env` and
  `spec.volumes`/`spec.volumeMounts` look like the answer and are **AgentRun-only**: the
  chart carried them, the app synced, the session pod was deleted so the controller
  rebuilt it, and the fresh pod still had no env and only the `tmp` mount. So the composer
  cannot upload its own artifact.
- **n8n as the courier stores the bytes.** `Visual Studio Test` was set to
  `saveDataSuccessExecution: all` and run once on the still path: `binary_data` went from
  900 rows to **906** and its payload grew by ~1 MB. A workflow that fetches an asset and
  uploads it stores the asset as surely as one that carries it in JSON.
- **An n8n Code node cannot move them itself.** It *can* `require('@aws-sdk/client-s3')` —
  the SDK is in the image and the task runner allows it — but the sandbox has no `fetch`
  and no `process.env`. (`crypto` is disallowed, which is also why n8n can never sign a
  presigned URL.)

What is left is a process that is **not** the workflow and **not** the model-driven
sandbox: a trusted MCP server with a credential of its own.

## What Changes

- A new server in `datahub-local-ai-mcp`, **`utils`**, SHALL move the bytes:
  `temp_store(source_url, key)` fetches a URL and writes it to the temp bucket, and
  `temp_retrieve(key)` signs a short-lived download URL. Its answers SHALL be one line of
  `key=value` pairs, because its callers are workflows rather than models.
- The server SHALL hold a Garage key **scoped to `datahub-local-temp` alone**, SHALL
  refuse a key outside the one prefix this deployment owns, and SHALL refuse a nested key
  — the prune lists a prefix with a `/` delimiter, so a nested object is never seen by it.
- The **session pod SHALL hold no credential at all.** Its artifacts are fetched by the
  server, which is admitted to the session's port by the callers policy.
- `agent_result` SHALL stop building a data URL; the asset SHALL carry the object key, the
  byte count and the media type, and SHALL report its own error when the store failed.
- `saveDataSuccessExecution` SHALL return to `all` on `Visual Studio`, which is what the
  whole change is for, and SHALL stay `none` on every workflow whose payload still *is* an
  asset: `Visual Studio Test`, `LinkedIn Post Sharing` and `Visual Studio Prune`.
- `apply_workflow_changes.py` SHALL warn when a node field does not resolve, because
  `get_path` returns `None` for a mistyped path and the read-back then verifies the stray
  key it wrote.

## Capabilities

### Modified Capabilities

- `visual-studio`: the asset is stored by a service and named by the run; the run is
  recorded again and no execution data carries an asset's bytes.
- `linkedin-post-publishing`: the approved asset is read from the object the run recorded,
  through a signed URL, rather than from the response.

## Impact

- **`datahub-local-ai-mcp`**: `servers/utils/` (two tools), `mcp_runner/s3.py` (the client
  and the key policy), `boto3` in the dependency union, the publish workflow's server
  lists, and tests.
- **`agents/sympozium/`**: the `utils` MCPServer in the values, an `envSecret` knob in
  `mcpservers.yaml`, the session's callers policy admitting that pod, and the live Secret.
- **`datahub-local-core`**: `MCP_UTILS_URL` on the n8n deployment, beside `PI_RENDER_URL`.
- **`agents/n8n/workflows/visual_studio.workflow.json`**: `store_artifact` and
  `store_paired_artifact` replace `fetch_artifact` and `fetch_paired_artifact`;
  `agent_result` carries keys; `set_result` prefers an asset's own key so the raster path's
  upload cannot blank it.
- **`agents/n8n/workflows/linked_in_post_sharing.workflow.json`**: `presign_animation` and
  `animation_url` fetch a signed URL, and `convert_animation` becomes `download_animation`.
- **`agents/n8n/workflows/visual_studio_test.workflow.json`**: the summary reports
  `S3_KEY`/`S3_BYTES`; its download link still serves only an asset that is a data URL.
- **Tests**: `test_storage_retention.py` splits the workflows that may record from those
  that must not; `test_visual_studio_graph.py` and `test_linkedin_animated_media.py` assert
  the new nodes and the absent data URL.
- A live Garage key (live only — credentials are not in git).

## Non-goals

- The run table. It stays removed; the response plus the recorded execution are the record.
- `TemporalFiles`, still bounded by `File Webhook`'s one-hour rule.
- Changing what an asset *is*. Only where its bytes live and who writes them.
- **The still-image path.** Its bytes are made inside n8n by the image model and returned
  as `b64_json`, so there is no URL for the store to fetch. A still run therefore still
  costs its ~0.9 MB in `binary_data`, and `LinkedIn Post Sharing` keeps `none` for the same
  reason: it must hold a video's bytes to hand them to LinkedIn.

## Supersedes

`store-visual-studio-assets-in-s3` (archived 2026-10-14) put the upload inside n8n. Its key
convention, its two-day prune and its response contract all stay; the writer moves out of
the workflow, and the earlier attempt in this change to make it the *producer* is recorded
in `design.md` as measured and rejected.
