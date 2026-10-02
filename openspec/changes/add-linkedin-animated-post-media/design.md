# Design

## Context

See `proposal.md` for motivation. The constraints below shape the approach and were read out of the running system, not assumed.

**The LinkedIn pipeline today** (`agents/n8n/workflows/linked_in_post_sharing.workflow.json`, live `oxARWWyxenKgmv6A`, 30 nodes): schedule or manual → `read_articles_sheet` (`content_planner` / `content_queue`, range auto-detected) → `select_article_to_post` (returns the whole chosen row, so a new column needs no code change) → `update_status_in_progress` → `download_content` → `execute_post_creator` → `check_subworkflow_error` → Slack double approval → `execute_image_creator` → `check_subworkflow_error_image` → `convert_image` (data URL → binary, hardcoded `image/png`) → `notification_sent_image` (Slack file) → `notification_accept_image` (double approval) → `switch_user_accept_image` → `send_2_linkedin_omImage` (`shareMediaCategory: IMAGE`, `binaryPropertyName: {{ $('convert_image').item.binary.data }}`) → `send_published_notification_a` → `update_status_published_a`. A rejection goes to `notification_retry_or_cancel_image` (custom form: Action Retry/Cancel + Feedback) → `switch_user_retry_image` → back to `execute_image_creator` with the feedback. `settings`: `errorWorkflow: yOLSrRQsp4rv1Wjv` (LinkedIn Post Sharing Error), `executionTimeout: 3600`, `binaryMode: separate`.

**The studio, as measured on 2026-10-01** (a sub-workflow probe with a frozen spec, since that is the call shape this change uses): called with `CONTENT`/`ASSET_TYPES`/`FEEDBACK`/`SPEC_JSON`, it returns `{RUN_ID, STATUS, ASSETS[]}`; an animated asset carries `{ASSET_TYPE, STATUS: RENDERED, FORMAT, CONTENT_TYPE, DURATION_MS, FRAME_COUNT, WIDTH, HEIGHT, IMAGE}` with `IMAGE` a `data:<mime>;base64,` URL. A requested-but-unavailable type returns that asset with `STATUS: UNAVAILABLE` and `ERROR: 'unavailable: no video encoder in this environment'`, and the run's own `STATUS` is then `PARTIAL` — so `PARTIAL` is normal and is never a failure signal. The probe produced 3 assets in 43 s and a 36-frame, exactly 3000 ms animated WebP at 1200×1500 (verified with `webpinfo`), and left `~/.n8n-files` empty.

**The assembler** (`build_assemble` in `visual_studio.workflow.json`) builds one command that tries `img2webp` and falls back to `gm convert`. The registry declares `format` per type but the assembler ignores it — the encoder is chosen by what succeeds, so a `format: gif` type still yields WebP.

**The animation budget** is a registry value: 12 fps / 36 frames / 1200 px, `max_types_per_request: 3`.

**Browserless is a shared dependency, and its failures read as the studio's.** During the 2026-10-01 rollout of `browserless/chromium` v2.57.0 the browser was transiently unable to launch Chromium (`Timed out after 30000 ms while waiting for the WS endpoint URL to appear in stdout`), and every browser-rendered asset failed with the studio's generic `frame capture failed` — a message that names neither the browser nor the real cause. A retry minutes later passed for both types. So a capture failure is diagnosed from the chromium pod's log or the puppeteer node's error, not from the asset's `ERROR` string, and a single occurrence is worth retrying before it is treated as a defect in the type.

**The GIF encoder's memory is not the constraint it looked like.** Measured 2026-10-01: `gm` assembling 36 frames at 1200×1500 into an animated GIF was OOM-killed (exit 137) — but in the **main** n8n container, which is capped at 1Gi, and only because that command was run there by hand. Studio executions do not run there: the instance is in queue mode with `offload_manual_executions_to_workers: true`, the frames of every test run appeared in the **worker** pod's `~/.n8n-files`, and the worker carries `requests == limits == 8Gi` (Guaranteed QoS) with zero restarts. The main pod's one OOM (lastState `OOMKilled`, 2026-10-01T18:35Z) is that manual command. So the GIF branch has ~8× the memory that killed the manual attempt, the 35M-pixel LinkedIn budget is comfortable inside it, and task 1.4 measures the peak to record a number rather than to clear a known ceiling.

## Gate findings

Two unknowns decide the numbers below, and neither can be settled from this repo:

- LinkedIn's media-support page lists GIF, JPEG, PNG and WEBP as supported image types but does not say whether an **animated WebP** plays in-feed. → We publish **GIF**, which the same page documents, and treat animated WebP on LinkedIn as `[UNVERIFIED]`. Recorded as an open question for the first live verification.
- The same page caps a GIF at "500 frames or 36,152,320 pixels". Read strictly as a whole-animation budget, the studio's default type is over it: 36 frames × 1200×1500 = 64.8M px. → A dedicated type declares 24 frames at 1080×1350 = 35.0M px, inside the cap under the strict reading and harmless if the cap is per-frame.

