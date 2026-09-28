# Tasks

## 1. Registry, templates and prompts

- [x] 1.1 Add `agents/n8n/datasets/visual_types.json` declaring `hero_static`, `infographic_static`, `diagram_animated`, `animated_svg` (and `motion_clip` marked unavailable) with `author`, `template`, `render`, `format`, `aspect`, `budget`, defaulting to 12 fps, 36 frames and a 1200px viewport; the registry governs structure/render/format only and raster art direction stays in `image_motifs.json`; verify it renders through `DownloadTemplate` with no unresolved variables
- [x] 1.2 Add `agents/n8n/templates/infographic.html` (CSS-keyframe infographic) and verify a fixed spec substituted by hand produces a valid, animating page in the browserless screenshot endpoint
- [x] 1.3 Add `agents/n8n/templates/infographic.svg` (SMIL/CSS animated SVG) and verify it opens and animates as a standalone file
- [x] 1.4 Add per-type authoring prompt files under `agents/n8n/prompts/` that instruct the model to return the typed content spec only, and verify each resolves through `DownloadTemplate`
- [x] 1.5 Confirm the prompts and templates follow the repo AI prompt policy (short, literal, no copied data) by review against `AGENTS.md`
- [x] 1.6 Commit and push the registry, prompts and templates — `DownloadTemplate` reads GitHub `main`, so unpushed files fail live runs with "resource not found" (hit 2026-09-27)

## 2. Trigger contract and run record

- [x] 2.1 Provision the `visual_studio_table` DataTable (`RUN_ID, STATUS, REQUEST, RESULT, ASSET_COUNT, ERROR`) via `agents/n8n/scripts/setup_data_tables.py --apply`; verify the script is idempotent by table name and that the DataTable API supports row get/insert/upsert (the earlier `article_assets` page, then table, is superseded by this run record — the studio keeps no per-caller state)
- [x] 2.2 Implement the one parameter contract on all three triggers — `executeWorkflowTrigger`, `POST /webhook/visual-studio`, and the form — taking `CONTENT` (required), `ASSET_TYPES`, `FEEDBACK`, `SPEC_JSON`; verify missing `CONTENT` fails naming the parameter and that the same parameters produce the same set on every surface
- [x] 2.3 Implement the run record: exactly one row per run keyed by `RUN_ID` (the execution id) carrying `REQUEST` and every asset's outcome in `RESULT`; verify the outcome — content included — is reconstructable from the row by `RUN_ID`
- [x] 2.4 Implement the response envelope (`RUN_ID`, `STATUS` `COMPLETE`/`PARTIAL`/`FAILED`, `ASSETS[]`) so a multi-asset result arrives whole over HTTP; verify the API response carries every asset, not just the first
- [x] 2.5 Ship the form trigger in the instance's proven shape (typeVersion 2.2, auto `webhookId` path, default "Form Is Submitted" response, pinned webhookId); verify a submission acks and lands a run record (a custom `path` registers GET but not POST — hit 2026-09-27)

## 3. Authoring stage

- [x] 3.1 Implement spec generation: model call returning the typed content spec (`title`, `blocks[]`, `accent`, `motion{kind,durationMs}`, `alt`); verify a malformed spec is rejected with the missing field named
- [x] 3.2 Implement the deterministic markup step: a Code node fills `templates/infographic.html` and `templates/infographic.svg` from a valid spec; verify markup contains every spec label and value and no model-authored markup reaches the renderer
- [x] 3.3 Verify a static and an animated variant built from one spec share the same title, labels and values
- [x] 3.4 Implement the frozen-spec parameter: a request supplying `SPEC_JSON` uses it verbatim for every variant and makes no authoring model call, validated by the same validator as model output; verify a re-render from the supplied spec keeps title/labels/values identical

## 4. Static raster render

- [x] 4.1 Implement the static path reusing the `linked_in_image_creator` image endpoint with a prompt derived from `CONTENT` and the spec; verify `hero_static` and `infographic_static` return decodable PNG binaries
- [x] 4.2 Verify the requested hero is produced even when another asset fails or reports unavailable (verified against the `motion_clip` unavailable path)

## 5. Animated render

