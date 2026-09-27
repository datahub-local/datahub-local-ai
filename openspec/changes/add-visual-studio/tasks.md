# Tasks

## 1. Registry, templates and prompts

- [x] 1.1 Add `agents/n8n/datasets/visual_types.json` declaring `hero_static`, `infographic_static`, `diagram_animated`, `animated_svg` (and `motion_clip` marked unavailable) with `author`, `template`, `render`, `format`, `aspect`, `budget`, defaulting to 12 fps, 36 frames and a 1200px viewport; the registry governs structure/render/format only and static-raster art direction stays in `image_motifs.json`; verify it renders through `DownloadTemplate` with no unresolved variables
- [x] 1.2 Add `agents/n8n/templates/infographic.html` (CSS-keyframe infographic) and verify a fixed spec substituted by hand produces a valid, animating page in the browserless screenshot endpoint
- [x] 1.3 Add `agents/n8n/templates/infographic.svg` (SMIL/CSS animated SVG) and verify it opens and animates as a standalone file
- [x] 1.4 Add per-type authoring prompt files under `agents/n8n/prompts/` that instruct the model to return the typed content spec only, and verify each resolves through `DownloadTemplate`
- [x] 1.5 Confirm the prompts and templates follow the repo AI prompt policy (short, literal, no copied data) by review against `AGENTS.md`

## 2. Asset data model

- [x] 2.1 Add an `article_assets` page to the `content_planner` sheet with headers `ENTRY_ID, ASSET_ID, ASSET_TYPE, RENDER_MODE, FORMAT, STATUS, ROUND, FEEDBACK, SPEC_JSON, PROMPT, PATH, DURATION_MS, FRAME_COUNT, WIDTH, HEIGHT, URL, ERROR, UPDATE_DATE`; verify it reads with the existing `content_planner` credential
- [x] 2.2 Implement a helper that upserts one row per article+type matching on `ASSET_ID = <ENTRY_ID>:<ASSET_TYPE>` and reads back the asset set for an article; verify a re-run updates rather than duplicates a row, and that cancelling an entry cancels its non-terminal asset rows
- [x] 2.3 Implement the column split by writer: the studio writes asset state (`STATUS, ROUND, FEEDBACK, SPEC_JSON, PROMPT, FORMAT, ERROR, UPDATE_DATE`) and the article workflow writes only `PATH, URL`; verify no cell is written from both sides and each read-modify-write touches only its own columns

## 3. Authoring stage

- [x] 3.1 Implement spec generation: model call returning the typed content spec (`title`, `blocks[]`, `accent`, `motion{kind,durationMs}`, `alt`); verify a malformed spec is rejected with the missing field named
- [x] 3.2 Implement the deterministic markup step: a Code node fills `templates/infographic.html` and `templates/infographic.svg` from a valid spec; verify markup contains every spec label and value and no model-authored markup reaches the renderer
- [x] 3.3 Verify a static and an animated variant built from one spec share the same title, labels and values
- [x] 3.4 Verify the spec freezes once any variant is approved: approve the static variant, reject the animated one with feedback, and confirm the retried variant keeps the frozen title/labels/values and changes only styling or motion

## 4. Static raster render

- [ ] 4.1 Implement the static path reusing the `linked_in_image_creator` image endpoint with a prompt derived from the article and spec; verify `hero_static` and `infographic_static` return decodable PNG/JPEG binaries
- [ ] 4.2 Verify the hero is produced even when every animated asset fails

## 5. Animated render

- [x] 5.1 (blocked by `datahub-local-core`: `NODES_EXCLUDE=[]` and `custom.extra_modules: webp-converter`) Enable `ExecuteCommand` and install the libwebp CLIs; verify through a probe workflow with `gm version` and the installed `img2webp -version`
- [ ] 5.2 Implement frame capture with Puppeteer `Run Custom Script`: render the markup from a `data:` URL at a fixed viewport, wait for `document.fonts.ready`, seek each animation's `currentTime` for the registry's frame count (default 36 at 12 fps), and return frames as base64 JSON (the one-binary-per-item path is unproven; splitting in a Code node/Convert to File is the reliable transport); capture as JPEG; verify a manual run yields exactly the expected number of frames
- [ ] 5.3 Write frames under `~/.n8n-files/<execution>/<asset>/` (the Files node cannot write `/tmp` without disabling `N8N_BLOCK_FILE_ACCESS_TO_N8N_FILES`) and implement assembly with `img2webp -loop 0 -d <ms> <frames> -o <out.webp>` against the same directory, distributing the duration remainder so the total matches the spec, with `gm convert -delay <100/fps> -loop 0 <frames> <out.gif>` as the fallback when `img2webp` is absent or fails, writing each frame through promptly; verify the output is a playable animated WebP (and the GIF fallback animates), and record the instance's binary-data mode
- [ ] 5.4 Verify the produced animation's duration matches the spec and that frame count (≤36), fps (≤12) and viewport (≤1200px) are bounded by the registry budget
- [ ] 5.5 Verify a frame-capture failure marks only that asset's row with an error and leaves the other assets untouched

