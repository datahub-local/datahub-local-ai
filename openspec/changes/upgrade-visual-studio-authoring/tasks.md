# Tasks

## 1. Composer guide (`agents/adapters/pi-render/prompts/authoring.md`)

- [x] 1.1 Reduced the guide to sandbox facts only: the working directory, `hyperframes` on
  `PATH`, the skills path (`/opt/hyperframes/skills/`, read `hyperframes/SKILL.md` first,
  `hyperframes-core` for the contract, `hyperframes-cli` for lint/render), the vendored
  GSAP, "no network at render time", "run `hyperframes render` in the foreground and
  wait", and "you cannot see images". Deleted the composition-contract restatement, the
  pacing numbers, the nine-point review, the page-indicator rule and the SVG instructions
  (the brief carries them).
- [x] 1.2 Kept the render command and its flags (`--low-memory-mode`, the worker warning),
  and added the two facts the composer got wrong live: the turn **must** end in a render,
  and the vendored GSAP must be **served**, not referenced by absolute path. The path is
  exposed by the session server (and the Job entrypoint), which stage
  `/opt/hyperframes/vendor/gsap.min.js` into the run directory as a sibling `gsap.min.js`;
  the composer references `<script src="gsap.min.js">`. Folded from
  `add-hook-registry-and-visual-intent` task 10.3. **[UNVERIFIED against a rebuilt image.]**
- [x] 1.3 Noted in `AGENTS.md` (§ Visual Studio) and in `test_hook_registry.py` that
  `holdSeconds` and review points 6–9 no longer apply: they were added live by
  `add-hook-registry-and-visual-intent` tasks 9.14 and 10.1 and are removed here.
- [x] 1.4 Rewrote `test/authoring-prompt.test.mjs`: it asserts no review section, no pacing
  thresholds (`2.5-3.5`, `0.6-0.9`, `1.5 second`), no page indicator, no composition-contract
  bullets and no SVG mode, and that the sandbox facts remain. Verified the new test fails
  against the previous guide.
- [x] 1.5 Rebuilt and pinned by CI (`8f038f9`, digest `sha256:e050a9b7…`); ArgoCD rolled the
  session Deployment to it (verified in 2.5).

## 2. Composer image (`agents/adapters/pi-render/Dockerfile`, `package.json`)

- [x] 2.1 Raised the `hyperframes` pin to `0.8.146` and re-read that release's
  `dist/skills/` listing: still only `hyperframes`, `hyperframes-cli`, `media-use`.
- [x] 2.2 `docker build` fetches `skills/` from `heygen-com/hyperframes` at the pinned tag
  and copies it over `/opt/hyperframes/skills/`.
- [x] 2.3 The build asserts each expected skill's `SKILL.md`
  (`hyperframes`, `-cli`, `-core`, `-animation`, `-keyframes`, `-registry`, `-creative`,
  `-studio`) and fails loudly naming any missing one.
- [x] 2.4 Vendored `@hyperframes/shader-transitions@0.8.146` in `package.json`; the build
  verifies it resolves in the image.
- [x] 2.5 Verified live instead of a local build: CI published the image and pinned the
  digest (`8f038f9`), the session Deployment rolled, the pod is `1/1 Running`, the
  session server answers `<host>:8080/healthz` with `ok`, the full skill set
  (`hyperframes-core`, `-animation`, `-keyframes`, `-registry`, `-creative`, `-studio`,
  plus `media-use` and the others) is present under `/opt/hyperframes/skills/`, and
  `gsap.min.js` is vendored at `/opt/hyperframes/vendor/`. Rendering a sample is left to
  the live POST checks in section 8.

## 3. Motion rules (`agents/n8n/prompts/visual_motion_rules.md`)

- [x] 3.1 Authored the file: no element ever fully stops (ambient idle, not a still final
  frame), one continuous camera move that never decays to a stop, entrances staggered at
  offsets shorter than their animations, compound properties only when they tell one story,
  overshoot on transforms only, depth planes with a real foreground occlusion, pacing
  matched to the content, seeded imperfection.
- [x] 3.2 Kept it free of this repository's rules: no frame-fill checklist, no page
  indicator, no pixel minimums, no product/article/dimension constant.
- [x] 3.3 Verified it is plain markdown with no doubled-curly-brace placeholder
  (`DownloadTemplate` scans the whole text).
- [x] 3.4 Committed and pushed in `4de97ce` (on `origin/main`), which `DownloadTemplate`
  reads as GitHub `main`.

