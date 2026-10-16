# Tasks

## 1. Spec

- [x] 1.1 `proposal.md`, `design.md` and this file land under `openspec/changes/add-launch-card-type/`; `design.md` records the six gate findings, the four decisions (D1 static png at 1.91:1, D2 a `launch` form, D3 no hook default, D4 the multi-slide review), the three rejected alternatives and the one risk — the composer obeying "compose it in the first frame" is [UNVERIFIED]
- [x] 1.2 Spec delta `specs/visual-studio/spec.md`: `Types are declared in a registry` is MODIFIED to name `launch_card` and gains the scenario that a still type declares no clip; one requirement is ADDED, `A still raster type is composed in one frame`, stating the first-frame contract and that it is not a clip
- [x] 1.3 `openspec validate --all` passes (12 passed, 0 failed)

## 2. Registry

- [x] 2.1 Add to `agents/n8n/datasets/visual_types.json`: `launch_card`, `brandKind: diagrammatic`, `author: agent`, `render: static`, `format: png`, `aspect: 1.91:1`, `available: true`, budget `fps 30 / frames 30 / viewport 1280`; no `durationSeconds`, no `secondsPerScene`, no `holdSeconds` (a still declares no clip). The file is fetched through `DownloadTemplate` with an empty `template_vars`, so it must still contain no doubled-curly-brace placeholder. `_comment_render` was corrected at the same time: it described `static` as "one raster file authored directly", which is not what the composer's still is
- [x] 2.2 `scripts/test_visual_studio_registry.py`: the declared-id list names `launch_card`; `test_the_launch_card_is_a_still_at_the_announcement_frame` asserts the still type is `agent` + `static` + `png`, is 1.91:1, declares no scene floor, no duration and no hold, and renders wider than tall at 1200 px or more; `test_a_png_type_is_a_still` guards the format the brief now branches on

## 3. Vocabulary

- [x] 3.1 `agents/n8n/prompts/visual_forms.md`: `launch` defined in the file's voice. Live on push
- [x] 3.2 The four enum copies gain `launch` (2 in `visual_studio`, 4 in `content_feed_curator`); `test_the_form_vocabulary_is_one_file` and `test_the_form_enum_matches_the_vocabulary` pass
- [x] 3.3 `agents/n8n/datasets/hook_types.json`: the vocabulary comment names `launch` and states why no hook defaults to it. Live on push

## 4. Brief

- [x] 4.1 `build_author_brief` gains the `format === 'png'` branch in both copies (identical after the edit): one still card at WxH, the whole visual complete in the first frame, `stillSceneLine` folding a declared `SCENES` count into the one frame instead of a sequence, and no animated `sampling` instruction
- [x] 4.2 `scripts/test_visual_studio_graph.py::test_the_brief_composes_a_still_in_one_frame` asserts the branch exists, names the frame that ships, folds in the scene count and does not carry the animated instruction

## 5. Docs

- [x] 5.1 `AGENTS.md`: the type list becomes seven and gains `launch_card` (and the note that a still type declares no clip); a new **A still is the render's first frame** paragraph states the `-frames:v 1` mechanism and why the brief needs the branch; a new **When a launch card, and when something else** paragraph carries the rule of thumb, the per-type alternative, why no hook defaults to `launch`, and the deferred paged carousel. The `FORCE` list gains `launch`

## 6. Apply and verify

