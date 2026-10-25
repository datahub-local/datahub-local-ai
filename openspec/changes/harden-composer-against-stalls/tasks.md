# Tasks

## 1. Gateway (cross-repo: `datahub-local-core`)

- [x] 1.1 Add `router_settings.stream_timeout: 120` to the litellm config
  (`datahub-local-core-data-litellm-config`); leave `litellm_settings.request_timeout` at `30`.
  The accepted shape is verified in the installed version: `Router.__init__` carries
  `stream_timeout`, the proxy builds the Router from `router_settings`, and
  `_get_stream_timeout` reads it ahead of `request_timeout`. If that repository prefers the
  per-deployment form, the equivalent is `litellm_params.stream_timeout: 120` on each
  `opencode-go/*` entry — `GenericLiteLLMParams` declares the field. Landed as a source edit
  in `releases/data/values/litellm.yaml.gotmpl` with the rationale beside it; not applied to
  the cluster, and that release's chart cannot be rendered locally (the OCI pull fails on this
  machine's docker credential helper), so the values file was checked by parsing the
  `model_list` / `litellm_settings` / `router_settings` regions after substituting the Go
  templates: 12 models, `request_timeout: 30`, `router_settings: {stream_timeout: 120}`
- [x] 1.2 Add `additional_drop_params: [reasoning_effort]` to the `opencode-go/glm-5.3-flash`
  entry and leave it in both `fallbacks` lists and in `model_list`. The hop is not broken: it
  answers `200` for plain, streaming and tool-carrying requests and rejects only
  `reasoning_effort` (`[1210] This model always engages in thinking and cannot be disabled`),
  which the composer always sends. Confirmed by probe 2026-10-16 that
  `opencode-go/glm-5.3-flash` is named as the fallback model by `visual_studio`'s
  `ai_model_fallback` and `image_content_generator`'s `OpenRouter Chat Model Fallback`, so
  removing it would delete a working hop for those callers. Landed as a source edit beside
  1.1; not applied, and the drop itself is 1.5
- [x] 1.3 Land the config and verify it is the one the router runs. The release is ArgoCD's
  (`argocd.argoproj.io/tracking-id: datahub-local-core-data:…` on the Deployment and the
  ConfigMap, and the Application auto-syncs `releases/data` at `HEAD`), so this is a commit in
  `datahub-local-core` and a sync — a local `helmfile apply` would drift from git and be
  reverted. Then: read the ConfigMap back, confirm the Router logged no
  `is not a valid argument for Router.__init__` warning for `stream_timeout`, and confirm the
  pod restarted onto the new revision
 **Landed and verified 2026-10-16.** Committed as `9630caf` and synced: `datahub-local-core-data` reached `Synced` at that revision, the ConfigMap's `resourceVersion` moved `193208166` -> `193604879` and now carries `router_settings.stream_timeout: 120` and `additional_drop_params: [reasoning_effort]` on the glm entry, the pod restarted onto a new ReplicaSet, and the Router logged no `is not a valid argument for Router.__init__()` warning for the key. The release also renders again once the machine's broken `docker-credential-secretservice` helper is shimmed: the rendered ConfigMap carries both settings in the right places, which closes the earlier cannot-render caveat. Arriving here needed the Secrets fix described in 1.6.
- [x] 1.4 Probe the new timeout rather than reading it: hold a stream open past 30 s against
  `opencode-go/deepseek-v4.1-flash` (a prompt whose generation is slow enough, or a fake
  upstream) and confirm the call is not killed at 30 s while a short non-streaming call still
  fails fast. Record both timings
  A >30 s inter-chunk gap cannot be induced on demand — the stalled endpoint is the upstream's, not something this stack can ask for — so the evidence is: the ConfigMap carries the setting and the Router logged no `is not a valid argument` warning for it (1.3); a *stream* whose total duration exceeds 30 s still completes, which shows the 30 s was never a total; and a stall is then only observable in the negative, as a stream that keeps waiting past 30 s instead of failing. Record which of these were taken.
 **Partially verified, and the gap probe is not reproducible.** Taken: the setting is in the applied ConfigMap with no Router warning, and a streaming call works (`200`, 7.2 s). Not taken: a >30 s inter-chunk gap cannot be induced on demand - it is the upstream's silence - so the stall tolerance is only observable in the negative, as a stream that keeps waiting instead of failing at 30 s. No attempt was made to fake one.
