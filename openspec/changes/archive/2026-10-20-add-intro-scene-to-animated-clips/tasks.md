# Tasks

## 1. Registry

- [x] 1.1 Declare `introScene: true` on `animation`, `animation_linkedin` and
      `animation_linkedin_video` in `agents/n8n/datasets/visual_types.json`, and document
      the field in `_comment_introScene`; leave `tiles`, `tiles_wide`, `svg`, `deck` and
      the stills without it

## 2. Brief

- [x] 2.1 In `build_author_brief` (both copies), add `introLine` for a blank `SCENES` on a
      type whose `INTRO_SCENE` is true, and insert it in the video branch only; leave the
      declared `N + 1` line and the single-scene case unchanged
- [x] 2.2 Carry `INTRO_SCENE` from `parse_registry` onto the request and from
      `agent_result` onto the asset

## 3. Review stills

- [x] 3.1 Change `DEFAULT_STILL_OFFSETS` in `agents/adapters/pi-render/session-lib.mjs` to
      `[0.1, 0.4, 0.7]` so the opening scene is in the first still

## 4. Tests

- [x] 4.1 `test_visual_studio_graph.py`: an animated type with a blank count asks for an
      opening scene naming the subject, and the deck/SVG/PNG branches do not
- [x] 4.2 `test_visual_studio_registry.py`: the animation types declare `introScene`, the
      loops and stills do not
- [x] 4.3 `agents/adapters/pi-render/test/session-lib.test.mjs`: the first clip still is at
      10% of the declared duration
- [x] 4.4 Run the three test files, `test_code_nodes_parse.py` and `ruff check`
- [x] 4.5 Run the whole `agents/n8n/scripts/` suite and `test_prompt_sources.py`; both copies
      of every export must pass

## 6. Rule

- [x] 6.1 Add the prompt-source rule to `AGENTS.md` under *AI prompt policy*: every
      instruction a model reads lives in a prompt file or the authoring brief; inline
      instruction prose in code is a gap; a definition is written where the model reads it

## 7. Scene contract

- [x] 7.1 Add `agents/n8n/prompts/visual_scene.md`: what a scene is (one beat, one
      continuous shot, held long enough to read), what the storyboard is, where the title
      scene sits, and the one-idea rule
- [x] 7.2 Fetch it (`download_scene_rules` → `scene_rules`) and append it to the brief beside
      the motion rules (both copies); keep the count/placement lines in `build_author_brief`
- [x] 7.3 Assert in `test_visual_studio_graph.py` that the brief carries the scene file and
      that the file states the contract

## 8. Audit gaps

- [x] 8.1 **G1** covered by task 7
- [x] 8.2 **G2**: move the `research_sources` and `read_page` descriptions into a prompt
      file; the tool nodes read it
- [x] 8.3 **G3**: move the `SUBJECT_MOTIFS` / `HOOK_TREATMENT` section wording into
      `prompts/linkedin_image_prompt.md`; `parse_image_motifs` emits lists only
- [x] 8.4 **G4**: move the format/length/closing directive lists into a prompt file;
      `set_variety_directives` selects from it
- [x] 8.5 **G5**: move the suggested-prompt template beside `diagram_generator.md` and fill
      it from the form values
- [x] 8.6 Re-run the audit over every export and record any new gap in `design.md`

## 9. Enforcement

- [x] 9.1 Add `agents/n8n/scripts/test_prompt_sources.py`: model text resolves to a
      `download_*` node or an allowlisted builder; every template target exists; the
      allowlist names only accepted gaps with a reason
- [x] 9.2 Wire it into `agents/n8n/scripts/` (the existing CI job runs the directory)

## 10. Apply

- [x] 10.0 Push the prompt files to `main` **before** the graph: every studio fetch
      (`DownloadTemplate`) reads GitHub `main`, so a graph naming `prompts/visual_scene.md`,
      `prompts/linkedin_variety.md` or `prompts/article_tools.md` before they are pushed
      fails on a 404. Applied and rolled back once on 2026-10-19 for exactly this reason.
- [x] 10.1 Apply the five workflow edits live with
      `scripts/apply_workflow_changes.py --require-edge`, re-read and diff the export
      against live (both copies; re-activate any workflow whose node set changed):
      `visual_studio` (scene fetch + brief), `article_creator` (tool prompts),
      `linked_in_post_creator` (variety fetch), `linked_in_image_creator` (motif lists),
      `image_content_generator` (prompt prefill). Attempted 2026-10-19: all five wrote and
      re-activated, then were rolled back to the pre-change graphs because 10.0 was not
      done; the live instance is back on the old graph until the push lands.
- [x] 10.2 `publish-images.yaml` rebuilt the adapter (run 39298318860, success) and pinned
      digest `sha256:f1ce6dbb…` in 726b843; the pi-render pod rolled at 18:04 and
      `DEFAULT_STILL_OFFSETS` reads `[0.1,0.4,0.7]` inside it (it triggers on the
      adapter path, re-pins `agents/adapters/pi-render/deploy/session.yaml` by digest, and
      ArgoCD rolls it); confirm the running pod carries the new digest before 10.3
- [x] 10.4 Smoke test: `POST /webhook/visual-studio-test` with `ASSET_TYPES=image` ran
      execution 14359 (`success`); `download_scene_rules` returned the file and the text
      "A scene is one beat" is in the run data
- [x] 10.3 Live clip run 14371 (`verify-intro-1019-2`, `animation_linkedin_video`,
      `SCENES` blank) succeeded; its final `review-1.jpg` (3 s of 30) shows the opening
      title "DuckDB — A variant type built in, so JSON columns query without a cast on
      every field", so the subject is named before the content scenes and the critic sees it and confirm it shows an opening scene
      naming the subject
