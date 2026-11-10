# Tasks

## 1. The drafting contract

- [x] 1.1 `agents/adapters/pi-writer/prompts/article_task.md` and `writing.md`: the hero is
      `<!-- asset:svg_wide -->` after the opening, exactly once; a section figure is
      `<!-- asset:figure -->` after the section it illustrates, zero times when no diagram earns its
      place, and never before the first section.
- [x] 1.2 `articlePrompt` fills `MAX_FIGURES` from the brief, and `build_article_request` passes the
      row's `MAX_FIGURES || 3`; a missing column reads as 3 rather than failing the run.
- [x] 1.3 `parse_article` (both copies of the export): count `figure` markers in document order,
      report `FIGURES: n`, reject `n > MAX_FIGURES` with the count and the cap, and treat `figure`
      as a known slot rather than a type not requested. The hero check is unchanged.

## 2. The asset plan comes from the approved draft

- [x] 2.1 One Code node derives the plan from the stored draft: the declared hero types plus
      `figure_1…figure_N`, each figure carrying its index, its section heading and its section text
      (the content between the surrounding `##` headings, 1,500 characters, fences excluded).
- [x] 2.2 `select_article_to_queue` keeps choosing the phase but stops being the only definition of
      the requested set: the assets and publish phases read the derived plan.
- [x] 2.3 `if_assets_pending`, `split_pending_types`, the publish gate and `build_commit_files` read
      the derived plan, not `REQUESTED_ASSETS` alone.
- [x] 2.4 `retire_figures` after `update_article_approved`: every `figure_*` row for the entry is set
      `CANCELLED` before the new plan is authored, because a new draft can move or drop a slot. The
      hero keeps its approval.

## 3. Authoring and storage

- [x] 3.1 `agents/n8n/datasets/visual_types.json`: add `figure` — author `agent`, render `static`,
      format `svg`, aspect 16:9, form `diagram`, available. Keep `image`/`image_wide` declared.
- [x] 3.2 The assets phase emits one studio item per slot: `ASSET_TYPE: figure` for the studio and
      `SLOT: figure_<k>` for storage, with the section text as `EXTRA_PROMPT`.
- [x] 3.3 `split_assets`/`store_assets` persist `SLOT` as the row's `ASSET_TYPE`, so each figure has
      its own row, S3 key and Slack review.
- [x] 3.4 `agents/n8n/datasets/board_intake.json`: keep the composer-only `asset_types`
      (`svg_wide`). Do not add `MAX_FIGURES` to the curator's append until the `article_queue`
      column exists — the lane reads it when present and defaults to 3 when absent, so the column is
      a manual, per-row control first.

## 4. Commit

- [x] 4.1 `build_commit_files`: replace the k-th `<!-- asset:figure -->` with
      `/img/<slug>-figure-<k>.svg`, alt from that section's heading, and fail if a figure row has no
      marker or a marker has no row.
- [x] 4.2 The marker count in `parse_article` and the replacement in `build_commit_files` agree on
      document order; a duplicate or missing slot fails loudly before the commit.

## 5. Verification

- [x] 5.1 Offline: a draft with zero, two and five figure markers (five against a cap of 3) reports
      `FIGURES` correctly and only the last is rejected. **Executed 2026-11-10** by running the
      committed `parse_article`, `derive_asset_plan`, `split_pending_types` and `build_commit_files`
      jsCode in a Node harness against stub items.
- [ ] 5.2 Live: one article with two figures authors exactly two rows `figure_1`/`figure_2`, each
      with its own review and its own committed path; the hero is unchanged. `[UNVERIFIED]`.
- [ ] 5.3 Live: a row declaring `image_wide` still gets the raster, and the default hero stays
      `svg_wide`. `[UNVERIFIED]`.
- [x] 5.4 Apply the workflow edits live, read them back against the export, and keep the workflow
      active.
- [x] 5.5 `openspec validate --all` and `node --test 'agents/adapters/pi-writer/test/*.test.mjs'`.

- [ ] 5.6 Rebuild and publish the `pi-writer` image for the prompt change (`MAX_FIGURES`, the hero and
      figure contract) and pin its digest before the drafting turn can place figure slots.
      `blocked by` the image pipeline, as in the previous adapter change. `[UNVERIFIED]`