## Goals / Non-Goals

**Goals:**
- A queued post may be published with a studio-rendered animated infographic as its media, opt-in per row, with the existing still-image path untouched as the default and as the fallback.
- The asset published to LinkedIn satisfies the platform's documented GIF limits by construction, not by hoping.
- The reviewer sees the motion and can send it back with feedback, exactly as the still image works today.

**Non-Goals:**
- Multi-media or carousel posts: the LinkedIn node takes one binary, and this change does not attempt a second media item.
- Changing the studio's request or response contract. The only studio change is which encoder the assembler picks, and only for types that declare it.
- `motion_clip` / video: still unavailable (no encoder in the n8n image).
- Anything about the blog pipeline (`add-content-writer-agent`) or the studio's own run record.

## Decisions

### D1. Media choice is opt-in per queued row, and defaults to today's behaviour

`content_queue` gains a `POST_MEDIA` column. Blank or `STATIC` publishes the post exactly as today; `ANIMATED` requests the animated media. `read_articles_sheet` auto-detects the range and `select_article_to_post` returns the whole row, so no read node changes.

*Alternatives considered:* a constant ANIMATED for every post — rejected; it would silently change the media of every queued post to a capability that is `[UNVERIFIED]` on the platform, and the writer's intent ("this one is a diagram") is per row. A new column on a different page — rejected; the row is the unit of work here.

### D2. A dedicated registry type declares GIF and the LinkedIn budget

`datasets/visual_types.json` gains `diagram_animated_linkedin`: same authoring and template as `diagram_animated`, `format: gif`, `budget: {fps: 8, frames: 24, viewport: 1080}` → 1080×1350, 3 s, 35.0M px total.

*Alternatives considered:* reuse `diagram_animated` — rejected; over the pixel cap under the strict reading and animated WebP is unverified on the platform. A per-request budget parameter on the studio — rejected; the registry is the type axis, and a caller-set budget makes an artifact's size the caller's problem to get right. A separate `gif` type for everything — rejected as speculative; only the LinkedIn caller needs it.

### D3. The declared format selects the encoder (studio change)

`build_assemble` reads the type's declared `format`: a `gif` type assembles with `gm` first and falls back to `img2webp`, a `webp` type keeps today's `img2webp`-then-GM order, and an absent or unknown `FORMAT` behaves as `webp` so no caller regresses. Both encoders now receive the whole declared duration: `gm` takes a per-frame `-delay` (centiseconds) with the remainder spread over the last frames, exactly as the WebP path already spread milliseconds, so 3000 ms over 24 frames is 12 frames at 12 cs + 12 at 13 cs rather than 24 at 13 cs. The requirement change is a MODIFIED requirement on the `visual-studio` capability.