## 6. Animated SVG

- [ ] 6.1 Produce `animated_svg` as authored text and commit it without rasterization; verify the committed file is valid SVG text and no binary was produced for it

## 7. Unavailable types

- [x] 7.1 Implement the `motion_clip` path to report `unavailable: no video encoder in this environment`; verify the run continues and the other requested assets are still produced

## 8. Review

- [ ] 8.1 Wire per-asset Slack review reusing the `sendAndWait` double approval and the retry form, with a GIF preview for animated assets; verify each asset appears with its type and round
- [ ] 8.2 Verify rejecting one asset regenerates only that asset and preserves the other assets' approved state
- [ ] 8.3 Cap the requested types per article to 3 and group one article's assets into one Slack thread; verify the cap is enforced with a reason

## 9. Commit integration

- [ ] 9.1 Extend the article workflow's GitHub Git Data commit to include the whole approved asset set in one commit, with derived `<post-slug>-<type-id>.<ext>` names and collision checks; verify one commit carries article + all assets and no commit occurs while any asset is unapproved
- [ ] 9.2 Record each asset's `PATH`, the article URL and the commit reference on its `article_assets` row; verify a re-run of a published article commits nothing
- [ ] 9.3 Verify the static hero is the article's first static image (the blog emits no `og:image`, so platforms preview page images) and that no animated asset is placed ahead of it
- [ ] 9.4 Verify the studio returns file content and type only: filenames bind to the article's frozen slug, references are inserted by the article workflow at its markers, and a title edit after commit renames nothing
- [ ] 9.5 Commit the HTML source beside each rendered markup asset as `<frozen-slug>-<type-id>.html` from the same commit, with no extra source for `animated_svg`; verify the source and the rendered asset share one commit
- [ ] 9.6 Verify the committed `.webp` and `.svg` render correctly in the built MkDocs site and inside glightbox, and that the animated SVG animates through a standard image reference

## 10. Error handling and apply

- [ ] 10.1 Give the Visual Studio workflow a failure path that marks the affected asset row with an error and notifies Slack, and wire `settings.errorWorkflow` at the entry point; verify a forced failure is reported
- [x] 10.2 Extend `scripts/apply_workflow_changes.py` with an idempotent `--create` (POST a workflow body once, keyed by name, print the new id); verify by creating a throwaway workflow, editing it through the existing `PUT` path, then deleting it, and confirm a same-named workflow is left untouched
- [ ] 10.3 Create and apply all new workflows live with `scripts/apply_workflow_changes.py --create`, then pairing subsequent edits with `--require-edge`, and re-read to confirm each field landed
- [ ] 10.4 Exercise the end-to-end set with the manual trigger: hero + static infographic + animated diagram + animated SVG, approve all, and verify the single commit and per-asset row states
- [ ] 10.5 Exercise the mixed path: approve the hero, reject the animated diagram with feedback, confirm the diagram re-renders from the feedback while the hero stays approved and the spec is unchanged
- [ ] 10.6 Confirm the operational boundary by graph inspection: the studio is invoked by the article workflow, reviews no gate of its own, never claims an `article_queue` entry, never commits, and delivers only through the article workflow's `#workflows` gates; single-flight and the commit are the article workflow's (`add-content-writer-agent` D9/D14)
- [ ] 10.7 Update the n8n operational docs (`CLAUDE.md` n8n section) with the `--create` path, the browser-render pipeline (including the `~/.n8n-files` constraint), the `article_drafts` DataTable setup step, and the studio/article asset contract; state explicitly that verification is manual-trigger plus `--require-edge` graph checks, since there is no CI coverage for n8n; verify a reader can follow creation through apply from the docs alone
