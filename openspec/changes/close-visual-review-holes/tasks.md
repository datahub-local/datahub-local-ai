# Tasks

## 1. The adapter's deterministic gate

- [x] 1.1 `session-lib.mjs`: `parseCheckReport(stdout)` runs over the `hyperframes check --json`
      envelope and returns `{ran, ok, reason, counts, findings}` capped at 25 (errors, warnings,
      info). A non-zero exit with a parsable report is `ran: true`; an unreadable body is
      `ran: false` with the reason. `checkArgs(dir)` owns the invocation so the flag list is
      testable.
      **Landed.** Verified against two real 0.9.1 envelopes from the deployed pod (`lips-j5n6da`
      0/4/1, `lips-60` 11/23/3); the real `bbox` object and `dataAttributes` shape are covered by
      the trimmed fixture. `--no-cache` and `--budget` were removed after the live binary rejected
      them with `Unknown flag: --cache`; the args are now
      `check <dir> --json --at-transitions --timeout=45000`.

- [x] 1.2 `session-lib.mjs`: `parseMotionSignals(stderr, durationSeconds)` parses freeze/black
      spans and `scdet` cuts; `MOTION_FILTER` is the exact ffmpeg filter.
      **Landed.** `freeze_start/end`, `black_start/end` and `lavfi.scd.time` were confirmed against
      ffmpeg 59 in the pod. `pix_th=0.02:pic_th=0.99` replaces the 10% default: `lips-60` reported
      seven false "black" spans at 10% (its dark background) and none at 2%, while a synthetic
      true-black second is still detected. Covered by tests for spans, plain keys, an
      unterminated span, sub-0.2 s cuts and empty stderr.

- [x] 1.3 `session-lib.mjs`: `stillTimesFor(signals, duration, {max, fps})` — one midpoint per
      detected scene, frames straddling each cut when room, settled frame appended by
      `stillArgs`, uniform grid fallback when no cut.
      **Landed.** The live 17510 render has **no hard cut** (`select=gt(scene,0.3)` selects zero
      frames), so the fallback is `min(max(ceil(duration/2.5), 8), cap)` uniform times — 12 across
      30 s instead of 8. Tests cover 7 scenes, no cuts at 12/30/60 s and a 20-scene cap.

- [x] 1.4 `session-server.mjs`: after the render and conformance, run the gate, the signals and
      the connector check, and add `check`, `signals`, `connectors` to the JSON response. A
      png/svg reports `ran: false` with the medium reason; a deck with only `out.html` reports that
      the engine cannot check its page.
      **Landed.** Server tests assert the fields and both not-checked reasons. One skip remains in
      the suite: the png still test needs `ffmpeg`, absent on this dev box.

## 2. Connectors as data

- [x] 2.1 `runtime/connectors.js`: `HFConnectors.draw(list, opts)` resolves ids, measures the live
      boxes, draws one overlay with `data-connector` / `data-connector-head`, and sets
      `data-hf-connectors` to `ok` or `error:<ids>`.
      **Landed.** Verified in the pod's Chromium: the resolved pair produced both tags, the
      missing target produced `data-hf-connectors="error:y"`. The stroke defaults to the
      composition's computed colour because the overlay sits outside it.

- [x] 2.2 Stage `connectors.js` beside `gsap.min.js`.
      **Landed.** `VENDOR_ASSETS` lists both; the Dockerfile copies both at the two places it
      staged gsap. A composer edit to the helper is overwritten each turn by design.

- [x] 2.3 `validateConnectors` reads `connectors.json`, dumps the settled DOM and parses the
      status attribute and the drawn tags.
      **Landed.** The real helper produced `ok` / `error:y` in the pod; absent file →
      `{declared: 0, drawn: 0, errors: []}`.

- [x] 2.4 `prompts/authoring.md`: the connector contract — declare in `connectors.json`, draw with
      `HFConnectors.draw` after both endpoints exist, never hand-place a line or head.
      **Landed.** Read back; no test over the prompt (repository rule).

## 3. The review ledger

- [x] 3.1 `agent_result`: the asset carries `SCENES`, `CHECK`, `CHECK_OK`, `CHECK_REASON`,
      `SIGNALS`, `CONNECTORS`, `MOTION_GATE`, `FORM`, `OPEN_FINDINGS` (inherited, not reset),
      `STALLED`, `VERDICT`, `NEEDS_REVIEW`; an error asset is `unread`.
      **Landed.** Both graph copies identical; `node --check` passes.

- [x] 3.2 `prepare_stills` / `encode_stills`: carry the ledger and append the open ids to the
      critic's text.
      **Landed.** The block is omitted when empty; stills follow it.

- [x] 3.3 `parse_verdict`: the ledger algorithm — ids, severity, `resolved`, `seen`, `stalled`,
      `RETRY = seen === 1`, unread is not a pass, check/craft warnings become findings, check
      findings are re-derived rather than inherited.
      **Landed.** Fixtures cover new/re-reported/resolved/silent, `unread`, no-verdict answers,
      case-insensitive ids, a fixed check error leaving the ledger, a stalled check error,
      craft copy findings (`line_unread`, `text_below_floor`, `dead_stretch`,
      `first_frame_empty`) and `film_silent` ignored.

