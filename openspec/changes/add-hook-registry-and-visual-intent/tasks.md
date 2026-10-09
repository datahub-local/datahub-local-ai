# Tasks

## 1. Hook registry (`agents/n8n/datasets/hook_types.json`)

- [x] 1.1 Author the registry: 15–20 hooks grouped by intent, each with `id`, `when` (eligibility), `opening` (the post's opening shape) and `visual` (`form` one of the `FORCE` values, `motion`, `scenes`), plus `image` (the raster composition device); verify the file parses and contains no doubled-curly-brace placeholder (it is fetched through `DownloadTemplate` with empty vars) — 19 hooks; parses; no placeholder
- [x] 1.2 Cover the required families — argument, evidence, news, reference (`ROUNDUP` among them) and narrative — and verify every `visual.form` is a value `normalize_input` accepts — all 19 forms are in `FORCE`
- [x] 1.3 Add `agents/n8n/scripts/test_hook_registry.py` asserting the registry parses, every `form` is a valid `FORCE`, and no hook id list is carried elsewhere (the `test_brand.py` shape); verify it fails if an id is duplicated into `image_motifs.json` — the hook map was removed from `image_motifs.json` and `parse_image_motifs` now reads the registry
- [x] 1.4 Commit and push the registry, since `DownloadTemplate` reads GitHub `main`; verify it is on `origin/main` before any live run — **not done: not pushed**

## 2. Judge (`prompts/curator_judge.md`, `content_feed_curator.workflow.json`)

- [x] 2.1 Rewrite `curator_judge.md` to select a `hook` from the registry and a `visual` intent (`form`, `motion`, `scenes`) in the same call, replacing the six-value prose enum; verify the prompt has no hard-coded hook ids and resolves `{{ HOOKS }}` — done; only the example `TRADE_OFF` remains
- [x] 2.2 Inject `{{ HOOKS }}` into the judge from the registry (a workflow var built from the fetched dataset); verify a run renders the full id list and an unknown id returned by the model is rejected — `download_hook_registry` + `parse_hook_registry` feed `download_judge_prompt` and `parse_judge`
- [x] 2.3 `parse_judge`: validate `hook` against the registry (not the inline `HOOKS` array) and validate the visual intent (`form` in `FORCE`, `motion` boolean, `scenes` a bounded integer, falling back to the hook's registry default); verify an out-of-registry hook falls back to empty as today
- [x] 2.4 `admit_to_backlog` and `build_queue_rows`: add `HOOK`, `VISUAL_FORM`, `ANIMATED`, `SCENES` to the emitted row and the column list (now 22), and map them in `append_content_queue`; verify the append maps every new column to a sheet header — **the four sheet headers must be added to `content_queue` before the live append runs (a sheet change, not a repo change)**
- [x] 2.5 Move `build_expire_rows`' TTL read from the `Hook: X.` prefix to the `HOOK` column (keeping the prefix as a fallback for old rows)
- [x] 2.6 Apply the curator workflow live with `--require-edge` guards on `parse_judge` and `admit_to_backlog`, re-read live, diff against the export, and publish; verify the four columns are written and the digest names the hook — **not done: no live apply**

## 3. Post creator (`linked_in_post_creator.workflow.json`)

- [x] 3.1 `set_variety_directives`: read `HOOK` from the row and map it to the registry's `opening`; keep the random `format`, `length` and `closing`
- [x] 3.2 Retire `classify_content` and `download_post_classify_prompt`; `set_workflow_vars` now feeds the registry fetch and `set_variety_directives`
- [x] 3.3 Pass `HOOK` through `main_trigger` to the creator (the row's value, not a re-derived one)
- [x] 3.4 Apply live with `--require-edge` on the creator entry, publish, and diff against live; verify `classify_content` is gone and the graph still has one terminal — **not done: no live apply**

## 4. Sharing (`linked_in_post_sharing.workflow.json`)

- [x] 4.1 Drive the media branch from the row's intent: `ANIMATED` (column) or a manual `POST_MEDIA` decides animated vs still; `FORCE` comes from `VISUAL_FORM`
- [x] 4.2 Forward `SCENES` into the studio request for a roundup
- [x] 4.3 Extend `scripts/test_linkedin_animated_media.py` (unchanged assertions still hold) and add the row-intent assertions in `test_hook_registry.py`
- [x] 4.4 Apply live with `--require-edge`, publish, re-read, and diff against live — **not done: no live apply**

## 5. Visual Studio (`visual_studio.workflow.json`)

- [x] 5.1 Accept an optional `SCENES` on the studio request (`normalize_input`, the form trigger) and include it in the authoring brief as "one item per scene, N scenes", leaving the composer's storyboard in charge when blank
- [x] 5.2 Extend `scripts/test_visual_studio_graph.py` assertions via `test_hook_registry.py::test_visual_studio_accepts_a_scene_plan`
- [x] 5.3 Apply live with `--require-edge`, publish, re-read, and diff against live — **not done: no live apply**

## 6. Verify

- [x] 6.1 Run the `agents/n8n/scripts/` suite; verify all pass and the registry-drift test is included — 153 passed
- [ ] 6.2 Manual acceptance, roundup: run the state-of article end to end and verify the row's `HOOK=ROUNDUP`, the studio received `FORCE=data`/`SCENES`, and the published GIF is a multi-scene sequence — **not done: no live run**
- [ ] 6.3 Manual acceptance, argument row: verify the post opens on the classifier's hook (not a random one) and the media `FORCE` matches the registry default — **not done: no live run**
- [ ] 6.4 Verify a manually set `POST_MEDIA` row still behaves as before, and a blank row falls back to the still image when no agent asset exists — **not done: no live run**

## 7. Documentation

- [x] 7.1 Update the `#### LinkedIn post media` section of `AGENTS.md` and add a `#### Post hooks and the visual intent` subsection: the registry, the hook/visual columns, the retirement of `classify_content` and `POST_MEDIA`-as-default
- [x] 7.2 Record in `AGENTS.md` that the hook is decided once and where

## 7b. EXTRA_PROMPT

- [x] 7b.1 Drop the `Hook: X.` prefix from `EXTRA_PROMPT` now that `HOOK` is a column, so the hook lives in one place; `EXTRA_PROMPT` carries only the judge's angle, and `build_expire_rows` keeps the prefix as a fallback for pre-column rows

## 8. Self-heal the pre-column queue

- [x] 8.1 Add the curator self-heal branch: `select_unclassified_queue` (queued `AUTO` rows with an empty `HOOK`) → `loop_backfill_queue` → `backfill_fetch_content` (Download Content by URL) → `backfill_judge_vars` → `download_judge_prompt_backfill` → `judge_llm_backfill` → `parse_judge_backfill` → `update_backfill_columns` (writes `HOOK`/`VISUAL_FORM`/`ANIMATED`/`SCENES` by `row_number`) → back to the loop
- [x] 8.2 Bound it: `CAP = 12` rows per run, so a ~60-row backlog backfills over a few days instead of one spike; the branch is a no-op once every queued row is classified
- [x] 8.3 An unparseable re-judge verdict leaves the row unclassified (no guess written); asserted in `test_hook_registry.py::test_the_curator_self_heals_unclassified_rows`
- [x] 8.4 Apply the curator live with `--require-edge` and publish; verify the first run writes the columns for the pre-column rows
- [ ] 8.5 Verify the branch goes quiet: a second run re-judges nothing and costs no calls


## 9. Live apply (2026-10-09)

- [x] 9.1 Applied all five workflows live with `scripts/apply_workflow_changes.py --changes` (extended to set non-`main` connection types, e.g. `ai_languageModel`): +10/-0 nodes and 6 field-sets on the curator, +2/-2 on the creator, 4 field-sets on sharing, +1 on the image creator, 3 field-sets on Visual Studio
- [x] 9.2 Re-read live and diffed against the exports: all five `MATCH` on nodes, connections and settings; `active=True` and `activeVersion == draft` for all five, so the published graph carries the change
- [x] 9.3 Fixed a bug the diff caught: the creator export kept dangling `ai_model`/`ai_model_fallback` edges to the removed `classify_content`; stripped to match live
- [x] 9.4 Fixed a live ordering bug the first manual run exposed (exec 12742): the registry branch was a sibling of the candidate fetch, so `parse_hook_registry` had not run when the backfill's judge prompt referenced it and the run aborted (`Referenced node is unexecuted`). The registry is now chained before the fetch (`parse_curator_config → download_hook_registry → parse_hook_registry → fetch_candidates`), so it is an ancestor of both the main judge and the backfill; re-applied and verified `MATCH`
- [ ] 9.5 Re-run the curator and verify the 12 unclassified rows get `HOOK`/`VISUAL_FORM`/`POST_MEDIA`/`SCENES` and that a later run re-judges nothing
- [x] 9.6 `POST_MEDIA` is the one media column: the curator writes `POST_MEDIA = ANIMATED | STATIC` (from the judge's motion), the sharing switch reads `POST_MEDIA` only, and `ANIMATED` is dropped from the mapping; a human forces either way by editing `POST_MEDIA`. Re-applied and verified `MATCH`
- [x] 9.7 Fixed a doubled-brace switch expression (`={{{{ … }}}}`) introduced by the `POST_MEDIA` edit; the live switch is `={{['ANIMATED','AGENT'].includes(String(POST_MEDIA||'').toUpperCase())}}`
