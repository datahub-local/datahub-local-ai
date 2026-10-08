# Tasks

## 1. Authoring guide

- [x] 1.1 Add a `## Review before you render` section to
  `agents/adapters/pi-render/prompts/authoring.md` with the four checks — content,
  proportion, legibility, pacing — each stated with a rule or a number, and require the
  review and its measured values in the report; verify a reader can name each check and
  its threshold without reading the workflow
- [x] 1.2 Fold the review into `## How to work` as a step between lint and render so it
  is not skippable; verify no other step's meaning moved

## 2. Test

- [x] 2.1 Add `agents/adapters/pi-render/test/authoring-prompt.test.mjs` asserting the
  guide carries the review section, its four checks, the legibility minimums and the
  duration bound; verify the test fails against the pre-change guide
- [x] 2.2 Run `node --test 'agents/adapters/pi-render/test/*.test.mjs'` and confirm the
  suite passes (20 passed; the new test fails against the pre-change guide)

## 3. Ship the guide (image rebuild)

- [ ] 3.1 Commit and push the guide + test; `publish-images.yaml` rebuilds the adapter
  (a non-`deploy/` file under `agents/adapters/pi-render/` changed) and the pin job
  commits the new digest — verify the adapter digest in `sympozium_pi_render.digest`
  and `agents/adapters/pi-render/deploy/session.yaml` changes
- [ ] 3.2 Confirm ArgoCD syncs the new digest and the session reports it in
  `status.resolvedImageDigest` with `phase: Ready`

## 4. Acceptance

- [ ] 4.1 Re-run one opted-in row (`LinkedIn Post Sharing`, `POST_MEDIA=AGENT`) and
  confirm the composer's report states the review (per-scene content coverage, minimum
  type size, total duration), the composition fills the 4:5 frame, and its total is no
  longer than the requested seconds — read the artifact with `ffprobe` and the
  composition's `data-duration`, not the studio record alone
- [x] 4.2 Record this session's evidence (studio runs 12622/12625/12628 and the two
  defects) in `agents/adapters/pi-render/README.md` so the review's rationale is not
  re-litigated (added `### The authoring review (before render)` with the three runs)

## 5. Proportion follow-up and pagination

- [x] 5.1 Tighten the proportion rule to measure the **visible content**, not a wrapper
  that stretches to fill, after studio run `12645` reported 86 % coverage while the
  frames kept every scene's content in the top third (`flex: 1` on the wrapper)
- [x] 5.2 Add the page-indicator rule: a multi-scene composition carries the scene
  number in the same bottom-right position on every scene
- [x] 5.3 Extend `authoring-prompt.test.mjs` to assert the visible-content wording and
  the page-indicator rule; `node --test` is 22/22
- [ ] 5.4 Rebuild and pin the adapter image again (a second `publish-images.yaml` cycle)
  and re-run the acceptance (4.1) with a multi-scene brief, confirming the report's
  proportion figure matches the frames and every scene carries the page indicator