## 4. Visual Studio workflow (`agents/n8n/workflows/visual_studio.workflow.json`)

- [x] 4.1 `normalize_input` accepts optional `EXTRA_PROMPT`; `main_trigger` and
  `form_trigger` carry it (the webhook trigger needs no field: it passes the body through).
- [x] 4.2 `download_visual_rules` (`DownloadTemplate` `prompts/visual_motion_rules.md`,
  empty vars) → `visual_rules` → `download_registry`, wired so `build_author_brief` reads
  `$('visual_rules').first().json.RULES`.
- [x] 4.3 `build_author_brief` appends the motion rules block, the request's `FEEDBACK`
  (under a reviewer-correction line) and `EXTRA_PROMPT` last; the `holdLine` and
  `reviewLine` are deleted; the scene plan and style lines remain.
- [x] 4.4 `render: deck` supported: the brief asks for one self-contained HTML deck to
  `out.html` and a render of the same plan to `out.mp4`; the session request carries
  `format: html` and the paired artifact URL. Session server + `session-lib.mjs` accept
  `html` (served `out.html`, `text/html`, no transcode) and the deck instruction.
- [x] 4.5 `agent_result` fetches both artifacts for a deck: `fetch_artifact` →
  `if_deck` → `fetch_paired_artifact` → `agent_result`, which emits the deck and its
  paired `deck_video`. `fetch_paired_artifact` continues on error.
- [x] 4.6 Extended `test_visual_studio_graph.py` and `test_visual_studio_registry.py`:
  triggers carry `EXTRA_PROMPT`; the brief contains the rules block, `FEEDBACK` and
  `EXTRA_PROMPT` and neither the hold line nor the review line; the deck fetch is wired;
  no animated type declares `holdSeconds`; the deck declares its pair. Verified each new
  assertion fails without its change.
- [x] 4.7 Applied live with `--require-edge` guards (`brand_tokens>download_registry`,
  `fetch_artifact>agent_result`, `download_registry>parse_registry`), all satisfied. The PUT
  published in place (`activeVersionId` moved to `e64b1570…`, `active: true` unchanged); the
  re-read shows 29 nodes with `activeVersion` equal to the top level, and the export diffed
  against live shows no parameter or connection differences.

## 5. Registry (`agents/n8n/datasets/visual_types.json`)

- [x] 5.1 Added the `deck` type (`author: agent`, `render: deck`, `format: html`, 16:9,
  30 s) with its paired `mp4` / `deck_video` declared.
- [x] 5.2 Added `animation_linkedin_video` (`author: agent`, `render: video`, `format: mp4`,
  4:5, 30 fps, no `holdSeconds`).
- [x] 5.3 Dropped `holdSeconds` from `animation`, `animation_linkedin` and `svg`; kept the
  GIF budget unchanged (and stated the choice in the type's fields), since the GIF remains
  a first-class output inside the platform cap.
- [x] 5.4 Extended `test_visual_studio_registry.py`: no video type declares `holdSeconds`;
  the deck declares both artifacts; every `author`/`render` is a known kind; the GIF stays
  inside the cap.
- [x] 5.5 Committed and pushed in `4de97ce` (on `origin/main`), which the studio fetches as
  GitHub `main`.

## 6. LinkedIn publish (`agents/n8n/workflows/linked_in_post_sharing.workflow.json`)

- [x] 6.1 **Probed:** the installed `n8n-nodes-base.linkedIn` node supports only
  `shareMediaCategory: IMAGE` / `ARTICLE` (read in the live n8n pod, 2026-10-11); it cannot
  upload video. The publish therefore follows the design's documented fallback below.
- [x] 6.2 `execute_visual_studio` requests `animation_linkedin_video` for an animated row;
  the still-image path is unchanged.
- [x] 6.3 `if_video_publish` chooses by the asset's `CONTENT_TYPE` (`video/mp4` → the
  LinkedIn API path; otherwise → the existing `send_2_linkedin_omImage` node). The video
  path is `linkedin_register_video` (`/v2/assets?action=registerUpload`) →
  `linkedin_video_upload` (signed `uploadUrl`) → `linkedin_post_video` (`/v2/ugcPosts`,
  `shareMediaCategory: VIDEO`) → `linkedin_video_urn` (id from `x-restli-id`), reusing the
  `linkedInOAuth2Api` credential. **[UNVERIFIED against LinkedIn.]**