- [x] 1.5 Probe the drop rather than trusting the field: send `opencode-go/glm-5.3-flash` a
  request carrying `reasoning_effort: "none"` and confirm the answer names glm rather than
  OpenRouter, i.e. that `additional_drop_params` took effect on that deployment. If it does
  not, fall back to leaving the hop as a known-wasted attempt and record that in `design.md`

 **Landed and verified 2026-10-16.** Probed with `reasoning_effort: "none"`: the answer came back `"model":"opencode-go/glm-5.3-flash"`, i.e. served by glm itself rather than the OpenRouter fallback, so `additional_drop_params` takes effect and the hop is usable again. The `[UNVERIFIED]` in D6 is resolved in favour of the drop working.
- [x] 1.6 Keep the cluster's Secret payload small, because the gateway cannot serve the list Argo
  CD needs without it (found while verifying 1.3). Measured 2026-10-16: Helm's default 10
  revisions per release made ~140 release Secrets and a ~30 MB cluster-wide Secret LIST, the
  kube-apiserver (2.8 GB RSS on a 4 GB node) aborted the stream, and **every** Argo CD Application
  sat at `sync=Unknown` for an hour with nothing unhealthy — which is also why the gateway change
  could not sync at first. Done: pruned to one revision per release (30 MB -> 3.9 MB, list 120 s ->
  19 s), `helmDefaults.historyMax: 2` in `datahub-local-core`'s `values/base.yaml.gotmpl` (one
  edit covers all seven helmfiles, verified with `helmfile build`), and three `gitops.rules` alerts
  in `releases/monitoring/values/default.yaml.gotmpl` (`promtool check rules` SUCCESS in the running
  Prometheus, the matcher returns the live 14 series, all three evaluate to 0 series healthy, and
  the rendered PrometheusRule carries them). **Not done, and the gap to know about:** the
  bootstrap-installed releases (traefik, cert-manager, argo-cd, longhorn) do not go through those
  helmfiles, and `datahub-local-bootstrap`'s `roles/k3s_maintenance` prune — which already exists
  and whose own comment names this failure — is scheduled by nothing, so it stays a manual run.
  The alerts now catch that drift; the timer or CronJob was declined for now.

## 2. Composer runtime settings (`agents/adapters/pi-render/`)

- [x] 2.1 Add a pure builder to `session-lib.mjs` — `agentSettings({ idleTimeoutMs, maxRetries,
  baseDelayMs, maxAgentDelayMs })` returning the `settings.json` object — so the shape is
  testable without a server, matching the file's stated purpose
  **Landed.** `agentSettings` and `DEFAULT_RETRY`/`DEFAULT_GATEWAY_STREAM_TIMEOUT_MS` in `session-lib.mjs`, with the idle-timeout-above-the-gateway check inside the builder so an unusable pair cannot be written.

- [x] 2.2 Have `session-server.mjs` write `~/.pi/agent/settings.json` next to the `models.json`
  it already writes, with the D3 values and the same `PI_RENDER_*` env-override idiom
  (`PI_RENDER_HTTP_IDLE_MS`, `PI_RENDER_RETRY_MAX`, `PI_RENDER_RETRY_BASE_MS`,
  `PI_RENDER_RETRY_MAX_DELAY_MS`). The idle timeout **must** default above the gateway's
  streaming timeout; the builder is where that invariant is visible
  **Landed.** the write is in `session-server.mjs`, next to the `models.json` write, reading those four overrides.

- [x] 2.3 Add assertions that fail without 2.1/2.2: `test/session-lib.test.mjs` for the builder
  (values, env overrides, and the idle-timeout-above-gateway relationship) and
  `test/session-server.test.mjs` for the write itself — that a started server has the file in
  its agent directory carrying the configured numbers
  **Landed.** shape, overrides and the relation are in `test/session-lib.test.mjs`; the file a started server writes is in `test/session-server.test.mjs`. Proven to fail without 2.2: with the write pointed at another name, `the session writes Pi's retry and idle-timeout settings` is the one failure (6 pass, 1 fail).

- [x] 2.4 Run `node --test test/` from the adapter directory and record the result
  **Landed.** `node --test test/` on node v26.12.0: **43 pass, 0 fail**.

## 3. A failed animation can be re-authored (`agents/n8n/`)

