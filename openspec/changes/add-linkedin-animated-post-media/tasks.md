# Tasks

## 1. Registry and studio format

- [x] 1.1 Add `diagram_animated_linkedin` to `agents/n8n/datasets/visual_types.json` — same `author`/`template` as `diagram_animated`, `render: animated`, `format: gif`, `fallbackFormat: webp`, `aspect: 4:5`, `budget: {fps: 8, frames: 24, viewport: 1080}`; verify the file still parses and that the declared budget is inside the platform caps (24 × 1080 × 1350 = 34,992,000 < 36,152,320) and that the file carries no doubled-curly-brace placeholder anywhere, since `DownloadTemplate` is called with empty `template_vars` (verified: parses, 34,992,000 ≤ 36,152,320, 24 ≤ 500 frames, no `{{` in the file)
- [x] 1.2 Make the type's declared format select the encoder in `build_assemble` (`visual_studio.workflow.json`): a `gif` type assembles with `gm convert` first, a `webp` type keeps today's img2webp-then-GM order, and each falls back to the other only when its own encoder is unavailable or fails; verify with a probe run requesting the new type that the returned `CONTENT_TYPE` is `image/gif` and that inspection of the file reports the declared frame count and total duration (implemented and applied live; the command each format generates was read out of the patched code with `node`, the webp path re-verified end to end after the apply — `image/webp`, 36 frames, 3000 ms, 2,054,162 bytes served — and the fallback direction proved in a probe container that has `gm` but no `img2webp`, where a webp type produced a GIF. The gif type's own live run waits on 1.3, since `DownloadTemplate` reads GitHub `main`)
- [ ] 1.3 Commit and push the registry and the studio export — `DownloadTemplate` reads GitHub `main`, so an unpushed type fails live runs with "resource not found" (hit 2026-09-27); **this is what blocks the live gif-type run** in 1.2
- [x] 1.4 Exercise the assembler's GIF branch at the LinkedIn type's declared budget (8 fps / 24 frames / 1080 px) and record the measured peak memory against the worker's 8Gi limit; verify the command completes, the file is an animated GIF, and its total duration matches the declared value (measured 2026-10-01: running the exact command `build_assemble` emits over 24 JPEG frames at 1080×1350, in a container capped at 512Mi — 4 s, peak 363,061,248 bytes ≈ 346 MiB, output 7,088,265 bytes, 24 frames. So the budget fits in a tenth of the worker's limit and no remedy was needed. The duration is exact: 12 frames at 12 cs + 12 at 13 cs = 3000 ms, because the GIF path now spreads the remainder the way the WebP path already did — the first version rounded per frame and gave 24 × 13 cs = 3120 ms, which is why the delays are per-frame here)
- [x] 1.5 Apply the studio change live with `scripts/apply_workflow_changes.py` (`--require-edge` on every edge it touches) and re-read the live workflow; verify the change landed and that live and the export still agree byte-for-byte afterwards (applied against the guard `if_capture_ok -> build_assemble`; re-read and the export resynced from live, byte-identical. Note a `PUT` re-serialises node key order, so the export is regenerated from live after each apply rather than hand-edited)

## 2. LinkedIn pipeline: opt-in animated media