- [x] 6.4 Extended `test_linkedin_animated_media.py`: the publish decision selects on
  content type; a `video/mp4` asset resolves to the API video path; the still/GIF path and
  the approval nodes are unchanged; the video API nodes carry the credential. Verified the
  assertions fail without the change. **Found and fixed while preparing the live apply:** the
  committed export had dropped `switch_user_accept_image`'s rejection edge, leaving
  `notification_retry_or_cancel_image` (and `switch_user_retry_image`) unreachable — a
  rejected still image dead-ended. Restored the second output to the image retry form and
  added `test_image_rejection_still_reaches_its_retry` and `test_no_node_is_orphaned` (both
  fail on the pre-fix export, both copies checked).
- [x] 6.5 Applied live with `--require-edge` guards (`switch_post_media>execute_visual_studio`,
  `check_animation_result>if_animation_ok`, `convert_animation>notification_sent_animation`),
  all satisfied. The PUT published in place (`active: true` unchanged); the re-read shows 47
  nodes with the seven video nodes in `activeVersion` and `activeVersion` equal to the top
  level, and the export diffed against live shows no parameter or connection differences.

## 7. Session reach (gate)

- [x] 7.1 Read the live policies: the session pod's egress admits 443
  (controller-generated `datahub-local-ai-pi-render`); our chart adds model egress on 4000
  only. Verified reach from the session pod: `raw.githubusercontent.com` → 200.
- [x] 7.2 Not needed: the reach is present, so a registry block may be installed at author
  time; the vendored `shader-transitions` primitives remain the always-available surface.
  No chart change.

## 8. Verify

- [x] 8.1 Ran the `agents/n8n/scripts/` suite (176 passed) and the adapter `node --test`
  suite (26 passed). No chart render needed (7.2 does not apply).
- [x] 8.2 No chart change in this change, so the render gate has nothing new to cover;
  `helmfile template` was not re-run here (CI runs it on every push under
  `agents/sympozium/**`). The only chart-adjacent change this cycle is the adapter digest,
  published by CI and rolled by ArgoCD.
- [x] 8.3 Live: POSTed `ASSET_TYPES=animation_linkedin_video` to `/webhook/visual-studio`.
  Execution 12927 succeeded (07:59:53→08:02:05Z); `download_visual_rules` and `visual_rules`
  ran before `download_registry`; the asset is `STATUS: RENDERED`, `CONTENT_TYPE: video/mp4`,
  h264 1080x1350, 30 fps, 300 frames, 10.0 s, and the report shows the motion grammar was
  followed (idle loops, no frozen hold).
- [x] 8.4 Live: POSTed `ASSET_TYPES=deck`. Execution 12932 succeeded (08:03:59→08:07:32Z);
  `if_deck → fetch_paired_artifact → agent_result` ran and one composer turn returned two
  assets — `deck` (`text/html`, out.html) and `deck_video` (`video/mp4`, 1280x720, 30 fps,
  900 frames, 30 s).
- [x] 8.5 Live: POSTed the same type with `FEEDBACK` set. The executed `build_author_brief`
  output shows the brief tail as motion rules, then `Correction from a reviewer - fix this in
  this attempt:` with the feedback verbatim, then the brand block — so a rejection reaches
  the composer on the next turn.
- [x] 8.6 Measured from the runs: `execute_author` 126.6 s for the video, 204.6 s for the
  deck (whole executions 132.2 s and 213.0 s). Model usage from the LiteLLM spend log:
  video run 16 calls, peak input 39,602 tokens, 520,614 total; deck run 13 calls, peak input
  42,160 tokens, 402,625 total. Both peaks fit the 65,536 window with headroom, which is what
  the per-`toolsAllow` budget was for.
- [ ] 8.7 Live: verify a `video/mp4` asset publishes as a video post (left to the user; a
  real public post).

## 9. Documentation

- [x] 9.1 Updated the `#### Visual Studio` and `#### LinkedIn post media` sections of
  `AGENTS.md`: the guide is sandbox facts, the brief carries the motion grammar, the skill
  set is fetched at build, `FEEDBACK`/`EXTRA_PROMPT` reach the composer, no type mandates a
  frozen frame, the video type and the `deck` pair, and the LinkedIn video API path.
- [x] 9.2 Recorded where the one copy of the motion grammar lives
  (`agents/n8n/prompts/visual_motion_rules.md`) and that the composer's guide must not
  regain a method section.
- [x] 9.3 Updated `agents/adapters/pi-render/README.md`: the skill set comes from the
  repository at the pinned release, and the `hyperframes-core`-not-bundled note is
  superseded.
