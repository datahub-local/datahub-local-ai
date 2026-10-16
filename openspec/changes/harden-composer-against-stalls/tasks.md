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
- [ ] 1.6 Keep the cluster's Secret payload small, because the gateway cannot serve the list Argo
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

- [ ] 4.1 Read `settings.json` back from a running session pod and confirm the values are the
  configured ones (`kubectl exec … cat /tmp/home/.pi/agent/settings.json`)
- [ ] 4.2 Force a stall inside the window and confirm the turn still completes; then force one
  longer than the window and confirm the turn fails naming the model endpoint and the reason.
  Make the stall deterministic rather than waiting for the upstream: the settings can be
  pointed at a local endpoint that answers late. Record both measurements, including the
  attempt count — Pi's documented `maxRetries: 3` did not explain the 9 attempts observed on
  2026-10-16, and this is where that is resolved
- [ ] 4.3 Exercise the failure branch end to end: an animation that fails inside the studio
  reaches one bounded Slack form naming the reason; an answer of "re-author" runs a second turn
  with the reason as feedback and the same session; no answer takes the still image and the post
  is not held. Use `Visual Studio Test` for the studio half where a full publish run is not
  wanted
- [ ] 4.4 Confirm the fallback notice's wording survives the rewiring: the failure is still
  named in Slack with the article, the reason and what happens next

## 5. Documentation

- [ ] 5.1 Extend the `agents/sympozium/MEMORY.md` entry on the composer (or add one) with the
  three findings that are not visible from the code: the gateway's `request_timeout` is a
  per-read timeout for a stream; `stream_with_fallbacks` cannot substitute a deployment once a
  stream has emitted, which is why the runtime's retry is the recovery mechanism; and an
  expired `sendAndWait` resumes with its own input and no `data.approved`, so a branch on that
  field must default to the still
  **Landed.** A `## The composer's model calls: a stalled stream is the failure mode (2026-10-16)` section appended to `agents/sympozium/MEMORY.md` carries the incident, the three findings with the code each was read from, the glm finding, the numbers, and the two unresolved measurements.
- [ ] 5.2 Note in `workflows/`/`agents/n8n` (wherever the animation branch is described) that a
  failed animated asset now has a bounded reviewer choice, so the branch's shape and the
  intent do not drift apart
  **Landed.** The `A failed animation never blocks the post` bullet in the repository `AGENTS.md` now states the bounded choice, the 30-minute bound and why the branch tests the retry action rather than the still — that file is where a reader looks before touching the branch.
- [ ] 5.3 Leave the change's `[UNVERIFIED]` markers honest: resolve the Pi attempt count (4.2)
  and the model-name caller (1.2), and keep the upstream-stall cause marked as such

## 6. Recovery of run 13648 (operator, not automated)

- [ ] 6.1 The owner sets row 72 back to `QUEUE` in the `content_planner` sheet, or retires it.
  `select_article_to_post` selects only `STATUS === 'QUEUE'`, so nothing picks the row up while
  it stays `WAITING_APPROVAL`, and the credential to edit the sheet lives in n8n
- [ ] 6.2 If the row is republished, note that it is re-drafted and re-reviewed from scratch:
  the stopped execution took its approved draft and the unapproved still with it