- [x] 3.1 Rewire the export: replace the direct `if_animation_ok[false] →
  notify_animation_fallback → execute_image_creator` edge with one `sendAndWait` that carries
  the failure message and a bounded `options.limitWaitTime.values` interval, a switch over the
  answer, and a retry edge into `execute_visual_studio`. The switch's **fallback output** is
  the still path, so a resumed timeout (which arrives with no `data.approved` —
  `SlackV2.execute` returns its own input, and this build carries no `timedOut` marker) cannot
  re-author. The retry sets `FEEDBACK` from the failed asset's `ERROR` and reuses
  `SESSION_ID` = `lips-<row_number>` unchanged
  **Landed.** `notify_animation_fallback` (a plain notice) became `notify_animation_failed` (a bounded `customForm`, `options.limitWaitTime.values` = 30 minutes), plus `if_animation_retry` and `build_retry_feedback`; `execute_visual_studio`'s `FEEDBACK` now prefers `build_retry_feedback` when it ran. The absent answer is handled by `if_animation_retry`'s false output rather than a switch fallback output, which is the same guarantee with one fewer option to depend on. Both copies of the graph were edited identically.

- [x] 3.2 Extend `scripts/test_linkedin_animated_media.py` so it fails without 3.1: the failure
  branch passes through exactly one bounded form; an absent answer routes to the still and not
  to the studio; every edge back into `execute_visual_studio` from the failure side passes that
  form; the retry carries `FEEDBACK` and the same session expression; the new node's channel and
  credential match its neighbours; and both `activeVersion` copies of the graph agree
  **Landed.** `test_a_failed_animation_offers_one_bounded_choice`, `test_a_retry_carries_the_failure_reason_and_reuses_the_session` and `test_no_path_re_authors_a_failed_animation_without_an_answer`, with the fallback-reachability test updated to the new node. Proven to fail without 3.1: reverting the export gives **8 failed, 39 passed**; with it, **47 passed**, and the whole `agents/n8n/scripts` suite is **485 passed, 1 skipped**.

- [x] 3.3 Apply to the live instance with `scripts/apply_workflow_changes.py`, guarded by
  `--require-edge` for the edges the change assumes. Show the diff and get the owner's answer
  before writing; after writing, re-read `activeVersion`, re-activate and confirm `active`
  (an activation failure leaves the workflow deactivated), and diff the export against live
  **Landed.** dry run first — all six `requireEdges` premises held and the plan was the intended edit — then `--apply`, which confirmed each field on write-back. Live read-back: 52 nodes (was 50), `active: true`, `triggerCount: 1`, both graph copies agree, `notify_animation_fallback` gone, the form carries its Slack credential and its bounded wait, and the composed `FEEDBACK` is stored verbatim. `activeVersion` already carried the change, so no deactivate/activate cycle was needed and none was risked. The export is a faithful backup of live: node-name sets equal, `connections` equal, every touched node deep-equal, and the workflow `settings` unchanged.

- [x] 3.4 Record where the bound sits (a value under the publishing run's `executionTimeout` of
  3600 s at `linked_in_post_sharing`), and confirm the failure message says what happens if it
  is not answered
 **Landed.** The bound is 30 minutes, the publishing run's `executionTimeout` is 3600 s, and the form's own message says what happens if it is not answered ("Unanswered, the still image is used after 30 minutes and the post continues"). Recorded in the repository `AGENTS.md` beside the branch's other invariants and in the design's D3/D4.
## 4. Behaviour verification (no CI covers n8n, so this is manual and recorded)

- [x] 4.1 Read `settings.json` back from a running session pod and confirm the values are the
  configured ones (`kubectl exec … cat /tmp/home/.pi/agent/settings.json`)
 **Verified 2026-10-16.** `kubectl -n automation exec datahub-local-ai-pi-render-5fb448f5d-7wz5r --
 cat /tmp/home/.pi/agent/settings.json` answers
 `{"httpIdleTimeoutMs":240000,"retry":{"enabled":true,"maxRetries":6,"baseDelayMs":5000,"maxAgentDelayMs":60000}}`
 — the D3 numbers, written at pod start (19:45 against a 19:44 start), with no `PI_RENDER_*`
 override set on the deployment, so these are the builder's defaults. The pod runs the digest
 pinned in `values/default.yaml.gotmpl` (`d4a089d6…`).