- [x] 3.4 `parse_raster_verdict`: the same id/severity/resolution protocol; a raster with no image
      is `unread`.
      **Landed.** Both graph copies; no CHECK source, as the raster has no engine gate.

- [x] 3.5 `review_feedback` / `raster_feedback`: findings sorted by `(severity, id)` plus the
      no-regression line.
      **Landed.**

- [x] 3.6 `set_result`: run-level `NEEDS_REVIEW` and the per-asset fields.
      **Landed.**

## 4. The prompts

- [x] 4.1 `visual_review_composition.md`: rubric kept; ledger protocol, severity 1-3, `where`
      cites the still index, `unread` answer, no-fix-not-a-finding.
      **Landed.** No test over the prompt (repository rule); the eval set is the intended gate.

- [x] 4.2 `visual_review_raster.md`: the same protocol in one paragraph, keeping the
      prompt-change rule.
      **Landed.**

## 5. The approval

- [x] 5.1 `check_animation_result`: exposes `VERDICT`, `NEEDS_REVIEW`, `OPEN_COUNT`,
      `OPEN_FINDINGS`, `STALLED`, `CHECK_OK`, `CHECK_REASON`.
      **Landed.** The 17510 asset shape yields `NEEDS_REVIEW: true` and the open count.

- [x] 5.2 `notification_accept_animation`: three branches — findings with ids, unread with zero
      open, clean.
      **Landed.** Rendered for all three shapes; both copies identical.

## 6. Measure the critic

- [x] 6.1 `agents/adapters/pi-render/test/fixtures/review/` with the labelled incident renders.
      **Landed, first four cases.** `lips60-copy` (17296), `connector-head` (17523),
      `sketch-clean` (16955) and `sketch-svg-clean` (16965), each with its verbatim brief, the
      stills the critic received, and a 1 fps contact sheet where the medium has a timeline.
      The two sketch cases passed the old critic and are defective by eye (a near-empty frame;
      a gold arrow in empty space), so they are labelled from the frames, not the old verdict.
      Still to add: blank first frame (13770), wrong container (13785), the 7-scene miss,
      the panel overlap, and a human-verified clean negative (none exists yet).

- [x] 6.2 `scripts/score_review.mjs`: run a critic model over the fixtures, report TPR/TNR and the
      unparsed rate.
      **Landed, and run.** The script reads `cases.json` + stills (+ an optional 1 fps sheet),
      calls the gateway through `REVIEW_BASE_URL`/`REVIEW_API_KEY`/`REVIEW_MODEL`, normalises
      punctuation before keyword matching, and supports `--samples`. First baseline: TPR 4/4,
      finding recall 8/8 across 2 samples, unparsed 0%, TNR `n/a` (no clean negative yet).

- [x] 6.3 Record the first baseline and the model/rubric versions in `design.md`.
      **Landed.** The appendix records the model, the prompt, the per-case 2/2 results and the
      pre-sheet instability; TNR is `n/a` until a human-verified clean render exists.

## 7. Verify and record

- [x] 7.1 Adapter suite: `node --test test/` → 82 tests, 81 pass, 0 fail, 1 skipped (the png test
      needs `ffmpeg`, absent on the dev box).
      **Landed.** The workflows have no committed test (owner rule).

- [x] 7.2 Every changed jsCode passes `node --check` inside an `(async () => { … })()` wrapper;
      both graph copies are byte-identical per node.
      **Landed.**

- [x] 7.3 `openspec validate close-visual-review-holes --strict` → valid.
      **Landed.**

- [ ] 7.4 Apply to the live instance and run one `animation_linkedin_video` request; confirm the
      asset carries `CHECK`, `OPEN_FINDINGS`, `NEEDS_REVIEW` and the approval names any finding.
      **Not landed.** No deploy was made. The order is fixed by the image being multi-arch and
      published by CI: (1) commit and push to `main`, which runs `Test Agents` then
      `publish-images.yaml` and pins the new digest in `agents/sympozium/values/*.gotmpl`;
      (2) roll the Sympozium session so the pod carries `runtime/connectors.js` and the new
      parsers; (3) apply both workflow exports with `scripts/apply_workflow_changes.py`, then
      re-activate and re-read `activeVersion`; (4) run one `animation_linkedin_video` request.
      The local image was built and inspected (the runtime split is present), but it is amd64-only
      and the agent nodes are arm64, so a local push is not a deploy. Applying the workflows before
      the image would correctly mark every mp4 `Xcheck-absent` and block approvals.

- [x] 7.5 Update the Visual Studio section of `docs/agent/n8n.md`.
      **Landed.** The review subsection, the 17510 evidence, the check flags, the copy gate, the
      black threshold, the connector contract, the ledger and the approval are documented.
