# Design

## Context

See `proposal.md` for the incident and `specs/` for the behaviour contract. This records
only what shapes the approach, and it reconciles every claim against the software that is
installed, because each of the three gaps was found by reading the running system rather
than the documentation.

- The composer's turn is one streaming model call chain. `session-server.mjs` spawns
  `pi --print … --session-id <id>`, Pi streams to `MODEL_BASE_URL`
  (`http://datahub-local-core-data-litellm.data.svc.cluster.local:4000/v1`,
  `api: "openai-completions"`), and the gateway proxies to `https://opencode.ai/zen/go`.
- `litellm_settings.request_timeout: 30` in the gateway's config. Read from the installed
  package: `aiohttp_transport.py` maps it to `ClientTimeout(sock_connect=timeout.connect,
  sock_read=timeout.read, connect=timeout.pool)`, so for a stream it is the **inter-chunk**
  timeout; and `Router._get_stream_timeout` resolves, in order, the request's
  `stream_timeout`, the deployment's `litellm_params.stream_timeout`, the router's
  `stream_timeout`, then `request_timeout`.
- `GenericLiteLLMParams` (`litellm/types/router.py`) carries `stream_timeout` as
  "timeout when making stream=True calls", so the deployment-level form is a supported
  field and not a convention. `Router.__init__` takes it too, and the proxy builds the
  Router from `router_settings` (`litellm.Router(**router_params, …)`), validating each key
  against that signature: an unknown key is warned about and ignored, not fatal.
- `router.py::stream_with_fallbacks` falls back only when the failure is pre-first-chunk with
  nothing generated: `if not e.is_pre_first_chunk and (e.generated_content or
  _stream_chunks_have_generated_content(model_response.chunks)): raise e.original_exception from e`.
  The failing traceback contains exactly that frame, so the composer's own emissions are what
  disarmed the fallback.
- `LinkedIn Image Creator`'s `lmChatOpenAi` call is non-streaming and took the
  `ageneric_api_call_with_fallbacks` path in the same window, retried the primary and
  answered `200` at 11:59:09 from `openrouter/deepseek/deepseek-v4.1-flash`. The chain works;
  it is unavailable to a stream.
- Pi, in this image (`@earendil-works/pi-coding-agent@1.2.0`): `httpIdleTimeoutMs` defaults
  to `300000`; `retry.enabled` `true`, `retry.maxRetries` `3`, `retry.baseDelayMs` `2000`,
  `retry.maxAgentDelayMs` `60000`, `retry.provider.maxRetries` `0`. Settings live at
  `<agent-dir>/settings.json` = `~/.pi/agent/settings.json`, and that file does not exist in
  the session pod — `~/.pi/agent/` holds `auth.json`, `models-store.json` and the
  `models.json` the adapter writes.
- `linked_in_post_sharing.workflow.json`: `if_animation_ok[false] → notify_animation_fallback
  → execute_image_creator[0]`, and `switch_user_accept_animation[false] →
  notification_retry_or_cancel_animation → switch_user_retry_animation[0] →
  execute_visual_studio`. Its `settings.executionTimeout` is `3600`; `visual_studio`
  carries none.
- The Slack `sendAndWait` node is built on the shared implementation:
  `SlackV2.node.js` requires `utils/sendAndWait/descriptions` and calls
  `configureWaitTillDate(this)`, which reads `options.limitWaitTime.values`
  (`limitType: afterTimeInterval`, `resumeAmount`, `resumeUnit`). A bounded wait is therefore
  available on the node this change adds a form to.
- `SlackV2.execute` posts the message and then `await this.putExecutionToWait(waitTill);
  return [this.getInputData()]` — so the resume payload is the **webhook's** for a click, and
  the node's own input for a wait that expires. `grep -rho timedOut` over `n8n-nodes-base` in
  the running image returns nothing: this build marks an expired wait by the *absence* of
  `data.approved`, not by a flag.

## Gate findings

Reconciled on 2026-10-16 against the live cluster.