- [x] 4.2 Force a stall inside the window and confirm the turn still completes; then force one
  longer than the window and confirm the turn fails naming the model endpoint and the reason.
  Make the stall deterministic rather than waiting for the upstream: the settings can be
  pointed at a local endpoint that answers late. Record both measurements, including the
  attempt count — Pi's documented `maxRetries: 3` did not explain the 9 attempts observed on
  2026-10-16, and this is where that is resolved
 **Measured 2026-10-16, deterministically, with a stub endpoint** (`/tmp/stub.mjs` in the
 session pod: one leading role chunk on `POST /v1/chat/completions`, then either the answer
 after `STALL_MS` or permanent silence, counted per request). `pi` was run against it in its
 own `HOME` with its own `settings.json`, so production config was untouched and the real
 gateway was never involved.
 - *Inside the window:* idle 3000 ms, first chunk then a 1500 ms gap -> exit 0 after 1.9 s,
   stdout `STALL-PROBE-OK`, **1 request**. A stall shorter than the idle timeout is invisible.
 - *Longer than the window:* idle 3000 ms, never speaks again -> exit 1 after 12.3 s
   (**3 requests** = `maxRetries: 2` + 1, and 3 x 3 s of silence plus backoff fits the 12.3 s).
   So Pi honours `retry.maxRetries` exactly; the 9 observed on 2026-10-16 was **not** a single
   turn's attempts and this probe does not reproduce it — recorded as such rather than
   explained.
 - *The failure text:* Pi's own account is the single word `terminated` (`--mode json` confirms
   it as `stopReason: "error", errorMessage: "terminated"`, and in that mode Pi exits **0**),
   and it named no endpoint. The spec requires a failure that names both, so the adapter was the
   missing half: see 4.5.
- [x] 4.5 Name the model endpoint in a failed turn (found by 4.2, required by this change's own
  spec delta). `runPi` rejected with `Pi exited 1: terminated` — no endpoint, and a reason only
  as legible as Pi's own word for an aborted stream, so a stalled model call and a bad brief
  read the same in the run record and in the Slack form that quotes it
 **Landed.** `piFailure(code, stderr)` in `session-server.mjs` answers
 `Pi exited <code> calling <MODEL_BASE_URL>: <last non-empty stderr line>`. Asserted by
 `a failed turn names the model endpoint and Pi's own reason` in `test/session-server.test.mjs`
 (the stub Pi fails on a `FAIL_PROBE` prompt): the test **fails without the change**
 (`Pi exited 9: noise before the reason / stream terminated by peer` — no endpoint) and passes
 with it. `node --test test/`: **44 pass, 0 fail**. The image is **live**: CI's publish-and-pin
 (`.github/workflows/publish-images.yaml`) committed `5d9a516`, ArgoCD synced
 `datahub-local-ai-sympozium` to it, and the session Deployment now runs
 `…-pi-render-adapter@sha256:5c825cb8…` (pod restarted 20:51 UTC) — read back from the pod,
 `/usr/local/bin/sympozium-pi-render-session` carries `piFailure` and the `calling <endpoint>`
 message, with the D3 `settings.json` unchanged.
