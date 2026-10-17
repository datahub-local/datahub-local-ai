# Tasks

## 1. The stills, produced where the render is (`agents/adapters/pi-render/`)

- [x] 1.1 `stillArgs({ format, runDir, width, height, durationSeconds, offsets })` in
  `session-lib.mjs` — a pure builder returning the command and its argument list, so the
  sampling is testable without a browser, ffmpeg or a server. Chromium for `svg`/`svg_wide`
  (screenshot of `out.svg` at the declared frame) and for a deck's `out.html`; `ffmpeg` for
  `mp4`/`gif`/`webp` (evenly spaced offsets **plus the final frame**); no command for a still
  png, whose artifact *is* the still.
  **Landed.** Verified against the running image rather than assumed: `chromium 155` writes a
  6,892-byte PNG from `--headless=new --no-sandbox --disable-gpu --hide-scrollbars
  --window-size=1280,720 --screenshot=… file://…/out.svg`, and `ffmpeg` produced both a mid
  frame (`-ss`) and the final frame (`-sseof -0.1`). Asserted in `test/session-lib.test.mjs`.
- [x] 1.2 Run it after the render in `session-server.mjs`, leave the stills in the run
  directory, and report their names as `stills: [...]` in the response. A still that cannot be
  made does not fail the turn — the others still show the artifact.
  **Landed.** `makeStills` is the only new server code, and it makes no model call.
- [x] 1.3 Serve the stills beside the artifact: the artifact route takes `review-final.jpg`
  and `review-<n>.(png|jpg)` in addition to `out.<ext>`, and `contentTypeFor` knows them, so
  the route stays a whitelist rather than a path a caller can steer.
  **Landed.** Asserted in both test files, including that `review-1.html` and `prompt.txt` are
  refused.

## 2. The critic, orchestrated in `Visual Studio`

- [x] 2.1 `prompts/visual_review_composition.md` — what a still can be judged on (overlap,
  collision, compression against a box edge, frame fit, brand use, fit to the brief) and what
  it must not invent, with the verdict shape. Fetched by the studio (`DownloadTemplate`, the
  motion-rules idiom) so the grammar is a prompt push rather than an image rebuild.
  **Landed.** Fetched by `download_review_prompt`, on the same chain as the vocabulary and
  before the registry.
- [x] 2.2 The review's own nodes: `prepare_stills` (one item per still the render reported,
  addressed on the session's own route) → `if_stills` → `fetch_still` (the existing
  file-response idiom, `outputPropertyName: data`) → `encode_stills` (every still as a data
  URL, with the brief the composer was given) → `critique` (`httpRequest` to the gateway's
  `chat/completions`, reusing `generate_image`'s bearer credential and the model
  `opencode-go/glm-5.3-flash` — a different model from the composer's).
  **Landed, and this is the correction the owner asked for:** the first shape had the *adapter*
  call the model, which puts a dependency and an API call inside the agent. The session now
  renders, serves stills and knows nothing about a critic; the call is this graph's.
- [x] 2.3 `parse_verdict` — the tolerant read of the verdict as data: `VERDICT`, `FINDINGS_TEXT`,
  `RETRY` (the loop's whole decision) and `REVIEW` (the outcome that rides on the asset). An
  unreadable answer is a pass with the raw answer recorded.
  **Landed.** `RETRY: verdict === 'fix' && round < cycles` is asserted offline.
- [x] 2.4 The bound: `REVIEW_CYCLES = 2` and `REVIEW_ROUND: 0` with the request's own defaults
  in `normalize_input`.
  **Landed.**

## 3. The loop

- [x] 3.1 A finding goes back into the **same session**: `review_feedback` sets `FEEDBACK` to
  the findings and increments `REVIEW_ROUND`, and its edge lands on `build_author_brief`, so the
  next turn is an edit of the composition. `build_author_brief` honours an item-level `FEEDBACK`
  (the caller's own on the first turn, the critic's on a review turn) and passes the round
  through.
  **Landed.** The loop re-renders and re-stores the artifact, so the last render is the asset.
- [x] 3.2 The clear path is what reaches `merge_branches`, so the review's outcome is on the
  asset the caller receives (`REVIEW` in `parse_verdict`'s item → `set_result`'s `ASSETS`), and
  a review that could not run says so rather than reading as a pass.
  **Landed** (`if_stills[1]` and `if_review_findings[1]` both land on `merge_branches`).
- [x] 3.3 Assertions in `test_visual_studio_graph.py`, parametrized over both graph copies: the
  whole review path, the critic's credential matching the raster call's, the fetched prompt, the
  stills coming from the session's route and its reported names, the bound, the tolerant parse,
  and the fix turn's `FEEDBACK`/round.
  **Landed.** 500 passed, 1 skipped.

## 4. The raster half (`Visual Studio`)

- [ ] 4.1 After `raster_result`: critique the PNG's data URL with
  `prompts/visual_review_raster.md` (where the fix is a rewritten image prompt rather than an
  edit), and on findings append them to the image director's input and regenerate, bounded by
  the same `REVIEW_CYCLES`. The bytes are the ones n8n already holds, so nothing is fetched back
  and the still question does not arise.
- [ ] 4.2 `prompts/visual_review_raster.md` — wrong frame, forbidden lettering, an invented
  number, a subject that does not match the brief.
- [ ] 4.3 Assertions: the loop exists on the raster branch only, it is bounded, and a verdict of
  `ok` goes straight to `merge_branches`.

## 5. Verification and record

- [x] 5.1 Apply the graph live (the studio is published, so this is a `PUT` plus a `publish`)
  and confirm the published version carries it, as the frame change needed.
  **Applied and published 2026-10-17.** Nine nodes added, eleven edges rewired, two Code nodes
  rewritten, all guarded by `--require-edge` on the edges being replaced
  (`agent_result>merge_branches`, `visual_forms>download_registry`, `if_deck>agent_result`). The
  studio is 38 nodes and `versionId == activeVersionId` (`d527b7be…`); the published copy was
  fetched by its version id and carries the whole path, `critique`, the prompt fetch and the
  `RETRY` bound. The article flow's per-type split was applied in the same pass: 78 nodes,
  `split_pending_types` on both paths into the studio call, which now sends `$json.ASSET_TYPE`.
  One robustness fix went in with it: a missing review prompt routes to the not-run path
  (`REVIEW_REASON: 'the review prompt is empty'`) instead of failing the asset it was meant to
  check — which matters because the prompt is a GitHub-`main` read and the graph is not.
- [ ] 5.2 The adapter image publishes through CI (the stills are new code in the image), and the
  live turn reports `stills` — read back from a real authoring response.
- [ ] 5.3 Live: one authoring turn whose composition carries a deliberate defect shows a
  critique, a fix turn and a second render without it, with the outcome on the asset — and the
  turn's length recorded, since two cycles roughly doubles it.
- [x] 5.4 `AGENTS.md`: the loop's shape, the two halves and why each sits where it does (the
  session owns the bytes and the render; the workflow owns the judgement), the bound, and that
  the stills are the only bytes the review adds to the graph.
  **Landed** as a paragraph in the studio section, next to what a type declares.