- **The 30 s is a per-read timeout, not a total.** It is why a compose turn's minutes-long
  generation is normally fine and a 30 s silence is fatal, and it is the reason the fix is a
  *streaming* timeout rather than a larger `request_timeout`.
- **A longer timeout alone does not save a mid-stream stall.** `stream_with_fallbacks`
  re-raises once content has been generated, so with a bigger `sock_read` the attempt simply
  waits longer for the upstream to resume. That is the intended behaviour here — waiting is
  what recovers — but it means the change buys patience, not a fallback.
- **Pi's attempt count does not match its documented defaults.** The transcript has 9 failed
  turns where `retry.maxRetries: 3` suggests 4 attempts, and the gaps (36-52 s against a 32 s
  call) fit backoff. It is recorded as an open question rather than explained, and the change
  does not depend on the answer.
- **`opencode-go/glm-5.3-flash` rejects `reasoning_effort`, and the composer always sends it.**
  Probed 2026-10-16: plain, streaming and tool-carrying requests all answer `200`, while the
  same request plus `reasoning_effort: "none"` answers `[1210] This model always engages in
  thinking and cannot be disabled; please use low, high, or max` and the router falls through
  to OpenRouter. It is the first fallback for the composer's model in both lists.
- **An export edit alone would be reverted.** The n8n half is an export edit *plus* an apply,
  since the nightly backup reads the live instance and writes this directory.
- **The gateway release is ArgoCD's, not the local helmfile's.** The litellm Deployment and
  its ConfigMap carry `argocd.argoproj.io/tracking-id: datahub-local-core-data:…`, and the
  `datahub-local-core-data` Application in `automation` auto-syncs `releases/data` at `HEAD`.
  A local `helmfile apply` would therefore put the cluster ahead of git and be undone by the
  next sync, so the gateway change lands by commit and sync — and this change holds the source
  edit only, with the operator's commit left to the owner. (The litellm release's chart is an
  OCI pull that also fails on this machine's docker credential helper, so a local render of it
  was not available either.)
- **`lips-72` cannot be recovered by re-running its producer.** The row sits at
  `WAITING_APPROVAL` (written by `update_status_waiting_approval`, never rewritten), and
  `select_article_to_post` selects only `STATUS === 'QUEUE'`, so nothing will pick it up.
  Recovering it is an operator edit of the sheet row plus a manual run; it is not this
  change's work and is not automated here.

## Goals / Non-Goals

**Goals:**
- Make a transient model-endpoint stall survivable by the authoring turn, without a human.
- Keep the existing promise that a failed animation never blocks the post, while giving the
  reviewer the option the rejection path already has.
- Change as little as possible: one gateway setting, one written settings file, one rewired
  branch.

**Non-Goals:**
- Fixing the upstream stall. This change tolerates it; `design.md`'s open question records
  that the cause is unmeasured.
- Any change to the composer's model, brief, prompt, skills, brand or graph.
- Recovering `lips-72`, or changing how a row leaves `WAITING_APPROVAL`.

## Decisions

### D1. Keep streaming; give the gateway a streaming timeout of its own

`router_settings.stream_timeout: 120` in `datahub-local-core`'s litellm config. The
deployment-level `litellm_params.stream_timeout` on the `opencode-go/*` entries is the
equivalent, verified in `GenericLiteLLMParams`; the router-level setting is one line for every
model and is preferred unless that repository's convention says otherwise.

120, not 300: the two are the same coverage at different shapes, because the window is
`retries × per-attempt timeout`, and the cost of a larger per-attempt wait is a slower
failure. At 120 s and six retries the window is ~12 minutes (the measured outage) with a
~17-minute bound; at 300 s it would be two attempts to cover the same stall and up to
~30 minutes to give up. One number, and the design's derivation is in D3.

