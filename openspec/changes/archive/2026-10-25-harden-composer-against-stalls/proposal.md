# Proposal

## Why

On 2026-10-16 the Visual Studio composer produced nothing for `lips-72` (run `13648`), and
the failure cost the article its animation. The evidence, all measured:

- `agents/adapters/pi-render` staged the run directory and the composer read the framework
  skills, then every authoring attempt died: the transcript holds **9** consecutive
  `stopReason: error` turns (`litellm.APIConnectionError … Timeout on reading data from
  socket`), 11:51:26 → 11:56:46, and `/tmp/aivideo/runs/lips-72/` holds only `gsap.min.js`
  and `assets/fonts` — no `index.html`, so no render, so the caller's
  `GET /artifacts/lips-72/out.mp4` answered `404`.
- The gateway's own log matches those 9 one-for-one. `litellm_settings.request_timeout: 30`
  is the cause: for a streaming call it lands as aiohttp `sock_read`
  (`aiohttp_transport.py` builds `ClientTimeout(sock_connect=…, sock_read=timeout.read, …)`),
  i.e. the gap **between chunks**, and the upstream
  (`https://opencode.ai/zen/go`, `opencode-go/deepseek-v4.1-flash`) went silent for longer
  than that, nine times in a row.
- The gateway's fallback chain could not help, and this is the discovery that matters most:
  `router.py::stream_with_fallbacks` falls back **only** when the error is pre-first-chunk
  with nothing generated —
  `if not e.is_pre_first_chunk and (e.generated_content or _stream_chunks_have_generated_content(...)): raise e.original_exception from e`.
  The composer's stream had already emitted a sentence and then stalled, so the router
  re-raised the provider error and the client got a hard failure, retry and fallback both
  bypassed. In the same minutes the **non-streaming** path in that same process did use the
  chain: `LinkedIn Image Creator`'s call retried the primary and answered `200` at 11:59:09
  from `openrouter/deepseek/deepseek-v4.1-flash`.
- Pi was not the one cutting the call. Its own HTTP idle timeout defaults to
  `httpIdleTimeoutMs: 300000`, and its retry settings are at their defaults
  (`retry.maxRetries: 3`, `baseDelayMs: 2000`, `maxAgentDelayMs: 60000`,
  `retry.provider.maxRetries: 0`) because the adapter writes only `~/.pi/agent/models.json`
  — `~/.pi/agent/settings.json` does not exist in the session pod.
- `linked_in_post_sharing` then did what it is built to do: `if_animation_ok[false] →
  notify_animation_fallback → execute_image_creator`, a Slack notice naming the reason and a
  still image taken to its own approval. That fallback is deliberate. What is missing is the
  other half the branch already has for a **rejected** animation: `switch_user_accept_animation
  [false] → notification_retry_or_cancel_animation → switch_user_retry_animation → execute_visual_studio`.
  A rejection can ask for a re-author; a **failure** cannot, so a transient gateway stall
  permanently downgrades the post's media.

Both halves are one-sided: the gateway is impatient with a stream it could have waited for,
and the pipeline has no way to ask for the asset again after a failure.

## What Changes

- **The gateway applies a streaming timeout of its own, larger than its request timeout.**
  `stream_timeout` is a first-class setting in the installed version: `GenericLiteLLMParams`
  carries it per deployment, `Router.__init__` accepts it, and `Router._get_stream_timeout`
  resolves request → deployment → router → `request_timeout`. The change is one setting in
  `datahub-local-core`'s litellm config (a different repository), and it is the only knob
  that lets a stalled stream recover instead of dying at 30 s.
- **The composer's runtime carries explicit Pi settings**, written by
  `agents/adapters/pi-render/session-server.mjs` next to the `models.json` it already writes:
  a retry window that outlasts a stall of several minutes, and an HTTP idle timeout that
  exceeds the gateway's streaming timeout so the gateway's verdict always arrives first.
- **A failed animated asset asks the reviewer, and the answer is bounded.** The failure
  branch gains the retry the rejection branch already has, carrying the asset's own `ERROR`
  as `FEEDBACK`. Its wait is limited, and a wait that expires routes to the still image, so a
  failed animation still cannot block the post.
- **The dead fallback hop is repaired.** `opencode-go/glm-5.3-flash` rejects
  `reasoning_effort`, which every composer request carries (`[1210] This model always engages
  in thinking and cannot be disabled`), so as the composer's first fallback it could never
  succeed — while serving the callers that send no such parameter. The gateway drops the
  parameter for that hop alone.

## Capabilities

### Modified Capabilities

- `agent-authored-compositions`: the authoring turn carries its own retry window and idle
  timeout, and the gateway distinguishes a streaming timeout from a request timeout, so a
  transient stall is survived rather than reported.
- `linkedin-post-publishing`: a failed animated asset is reported with a bounded reviewer
  choice between re-authoring the animation and taking the still fallback.

## Impact

- **`datahub-local-core`** (cross-repo): `litellm_settings.request_timeout` stays as it is;
  add `router_settings.stream_timeout: 120`, and add
  `additional_drop_params: [reasoning_effort]` to the `opencode-go/glm-5.3-flash` entry so the
  first fallback can serve the caller it exists for. This repository cannot render that
  release's chart (an OCI pull fails on this machine's credential helper), and it cannot
  verify the gateway beyond its logs; the config delta and the checks are recorded in
  `design.md` and in the change's tasks.
- **`agents/adapters/pi-render/session-server.mjs`**: writes `~/.pi/agent/settings.json`
  (retry + idle timeout), with the same env-overridable idiom as the `models.json` values
  already there. `session-lib.mjs` gains the pure builder so it is unit-testable, matching
  that file's stated purpose.
- **`agents/n8n/workflows/linked_in_post_sharing.workflow.json`**: the failure branch is
  rewired — one bounded `sendAndWait` whose timeout reaches the still, a switch over the
  answer, and a retry edge into the existing `execute_visual_studio`. Export edit plus a live
  apply, since an export edit with no apply behind it is a revert waiting for the next backup.
- **`agents/n8n/scripts/test_linkedin_animated_media.py`** and
  `agents/adapters/pi-render/test/`: assertions that fail without the wiring.
- **No change** to the studio's node graph, the asset registry, the brand, the prompts, or
  the composer's model. Pinning the composer to the `openrouter/deepseek/deepseek-v4.1-flash`
  deployment was considered and declined: it moves the composer off the gateway's primary
  deployment without addressing why a stall becomes a hard failure.

## Non-Goals

- Making the router fall back *mid-stream*. That is upstream behaviour (`stream_with_fallbacks`
  cannot swap deployments once chunks have been emitted to the client) and not ours to change.
- Switching the composer to a non-streaming call. It would restore the retry+fallback path,
  but the same 30 s then covers the whole generation, and a compose turn takes minutes — so it
  needs this change's timeout work anyway while giving up Pi's liveness.
- A second automatic studio attempt inside the workflow. The asset is expensive and optional;
  the reviewer decides, and the runtime is the thing that should absorb a transient stall.
- Recovering `lips-72`. That is an operator action on the queue row, recorded in `design.md`.