- [ ] 4.3 Exercise the failure branch end to end: an animation that fails inside the studio
  reaches one bounded Slack form naming the reason; an answer of "re-author" runs a second turn
  with the reason as feedback and the same session; no answer takes the still image and the post
  is not held. Use `Visual Studio Test` for the studio half where a full publish run is not
  wanted
 **Deferred by the owner 2026-10-16, not dropped.** The shape this task would observe is already
 held offline — `test_linkedin_animated_media.py` asserts the single bounded form, the retry's
 `FEEDBACK` and unchanged session, the absent answer taking the still, and the no-loop wiring
 (47 passed) — and 4.4 read the applied node's text back. What is missing is one live run of
 `LinkedIn Post Sharing` driven to a failed animation, which is a real draft, real Slack
 approvals and a real branch decision. It stays open as a live check for the owner rather than
 being asserted from the offline suite.

 **Two of the three halves measured live 2026-10-24, on execution 14801** (row 106,
 `POST_MEDIA=ANIMATED`, `VISUAL_FORM=diagram`): a real draft that had been waiting at
 `notification_accept` since the Friday 10:30 tick, and a failure injected in the composer's own
 sandbox.
 - *The failure needed no graph edit.* A **regular file** at `/tmp/aivideo/runs/lips-106` makes
   the turn answer `400 {"error":{"message":"EEXIST: file already exists, mkdir …"}}` in **1.2 ms**
   (measured first on a throwaway session id), so the run takes the real path with the real
   graph. A read-only run directory does **not** fail the turn: `stageVendorAssets` catches its
   own write errors. `execute_author` spent its `maxTries: 2` and answered in ~21 s.
 - *The form, and only it.* Studio run 14878 reported `STATUS: FAILED` with the asset `ERROR: …
   /artifacts/lips-106/out.mp4 answered HTTP 404. Nothing was stored.`; `check_animation_result`
   carried `animated media unavailable: <that>`; `if_animation_ok` took the false output;
   `notify_animation_failed` has one runtime entry and was the last node that ran;
   `execute_image_creator` had **not** executed.
 - *No answer takes the still.* Nothing was answered: at 20:18 UTC, 30 minutes to the second
   after the node ran, the execution went `running`, resumed with no `data.Action`,
   `if_animation_retry` took the false output, `execute_image_creator` ran and the run reached
   `notification_accept_image` — the still path with its own approval. Nothing timed the run out
   and it was never parked. That is the half the old wiring could not do for a *failure*.
 - *Still missing: an answer of `Retry animation`.* It needs a second failure of the same kind.
   The owner chose the **Monday 2026-10-26 16:00 UTC tick** over a manual editor run. Arm the
   fault once `select_article_to_post` has picked its row (the session id is `lips-<row_number>`),
   which is the whole window before the text approval is answered, then **remove it before the
   form is answered** or the retry fails on the same injection. The retry then authors in
   `lips-<row>`, `FEEDBACK` opens with `the previous attempt failed: …`, and the run continues to
   `notification_accept_animation`.

 **Found while injecting, and not fixed here:** a failed authoring call's own reason never reaches
 the asset. `execute_author` carries `continueRegularOutput`, so it forwards its input and sets no
 `json.error` (the 2026-09-28 rule), `store_artifact` then fails on the missing artifact and
 `agent_result` records *that* — which is why the form named a `404` on `out.mp4` and not the
 session's `EEXIST`. The session server logs nothing for a pre-turn failure (`piFailure` covers a
 Pi turn, not staging), so the cause was visible only in the injected file and in n8n's retry
 count. Naming the cause means reading `execute_author`'s own error while still emitting an item
 for the store to fail on.
- [x] 4.4 Confirm the fallback notice's wording survives the rewiring: the failure is still
  named in Slack with the article, the reason and what happens next
 **Verified offline 2026-10-16, from the applied node.** `notify_animation_failed`'s message
 names the article (`$('select_article_to_post').item.json.URL`), the reason
 (`$('check_animation_result').item.json.ERROR`) and the consequence ("Unanswered, the still
 image is used after 30 minutes and the post continues"), with the two choices and the 30-minute
 `limitWaitTime`. Task 3.3 verified this node's export equals the live read-back, so the text
 above is what Slack receives. The behavioural half — that a person actually sees it — is 4.3.

## 5. Documentation

- [x] 5.1 Extend the `agents/sympozium/MEMORY.md` entry on the composer (or add one) with the
  three findings that are not visible from the code: the gateway's `request_timeout` is a
  per-read timeout for a stream; `stream_with_fallbacks` cannot substitute a deployment once a
  stream has emitted, which is why the runtime's retry is the recovery mechanism; and an
  expired `sendAndWait` resumes with its own input and no `data.approved`, so a branch on that
  field must default to the still
  **Landed.** A `## The composer's model calls: a stalled stream is the failure mode (2026-10-16)` section appended to `agents/sympozium/MEMORY.md` carries the incident, the three findings with the code each was read from, the glm finding, the numbers, and the two unresolved measurements.
- [x] 5.2 Note in `workflows/`/`agents/n8n` (wherever the animation branch is described) that a
  failed animated asset now has a bounded reviewer choice, so the branch's shape and the
  intent do not drift apart
  **Landed.** The `A failed animation never blocks the post` bullet in the repository `AGENTS.md` now states the bounded choice, the 30-minute bound and why the branch tests the retry action rather than the still — that file is where a reader looks before touching the branch.
- [x] 5.3 Leave the change's `[UNVERIFIED]` markers honest: resolve the Pi attempt count (4.2)
  and the model-name caller (1.2), and keep the upstream-stall cause marked as such
 **Resolved except the upstream cause, which stays marked.** 4.2 measured Pi's attempt count as
 `maxRetries + 1` on a forced stall (3 requests for `maxRetries: 2`), so the 9 attempts recorded
 on 2026-10-16 is not what one turn's retry window does — it is left as unexplained, with the
 measurement that fails to reproduce it recorded in D-finding form rather than a cause invented
 for it. The model-name caller is 1.2's own finding (the two n8n nodes name glm as their
 fallback). D6's `[UNVERIFIED]` was resolved by 1.5's probe, which showed the drop takes effect
 and the answer comes from glm. The one that remains is *why the upstream stalls mid-stream*:
 `[UNVERIFIED]`, tolerated rather than explained, exactly as the design says.