- [ ] 2.1 Add the `POST_MEDIA` column to `content_queue` in `content_planner`; verify `read_articles_sheet`'s auto-detected range picks it up and that `select_article_to_post` carries it through unchanged (it returns the whole row, so no code change is expected)
- [ ] 2.2 Add the media switch after the post's text approval so any value other than `ANIMATED` takes the existing `execute_image_creator` path byte-for-byte; verify both a blank and a `STATIC` value reach it
- [ ] 2.3 Add the studio call node (`executeWorkflow`, waiting for the sub-workflow) invoking `Visual Studio` with `CONTENT` from the post text, `ASSET_TYPES=diagram_animated_linkedin`, `FEEDBACK` from the retry form, and no `SPEC_JSON`; guard its incoming edge with `--require-edge`
- [ ] 2.4 Test the returned asset's own `STATUS`/`ERROR` rather than the studio's run `STATUS` — which is `PARTIAL` whenever a requested type is unavailable — and route success onward and unavailable/error into the still-image fallback
- [ ] 2.5 Convert the asset's `data:` URL into a binary item using the asset's own `CONTENT_TYPE` and a filename derived from it, mirroring the existing image conversion node's shape; verify the binary's `mimeType` matches the asset rather than a hardcoded `image/png`
- [ ] 2.6 Add the Slack file upload so the reviewer sees the motion, and the double-approval gate, and wire the existing retry-or-cancel form for animation rejections with its feedback returned to the studio call; verify Retry re-authors with the feedback and presents the new result, and that Cancel ends the row without publishing and without generating the still image
- [ ] 2.7 Point the LinkedIn publish node's binary property at the approved media for both paths without changing `shareMediaCategory: IMAGE`; verify exactly one media item is attached on each path

## 3. Fallback and its announcement

- [ ] 3.1 Route the animation failure output into the existing still-image branch and add a Slack notice naming the post and the reason the animation was not used; verify a forced unavailable or errored animation still publishes the post with a still image and posts that notice
- [ ] 3.2 Confirm the animation branch's failures still reach `settings.errorWorkflow` (`LinkedIn Post Sharing Error`) rather than being swallowed; verify by forcing an error and observing the row's `STATUS=ERROR` and the notice

## 4. Tests

- [ ] 4.1 Add an offline structural test over `linked_in_post_sharing.workflow.json` asserting the media switch exists, that its non-animated path still reaches `execute_image_creator`, that the studio call requests the LinkedIn type and passes no `SPEC_JSON`, and that the animation branch's failure output reaches the image branch; verify the test fails when the switch or the fallback edge is removed
- [ ] 4.2 Add an offline structural test over `visual_studio.workflow.json` and `datasets/visual_types.json` asserting the assembler reads the type's declared format and that the LinkedIn type's declared budget stays inside 500 frames and 36,152,320 pixels; verify it fails when the budget is raised past the cap
- [ ] 4.3 Confirm both tests run in the `agents/n8n/**` CI job added by `fix-linkedin-post-review-gate`, or add that job here if it has not landed; verify the job gates a pull request rather than only running locally

## 5. Apply and verify

- [ ] 5.1 Confirm `fix-linkedin-post-review-gate` has landed and its live apply is complete before touching this workflow (design D6); re-read the live workflow and diff it against the export so the field-level apply starts from a known state
- [ ] 5.2 Apply the new nodes and connections with `scripts/apply_workflow_changes.py --changes` guarded by `--require-edge`, re-read the live workflow, and confirm every field landed
- [ ] 5.3 Manual-trigger a row with `POST_MEDIA=ANIMATED`: verify the studio produced a GIF (content type, frame count and total duration read from the file itself, not from the asset's own metadata), that it was uploaded to Slack for review, and that approving it publishes a post carrying the GIF
- [ ] 5.4 Manual-trigger a row with `POST_MEDIA` blank: verify the run takes the still-image path unchanged, with one media gate and no studio call
- [ ] 5.5 Exercise the animation rejection (Retry with feedback re-authors; Cancel publishes nothing and produces no still image) and the fallback (force the type to be reported unavailable and confirm the post still publishes with a still image and the notice)
- [ ] 5.6 Answer the design's open questions from a real post: whether LinkedIn animates the GIF in-feed at 4:5, and whether the documented pixel cap is per frame or per animation; record the outcome here or in the n8n section of `AGENTS.md`, and revisit the type's budget if the cap turns out to be per frame

## 6. Documentation

- [ ] 6.1 Document in `AGENTS.md` (n8n section) the `POST_MEDIA` opt-in, the LinkedIn animated type and its budget, that this caller passes no frozen spec, and that the fallback media is the still image; verify a reader can follow the wiring from the docs alone