- [x] 5.1 (blocked by `datahub-local-core`: `NODES_EXCLUDE=[]` and `custom.extra_modules: webp-converter`) Enable `ExecuteCommand` and install the libwebp CLIs; verify through a probe workflow with `gm version` and the installed `img2webp -version`
- [x] 5.2 Implement frame capture with Puppeteer `Run Custom Script`: render the markup from a `data:` URL at a fixed viewport, wait for `document.fonts.ready`, seek each animation's `currentTime` for the registry's frame count (default 36 at 12 fps), and return frames as base64 JSON (the one-binary-per-item path is unproven; splitting in a Code node/Convert to File is the reliable transport); capture as JPEG; verify a manual run yields exactly the expected number of frames
- [x] 5.3 Write frames under `~/.n8n-files/<execution>/<asset>/` (the Files node cannot write `/tmp` without disabling `N8N_BLOCK_FILE_ACCESS_TO_N8N_FILES`) and implement assembly with `img2webp -loop 0 -d <ms> <frames> -o <out.webp>` against the same directory, distributing the duration remainder so the total matches the spec, with `gm convert -delay <100/fps> -loop 0 <frames> <out.gif>` as the fallback when `img2webp` is absent or fails, writing each frame through promptly; verify the output is a playable animated WebP (and the GIF fallback animates)
- [x] 5.4 Verify the produced animation's duration matches the spec and that frame count (≤36), fps (≤12) and viewport (≤1200px) are bounded by the registry budget (WebP matches exactly — 36 frames, 24×83+12×84 = 3000 ms; the GIF fallback is centisecond-quantised, so a 3200 ms spec yields 36×90 ms = 3240 ms, which is what design D4 accepts)
- [x] 5.5 Verify a frame-capture failure marks only that asset's result with an error and leaves the other assets untouched

## 6. Animated SVG

- [x] 6.1 Produce `animated_svg` as authored text, returned as `image/svg+xml` markup and never rasterized; verify the returned content is valid SVG text and no binary was produced for it

## 7. Unavailable types

- [x] 7.1 Implement the `motion_clip` path to report `unavailable: no video encoder in this environment`; verify the run continues and the other requested assets are still produced

## 8. Review, retry and commit (moved)

Review gates, the retry-with-feedback loop, per-asset review state and the single multi-asset commit are the caller's, not the studio's — the studio returns content and writes nothing but its run record. The scenarios these tasks covered moved into `add-content-writer-agent` (its design D4/D5/D9 and its tasks 4.5–4.12), which invokes this studio as a sub-workflow and owns `article_queue`/per-asset state:

- 8.1 per-asset Slack review, 8.2 reject-one-regenerate-one, 8.3 review grouping → `add-content-writer-agent` tasks 4.5, 4.12
- 9.1 single multi-asset commit with collision checks, 9.2 record paths and commit ref, 9.3 hero placement first, 9.5 source committed beside rendered asset, 9.6 site render checks → `add-content-writer-agent` tasks 4.6, 4.9
- 10.4 end-to-end approve-all exercise, 10.5 mixed approve/reject exercise → `add-content-writer-agent` tasks 6.2, 6.3

## 9. Error handling and apply

- [x] 9.1 Give the Visual Studio workflow a failure path that marks the run record `FAILED` with the reason and notifies Slack, and wire `settings.errorWorkflow` at the entry point; verify a forced failure is reported; the handler must be **active**, n8n otherwise logs `Workflow "<id>" is not active and cannot be executed` and nothing is reported (hit 2026-09-28)
- [x] 9.2 Extend `scripts/apply_workflow_changes.py` with an idempotent `--create` (POST a workflow body once, keyed by name, print the new id); verify by creating a throwaway workflow, editing it through the existing `PUT` path, then deleting it, and confirm a same-named workflow is left untouched
- [x] 9.3 Create the workflow live with `scripts/apply_workflow_changes.py --create` and re-read to confirm each field landed; pair subsequent edits with `--require-edge`
- [x] 9.4 Confirm the operational boundary by graph inspection: the studio has no schedule, no Slack nodes, no GitHub nodes and no queue access — it is started by its three triggers, writes only to `visual_studio_table`, returns content only, and owns no review gate or commit

## 10. Documentation

- [x] 10.1 Update the n8n operational docs (`AGENTS.md` n8n section) with the `--create` path, the DataTable setup step (`setup_data_tables.py`), the three trigger surfaces and their parameter contract, the frozen-spec mechanism, and the browser-render pipeline (including the `~/.n8n-files` constraint); state explicitly that verification is manual-trigger plus `--require-edge` graph checks, since there is no CI coverage for n8n; verify a reader can follow creation through apply from the docs alone

## 11. Temporal data

Frame files and run records are both throwaway, so both are reaped.

- [x] 11.1 Remove the frame directory on **every** exit path, not just success: `assemble_animation` runs `rm -rf` on its own directory after `base64`, `cleanup_frames` sits between `merge_branches` and `run_record` and removes `~/.n8n-files/<execution>` whatever went wrong on the way, and `Visual Studio Error` removes it when the run fails outright (`run_record` reads `$('merge_branches')` because `ExecuteCommand` does not forward its input); verify `~/.n8n-files` is empty after a successful run and after a forced capture failure.
- [x] 11.2 Add `Visual Studio Prune`: a schedule trigger (daily 04:00 UTC) running one `deleteRows` against `visual_studio_table` with `createdAt lt now-7d`, whatever the row's status, and `settings.errorWorkflow` = `Catch Errors` (not `Visual Studio Error`, which would write a FAILED row about the pruner into the table it is pruning). The DataTable has a system column `createdAt` of type `date` with `lt`/`lte` operators, so no schema change was needed; verify the filter server-side before trusting the node, then confirm the node's first scheduled execution succeeds and deletes nothing it should not.