*Alternatives considered:* raise `request_timeout` globally — rejected, it slows the failure
report for every short non-streaming call (the image path's calls answer in seconds) to buy
patience only the composer needs. Make the composer's call non-streaming — rejected: the same
timeout then covers the whole generation, so a compose turn of minutes would fail outright,
and Pi loses the liveness it uses to stream into `runPi`'s SSE path.

### D2. The composer's runtime settings are written by the adapter, from env

`session-server.mjs` already writes `models.json` from `PI_RENDER_*` overrides; it writes
`settings.json` the same way, through a pure builder in `session-lib.mjs` so the shape is
unit-testable without starting the server.

*Alternatives considered:* bake `settings.json` into the image — rejected, tuning a retry
window would need an image rebuild and the runtime's config would live in two places. Mount it
as a ConfigMap — rejected: a session Deployment is owned by the `HarnessSession` controller
and mounts only the session PVC, so the chart cannot attach a file to it.

### D3. The numbers, and the invariant between them

- gateway `stream_timeout: 120`
- Pi `httpIdleTimeoutMs: 240000` — **must** exceed the gateway's streaming timeout, or Pi
  kills the call before the gateway reports its own verdict and the retry sees a different
  error than the one being tuned.
- Pi `retry.maxRetries: 6`, `retry.baseDelayMs: 5000`, `retry.maxAgentDelayMs: 60000`

Derivation: the observed outage was ~12 minutes (11:51 → 12:03). At 120 s per attempt, six
retries span ≈ 12 minutes of stalls plus ≈ 3 minutes of backoff, so the window covers the
incident that motivated the change. The worst case — an endpoint that never answers — is
≈ 17 minutes before the turn fails, which is inside the publishing run's `executionTimeout`
of 3600 s and, when it is reached, still leaves the reviewer choice and the still fallback
intact.

### D4. The failed-animation choice is bounded, and an expired wait takes the still

The failure branch becomes one `sendAndWait` carrying the same message `notify_animation_fallback`
posts today (plus the choice), an `if` over the answer, and a retry edge into
`execute_visual_studio`. `options.limitWaitTime.values` is set to a bounded interval, and the
decision node's **unmatched** output is the still path.

Implemented as an `if` rather than a `Switch`, and that is the stronger shape here: a switch
would need `options.fallbackOutput: 'extra'` plus a reserved output index to express the same
thing (the option is supported in this version — `SwitchV3` pushes it — but it is one more
thing to depend on), whereas an `if` has exactly one non-matching output, and the sibling
result check in this same branch (`if_animation_ok`) is already an `if` reading the same kind
of field.

Two consequences, both deliberate:

- **A stall cannot retry.** A wait that expires resumes with the node's own input and no
  `data.Action` (D-finding above), which fails the condition, so the switch routes it to the
  still. Testing the retry action as an *approve* rather than testing "not the still" is what
  makes this safe: the inverse wiring would make an unanswered form re-author the animation
  forever — the exact class of branch-on-a-missing-field bug this repository has written down
  twice.
- **The promise holds.** An unattended failure proceeds to the still image on the timer, which
  is what `A failed animation falls back to a still` requires; the reviewer's choice is an
  addition to that path, not a gate in front of it.

*Alternatives considered:* an unbounded form — rejected, it parks the publish until someone
answers, which is the one thing the fallback exists to prevent. A second automatic studio
attempt — rejected as expensive and blind: the asset is optional, and the runtime now absorbs
the transient case that made an automatic retry look necessary. Offering the choice on the
image approval instead — rejected: it mixes two decisions in one gate and leaves the failure
unrecorded at the point it happened.

### D5. A failed re-author carries the failure reason

The retry sets `FEEDBACK` from the failed asset's own `ERROR`, which
`execute_visual_studio` already passes through verbatim to the brief. A composer that failed
for a reason its brief can address gets the reason; one that failed on the gateway gets it as
context rather than silence.

### D6. Make the dead fallback hop able to serve the caller it exists for

`opencode-go/glm-5.3-flash` is not protocol-broken: probed directly on 2026-10-16 it answers
`200` for a plain chat-completions request, for a streaming one, and for one carrying tools.
What it rejects is `reasoning_effort`:

```
litellm.BadRequestError: OpenAIException - Upstream request failed: [1210] This model always
engages in thinking and cannot be disabled; please use low, high, or max
```

and the composer always sends it (`compat.supportsReasoningEffort: true`, thinking level
`minimal` → `reasoning_effort: "none"`), so the hop could never serve the caller the chain
exists for, while it served the n8n model nodes (which send none) fine. The incident's
`ModelProtocolUnsupported` is the same rejection as the provider worded it then.

So instead of removing the hop, the gateway drops the parameter **for that hop only** —
`additional_drop_params: [reasoning_effort]` on the glm entry — because the primary honours
it and dropping it globally would put the gateway's reasoning back on the bill. The field is
read from the request's kwargs in the installed version; [UNVERIFIED] until the applied
config is probed with a `reasoning_effort` request and the answer names glm rather than
OpenRouter.

*Alternatives considered:* remove `opencode-go/glm-5.3-flash` from both `fallbacks` lists and
from `model_list` — rejected on the probe above: it would delete a working, same-subscription
hop for every caller that does not send `reasoning_effort`, including the two n8n nodes that
name it as their fallback model. Leave the hop as it is and accept the wasted attempt —
rejected as the smaller fix: the wasted attempt is a real cost on the one path that needs a
fallback most, and the fix is one field.

### D7. `lips-72` is an operator action, not part of this change

The row must be set back to `QUEUE` in the sheet (the credential lives in n8n, not here) and
a manual run started. The unapproved still image and the abandoned draft die with the stopped
execution, so the row will be re-drafted and re-reviewed. Recorded so the incident has an
end, not automated.

## Risks

- **The gateway half is cross-repo and cannot be verified from here.** Until it lands, the Pi
  idle-timeout change alone changes nothing, because the gateway's 30 s verdict still arrives
  first. The apply order is gateway, then adapter.
- **A stalled endpoint now costs up to ~17 minutes** before the turn reports failure. That is
  deliberate (patience is the recovery mechanism) and bounded inside the caller's budget, but
  it is a visible change in how long a broken composer takes to fail.
- **One more reviewer interaction.** The failure form adds a Slack gate that the fallback path
  did not have; its bounded wait is what keeps it from becoming a block.
- **A loop is possible if the switch is wired wrongly** (D4). It is asserted offline, because
  the failure it produces — an unattended form re-authoring forever — is invisible until the
  tokens are spent.

## Open questions

- **Why the upstream stalls mid-stream is not measured.** `[UNVERIFIED]` — the change
  tolerates the stall rather than explaining it; a later change may find that a different
  deployment or provider setting removes it entirely.
- **Whether Pi's `retry.*` settings change the observed attempt count is now measured for the
  settings themselves, and the original discrepancy is not reproduced.** 4.2's forced stall
  against a stub endpoint gave exactly `maxRetries + 1` requests (3 for `maxRetries: 2`), so the
  settings are honoured; the 9 attempts seen on 2026-10-16 therefore came from something other
  than one turn's retry window (`[UNVERIFIED]` — most likely more than one turn, but that is not
  established).
