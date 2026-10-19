# Tasks

## 1. Board intake

- [x] 1.1 Add `agents/n8n/datasets/board_intake.json` — owner, repo, label, state, and the
  defaults an imported row carries (`categories`, `asset_types`, `max_words`, `priority`),
  with the `_comment` keys the other datasets use. Validated as JSON and with
  `priority`/`categories` checked against the article lane's own taxonomy in 3.1
- [x] 1.2 Author `agents/n8n/workflows/content_board_curator.workflow.json` as a create
  body: `schedule_trigger` → the two `DownloadTemplate` fetches → `parse_board_config` →
  `list_board_issues` → `read_article_queue` → `build_intake_rows` → `if_has_new` →
  `append_article_queue`, then the ceiling leg, then `notify_board`.
  `settings.errorWorkflow` names the existing `Catch Errors`. The board read is
  `resource: repository, operation: getIssues` with the label and state as expressions from
  the config, and `alwaysOutputData` so an empty board does not stop the run
- [x] 1.3 `build_intake_rows` dedupes on `ENTRY_ID` (`gh-<number>`) and `LINK` against every
  row the queue holds, drops pull requests, and emits the row's own title/body/URL plus the
  configured defaults with `ORIGIN=BOARD`, `STATUS=QUEUE`
- [x] 1.4 Both reads carry `alwaysOutputData`, so an empty board or an empty queue still
  reaches the ceiling and the notice; `build_intake_rows` emits one zero-count item when
  nothing is new so `if_has_new` has something to branch on

## 2. The one-week ceiling

- [x] 2.1 Add `cancel_after_days: 7` to `datasets/curator_config.json` with its rationale,
  and expose it from `parse_curator_config` (both copies) as
  `cancel_after_days: Math.max(1, num(cfg.cancel_after_days, 7))`
- [x] 2.2 Add `build_cancel_rows` and `cancel_stale_queue` to
  `content_feed_curator.workflow.json` (both copies), fan `if_write_to_sheet` out to the new
  pass, and write `CANCELED` — this lane's spelling
- [x] 2.3 `build_expire_rows` returns early on a row past the ceiling, measured on the
  ceiling's own clock (`UPDATE_DATE`) rather than the `PUBLISHED_AT` the TTL check uses, so no
  row is selected by both the TTL pass and the ceiling pass — and none escapes both. The first
  version skipped on `PUBLISHED_AT` and did exactly that (an old article rewritten recently);
  `test_the_expire_pass_skips_on_the_ceilings_own_clock` fails without the fix
- [x] 2.4 The board curator's `build_cancel_rows` / `if_has_cancels` /
  `cancel_stale_articles` cancel an `article_queue` row still in play, setting `STATUS` and
  `ARTICLE_STATUS` both, and read the ceiling from `curator_config.json` rather than a
  second copy

## 3. Tests

- [x] 3.1 Add `agents/n8n/scripts/test_content_board_curator.py`: the graph (scheduled entry
  point, error workflow resolves, GitHub operation and filter, both reads tolerate empty),
  the config, and both Code nodes executed against stubs — an issue imported once and
  skipped when already present, a pull request ignored, the row's fields, the ceiling
  cancelling in-play rows and never a live or terminal one, and the two lanes' spellings
- [x] 3.2 `uv run -- pytest agents/n8n/scripts/ -q` — **571 passed, 1 skipped** (the skipped
  one is the board workflow's "no published copy" check, which is correct for a create
  body); `ruff check` clean on the new file (the one remaining lint error is pre-existing in
  `test_visual_studio_registry.py`)
- [x] 3.3 Proven to fail without the change: with `content_feed_curator.workflow.json`
  reverted, the five curator-ceiling tests fail; with the board workflow absent, the module
  fails at collection

## 4. Documentation

- [x] 4.1 Record the two workflows and the ceiling in `AGENTS.md`, where a reader looks
  before touching either workflow, and keep the per-knob rationale in the datasets'
  `_comment` keys

## 5. Apply (live, owner-approved)

- [x] 5.1 Apply the curator edit with `scripts/apply_workflow_changes.py --changes`, guarded by
  `--require-edge` for `if_write_to_sheet>build_expire_rows` and
  `build_expire_rows>expire_auto_queue`. **Landed 2026-10-18**: two nodes added, the fan-out and
  the two `jsCode`s and the sticky note written, workflow still `active`. Read back and diffed
  against the export: top-level and `activeVersion` both deep-equal the committed file. The first
  pass dropped `if_write_to_sheet`'s false branch (`if_mark_read`) because a connections entry
  replaces the whole array — a second spec restored it. **Lesson: name every branch of a source
  in the spec.**
- [x] 5.2 Create `Content Board Curator` with `--create`, then activate it. **Landed 2026-10-18**:
  created `RCSPaKMKsckAnJ9B`, 15 nodes, `errorWorkflow` `fejq5nN6LP3F820w`, activated (`active:
  true`). A manual trigger was added beside the schedule so a run can be forced from the editor.
  Read back and diffed against the export: nodes, connections and settings equal (the export
  gained the two n8n-generated `webhookId`s). **The GitHub read is not yet exercised by a run** —
  see 5.4.
- [ ] 5.3 Let the nightly backup rewrite both files as full exports (the curator file already is
  one; the board file gains its id and `activeVersion`), and confirm `pytest
  agents/n8n/scripts/` stays green afterwards.
- [x] 5.4 Force one run (editor *Execute workflow*, or the 12:15 tick) and read the outcome back
  from `article_queue`: the four open `post` issues imported once, `ORIGIN=BOARD`, no duplicates
  on a second run, and the Slack notice naming the count. This is the only check that proves the
  GitHub node's filter actually restricts to the label. **Measured 2026-10-19** with `n8n
  execute --id`: runs 14349 and 14355 succeeded, the second imported 0 and the read carried four
  `gh-` rows, one per open issue; the Slack notice named the four titles. Getting there fixed
  two defects the first runs exposed: the API-created `append_article_queue` had no
  `columns.schema` and threw before writing (14174, 14322), and `read_article_queue` returned
  every row once per issue because a Sheets read past 4.1 fans out over its input — `executeOnce`
  took 792 items for 198 rows down to 202.