- [x] 6.1 `uv run pytest scripts/` — 435 passed, 1 skipped; `uv run ruff check .` — clean. Verified offline against both graph copies
- [x] 6.2a The live instance was **read** and diffed without writing (`--changes /tmp/opencode/launch_card_changes.json`, no `--apply`): live `jsCode` for all four nodes was byte-identical to the pre-change export, so there was no live drift to overwrite, and the planned delta was exactly the intended one. Recorded here: `Visual Studio` = `2pSrRNmYR2jkX1JG` (29 nodes), `Content Feed Curator` = `iIA5QN5HuK21TmBX` (50 nodes), both active before and after
- [x] 6.2 Applied with `--apply`, both workflows guarded by `--require-edge` (`normalize_input>download_brand`, `if_agent>build_author_brief`, `judge_llm>parse_judge`, `judge_llm_backfill>parse_judge_backfill`), then re-read: all four nodes are byte-identical to the export. `active` stayed `True` on both
- [x] 6.2b **Incident, found and fixed the same session.** The first apply shipped `build_author_brief` with a literal `\n` between `stillPlanLine` and `stillSceneLine` instead of a newline — a JavaScript **syntax error**, so every agent-authored asset would have failed at that node. Nothing offline caught it: the JSON was valid, the diff read as two lines, and every textual assertion passed. Found by executing the live jsCode under node. Fixed in the export, re-applied as a second field-level apply, and verified: node parses every Code node of both exports, and live matches. The class is now gated by `scripts/test_code_nodes_parse.py` (every export's `jsCode` through `node --check` in an async wrapper) with node installed in the `agents/n8n` CI job, and recorded in `AGENTS.md`
- [x] 6.3a The brief was verified by **executing the live `build_author_brief`** under node with a `launch_card` request: frame `png 1280x670 (1.91:1)`, artifact `visual-studio/13499-launch_card.png`, session `launch_card-13499`, and a brief that takes the still branch — one card at 1280x670, "the whole visual complete in the first frame of the composition", no entrance animation, a declared `SCENES=3` folded into the card's three parts, and the vocabulary carrying `launch`. The animated branch is not taken
- [x] 6.3 Probed the still path on live: `POST /webhook/visual-studio` with `ASSET_TYPES=launch_card`, `FORCE=launch` and a real `CONTENT` — see section 7, which records the run, the blank frame it exposed and the fix

## 7. The first probe, and the defect it found

- [x] 7.1 Pushed (`6dec04f`) and probed `POST /webhook/visual-studio` with `ASSET_TYPES=launch_card`, `FORCE=launch` and a real launch text. The run succeeded end to end — execution **13581**, session `launch_card-13581`, a stored key `visual-studio/13581-launch_card.png`, `content-type=image/png` — and the composer's report shows it authored the card faithfully: a `launch` form, lockup, badge, headline, five chips and the product's interface window, 25 KB of HTML, a 7-second h264 1280x670 render at 210 frames
- [x] 7.2 **The artifact was blank.** Fetched through `temp_retrieve` and decoded locally: 4,107 bytes, 8-bit RGB, 1280x670, **one distinct colour** (`#0c1016`) across 100% of the pixels — 0.0% non-background. The composer animated its entrances (the framework's motion rules ask for them), so the render's first frame is the empty page, and asking the brief for a card complete at t=0 did not change that
- [x] 7.3 Fix measured on the real render, in the pi-render session: frame 1 = 4,107 bytes / 1 colour; final frame (`-sseof -0.1`) = 251,865 bytes / 12,257 colours / 54.5% non-background, with content in every row band; one second earlier (`-sseof -1`) = 246,944 bytes / 11,709 colours. The card was always right; only the sample was wrong
- [x] 7.4 Fix applied: `transcodeArgs("png")` samples the final frame, its adapter test now fails without `-sseof` (41 adapter tests pass), the brief names the final frame and forbids only an exit, and the registry comment, the spec delta, `design.md`, `proposal.md` and `AGENTS.md` all carry the measurement
- [ ] 7.5 Push the adapter fix (which triggers the adapter image build and its digest re-pin), roll the pi-render session onto the new image, and re-probe with a fresh run: the same request must come back with a png whose frame is a card — more than one colour and tens of KB, not 4,107 bytes. **Blocked by nothing but the push this task describes**
- [ ] 7.6 Confirm the run's own `S3_BYTES` and the decoded pixel size agree with the measured final frame, and record the run id here