- **A failed turn named no model endpoint until 4.5.** Pi's own account of an aborted stream is
  `terminated` and carries no endpoint, so `runPi`'s message did not satisfy this change's own
  "names the model endpoint and the reason" requirement. Found by 4.2's probe rather than by
  reading, and closed in the adapter (`piFailure`) with a test that fails without it.
- **Which of `router_settings.stream_timeout` and `litellm_params.stream_timeout` suits
  `datahub-local-core`** is that repository's call; both are supported by the installed
  version, and the deployment-level form is the fallback if the router-level key is refused.
  The router-level form was taken and 1.3 verified it applies with no Router warning.

## Definition of done

- `openspec validate --all` passes with this change present.
- The gateway change is applied and its effect is read back from the config and from a probe
  that stalls (a stream that waits longer than 30 s without dying).
- The composer's `settings.json` is present in a session pod and carries the configured values,
  read back with a shell into a live session.
- A forced stall inside the retry window produces a completed turn, and a stall longer than the
  window produces a failed turn that names the reason — both measured, not reasoned.
- The failure branch is wired as designed and applied; `test_linkedin_animated_media.py` fails
  without the wiring and passes with it.
- The export and the live instance agree after the apply (the backup's own graph).
- Every `[UNVERIFIED]` above is either resolved or still marked as such.