Measured 2026-10-01 on the literal command the patched code emits, over 24 JPEG frames at 1080×1350: 4 s, peak 363,061,248 bytes (≈346 MiB) in a container capped at 512Mi, output 7,088,265 bytes. The same probe container has `gm` but no `img2webp` (that module is installed by n8n's entrypoint, which the probe bypassed), and there a `webp` type produced a GIF — which is the fallback working, and a reminder that the produced format is reported from the bytes, not from the declaration.

*Alternatives considered:* transcoding WebP → GIF in the caller with `anim_dump` + `gm convert` — rejected; both binaries exist in the image, but it duplicates the assembly logic and the frame-duration arithmetic in a second place, and the studio is the only component that knows a frame's duration. Publishing the WebP and hoping — rejected; the whole point of the gate finding is that it is unverified, and the pixel cap arithmetic is cheaper to satisfy than to discover in a failed post. Rounding the GIF delay per frame — rejected once measured: it overshot a 3000 ms spec to 3120 ms, and the declared duration is a requirement, not a hint.

### D4. The animation is a second media path, and the still image is its fallback

New nodes mirror the image branch: call `Visual Studio` (`ASSET_TYPES=diagram_animated_linkedin`, `CONTENT` from the post text, `FEEDBACK` from the retry form) → test the returned asset's own `STATUS` → `convert_animation` (data URL → binary, mime type from the asset) → `notification_sent_animation` (Slack file, so the reviewer sees the motion) → `notification_accept_animation` (double approval) → `switch_user_accept_animation` → the same `send_2_linkedin_omImage` node, now with the animation's binary. Rejection → the retry form → re-invoke the studio with the feedback. Unavailable or error → the run continues into the existing `execute_image_creator` path, and the fallback is announced in Slack so the still image is not mistaken for the animation.

*Alternatives considered:* a separate publish node for animated posts — rejected; one media path keeps the post's failure surface in one place. Blocking the post when the animation fails — rejected; the design constraint is that a post is never blocked on the animation. Testing the studio's run `STATUS` — rejected; `PARTIAL` is what an unavailable type produces and is not a failure.

### D5. No frozen spec for this caller

`SPEC_JSON` is not used. A post has exactly one media asset, so there is no second variant to keep in step, and a feedback retry must be free to re-author the spec — which passing a frozen one back would forbid. The frozen-spec mechanism stays what it is for: the blog pipeline re-rendering an approved variant.

*Alternatives considered:* freeze the spec on approval to make a re-render byte-comparable — rejected; nothing consumes that property here, and it would make the Retry button a no-op for the case it exists for.

### D6. Apply after `fix-linkedin-post-review-gate` lands

Both changes edit `agents/n8n/workflows/linked_in_post_sharing.workflow.json`. That change was applied live on 2026-10-01 (its tasks 5.1–5.5), and the live workflow matched this repo's export immediately afterwards, so the sequencing it required is satisfied: this change's pipeline half can now edit and apply the sharing workflow. Its own verification (tasks 6.x/7.x) is still partly open and does not touch the graph.

The studio trio (`Visual Studio`, `Visual Studio Prune`, `Visual Studio Error`) was separately found drifted on 2026-10-01 and has been resolved, because it would otherwise have made this change's apply start from an unknown state. Cause: live was re-saved for all three at 17:38:21–17:38:23 the same day, a second apart, which moved node positions and dropped parameters equal to their defaults — `ExecuteCommand.executeOnce` (default `true`) and Merge v3 `mode`/`options` (default `append`, verified by reading the node definitions out of the running image, not assumed). The committed exports were stale snapshots of the pre-save state, so they were regenerated from live with the backup workflow's own serialization (top-level keys sorted, `JSON.stringify(obj, null, 2)`), a method first validated by reproducing three untouched exports byte-for-byte. All three now match live byte-for-byte. The re-saved live studio is also the one this change's design verified working: the probe run at 18:0x, after that re-save, produced all three assets correctly.

*Alternatives considered:* apply both concurrently and accept the overlap — rejected; the export is a backup, so a concurrent edit makes "read live, diff, write" ambiguous about which state is authoritative.

## Risks / Trade-offs

- **Animated GIF size depends on how much changes per frame**: the live infographic asset measured 1,454,147 bytes for 24 frames at 1080×1350, while a synthetic test whose frames changed across the whole canvas produced 7,088,265 bytes at the same budget — a 4.9× spread. → The real content (flat colours, small per-frame deltas) is the cheap case, and both are inside the frame and pixel caps; a smaller viewport or fewer frames is a one-line registry edit if a post is ever rejected for size, and the platform's exact per-image ceiling is `[UNVERIFIED]`.
- **The GIF encoder's memory is not a known ceiling, but it is unmeasured on the studio's own branch** (Context). The worker has 8Gi Guaranteed against a 35M-pixel budget; the only kill observed was a manual `gm` in the 1Gi main container. → Task 1.4 records the peak at the declared budget as a number. Remedies if it ever comes close: keep the JPEG frames the capture step already produces, cap the encoder (`gm -limit memory`/`-limit map`), or lower the type's budget.
- **Animated WebP remains unverified on LinkedIn** and is explicitly not used here. → If GIF turns out not to animate either, the row's `POST_MEDIA` can be returned to `STATIC` with no code change.
- **A second Slack gate per animated post** (file + approval). → Only for rows that opt in, and it replaces the image gate rather than adding to it: an animated post takes one media approval, not two.
- **The reviewer approves a still frame.** → The animation is uploaded to Slack as a file so the motion is visible; there is no in-Slack animation guarantee `[UNVERIFIED]`, the same as for any GIF file upload.
- **A studio call inside the LinkedIn execution** lengthens the run (43 s measured for three assets; one 24-frame GIF is comparable). → `executionTimeout` is 3600 s, and the branch replaces the image-model call rather than adding a stage.
- **The row's `ASSET_TYPES` intent and the studio's cap.** → One type is requested, well inside `max_types_per_request: 3`.

## Migration Plan

1. Registry type + assembler format honouring; push, because `DownloadTemplate` reads GitHub `main` (unpushed files fail live runs with "resource not found").
2. Sheet column `POST_MEDIA` on `content_queue`; no existing row needs a value (blank = today's behaviour).
3. Studio changes applied live and re-read; then the LinkedIn workflow's new branch, applied after `fix-linkedin-post-review-gate` lands, with `--require-edge` guards.
4. One real post with `POST_MEDIA=ANIMATED` as the acceptance test; one with it blank as the regression test.
5. Rollback: clear `POST_MEDIA` (the still-image path returns immediately) or deactivate the branch; nothing is committed to a repository and no sheet row shape changes beyond one optional column.

## Open Questions

- Does LinkedIn animate a GIF attached through its images API at a 4:5 aspect in-feed? Unanswerable here; the first acceptance post answers it, and the fallback is a one-column revert.
- Is the 36,152,320-pixel cap per frame or for the whole animation? If per-frame, the LinkedIn type's budget could return to 12 fps / 36 frames / 1200 px for smoother motion. Left deliberately at the strict reading until verified.