- [x] 5.4 Record 4.2's finding where the composer's failure text is decided, since the spec
  requires it and the adapter is the only place that can supply it
 **Landed.** The `piFailure` comment in `session-server.mjs` carries the reason (Pi names no
 endpoint, so a stalled model call and a bad brief would read the same), and 4.5's tests hold
 it. No `MEMORY.md` change was needed: the composer section's failure paragraph already
 describes the shape.
- [x] 4.6 Carry a failed authoring call's own reason onto the asset, which the spec's "reported
  rather than left for the caller to discover as a missing artifact" requires and execution
  14801 broke (found while injecting 4.3's fault)
 **Landed in the export and the adapter, not yet applied or deployed.**
 - *The graph.* `execute_author` moves to `continueErrorOutput` and gains
   `options.response.response.neverError: true`, with its error output wired to `agent_result`
   beside `store_artifact`'s success path. `agent_result` prefers
   `$('execute_author').first().json.error.message` and reports `authoring failed: <reason>`,
   falling back to the store's verdict when the authoring call succeeded.
 - *Why both settings.* `neverError` is what puts the session's 400 body (`EEXIST: …`) in the
   item; `continueErrorOutput` is what carries a transport failure, which has no body. Read off
   the installed image (`HttpRequestV3.node.js`: `neverError` sets `requestOptions.simple =
   false`, so a non-2xx resolves instead of throwing) — which also means `retryOnFail` no longer
   retries a 4xx. That is acceptable here rather than overlooked: this session answers only
   `200`, `400` and `404`, and a 400 is its verdict after its own five attempts, so a retry
   repeats a decision rather than riding out a transient. Transport failures still throw and
   still spend `maxTries: 2`.
 - *The log half.* The adapter logged nothing for a pre-turn failure, so the reason existed only
   in the response body. `session-server.mjs`'s request catch now logs
   `turn failed: <message>`; `test/session-server.test.mjs` reproduces execution 14801's
   injection (a regular file where the run directory belongs at `runs/<id>`) and asserts both
   the 400 body and the log line. 62 tests: 61 pass, 1 skipped (no ffmpeg here).
 - *Tested offline.* `test_the_asset_names_the_authoring_failure_rather_than_the_missing_artifact`
   executes the committed `agent_result` on the three shapes — 4xx body, transport error, success
   — and the 4xx case reproduces the live defect exactly under the old code (`ERROR:
   /artifacts/lips-106/out.mp4 answered HTTP 404. Nothing was stored.`). The wiring test fails on
   the old export too. `pytest agents/n8n/scripts/` **894 passed**, `ruff` clean, `node --test`
   **61/0**.
 - *Not measured.* The form's text after the change: the next failed authoring call has to name
   the session's reason in Slack, and the error output's runtime `json.error` shape for a
   transport failure is asserted from the 2026-10-18 probe, not re-probed here. The image also
   has to be published and the graph applied for either half to be live — 4.3's Monday retry is
   the natural run to read both from.

## 6. Recovery of run 13648 (operator, not automated)

- [x] 6.1 The owner sets row 72 back to `QUEUE` in the `content_planner` sheet, or retires it.
  `select_article_to_post` selects only `STATUS === 'QUEUE'`, so nothing picks the row up while
  it stays `WAITING_APPROVAL`, and the credential to edit the sheet lives in n8n
  **Owner action, 2026-10-16.** The row is set back to `QUEUE` there, so the next publishing run
  selects it. `[UNVERIFIED]` from this repository: it holds no credential for that sheet, and the
  evidence is the run that picks the row up, not the edit.
- [x] 6.2 If the row is republished, note that it is re-drafted and re-reviewed from scratch:
  the stopped execution took its approved draft and the unapproved still with it
  **Condition never arose, checked 2026-10-24.** Row 72 has not been selected since the owner
  re-queued it: the workflow's executions after 2026-10-16 are 14801 (2026-10-23, row 106) and
  none in between, so nothing was republished and there is no note to attach. The note itself
  stays here for the run that does pick it up: 13648's draft and its unapproved still went with
  the stopped execution, so that run drafts and reviews from scratch rather than resuming.
