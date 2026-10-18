# Tasks

## 1. The requested set, derived once

- [ ] 1.1 `select_article_to_queue` emits `REQUESTED_ASSETS` — the set it already computes with the
  hero rule — beside `PENDING_ASSETS`, and its comment says the field is the one definition every
  consumer reads.
- [ ] 1.2 `if_all_assets_approved` reads `REQUESTED_ASSETS` instead of re-deriving the hero rule,
  keeping its own status logic, and its comment changes from "has to stay the same rule" to the
  structural reason.

## 2. The commit path filters

- [ ] 2.1 `build_commit_files` filters the rows it takes from `read_asset_rows_for_publish` to
  `REQUESTED_ASSETS`, and logs the types it left out so a stale row is visible in the run.
- [ ] 2.2 `read_asset_rows_for_publish` is left filtering on `ENTRY_ID` alone, and the reason is
  recorded where the filter is: the publish path owns its own reads and the decision belongs to the
  node that commits.

## 3. Offline gates

- [x] 3.1 Add a case to `agents/n8n/scripts/test_article_entry_point.py` that executes the committed
  `build_commit_files` with an entry whose rows include a type it no longer requests: the stale type
  is absent from the committed files, the requested type is present at its marker, and the drop is
  logged. Assert the selector's field is what the commit reads, and that no second derivation of the
  hero rule remains in `if_all_assets_approved`.
  **Landed.** `test_a_row_for_a_type_the_entry_no_longer_requests_is_not_committed` (executes the
  node) and `test_the_requested_set_is_derived_once_and_read_by_its_consumers` (structural: the hero
  rule appears once, in the selector, and both consumers read `REQUESTED_ASSETS`). The existing
  `test_the_hero_every_run_asks_for_is_the_wide_frame` asserted the gate's own copy of the rule and
  now asserts it reads the selector's field instead.
- [x] 3.2 Prove the new case fails without the change: revert the export to HEAD, run it, record the
  failures, restore.
  **Landed.** With the export at HEAD, both cases fail and the first names the defect exactly:
  `AssertionError: a row for an unrequested type was committed` against the committed paths
  `[…-image_wide.png, …-image.png]`. Restored: both pass.
- [x] 3.3 Run the offline gates and record the result: `test_article_entry_point.py`,
  `test_content_writer_graph.py`, `test_code_nodes_parse.py`, `test_workflow_invariants.py`, then the
  whole `agents/n8n/scripts/` suite and `ruff`.
  **Landed.** Full suite **539 passed** (537 before this change); the two graph copies agree;
  `openspec validate --all` 14 passed. `ruff` reports one error, pre-existing and unrelated
  (`FURB167` in `test_visual_studio_registry.py:90`, `re.M` for `re.MULTILINE`), untouched by this
  change.

## 4. Apply to the live instance

- [x] 4.1 Ask the owner before writing: present the diff of the three nodes and get an explicit
  answer.
  **Asked 2026-10-18 and answered** — the diff of the three nodes, the offline results and the four
  guards were presented, and the owner chose dry run then apply.
- [x] 4.2 Apply with `scripts/apply_workflow_changes.py --changes`, guarded by `--require-edge` for
  the edges the change assumes, then re-read: the export's node-name set, connections and touched
  nodes match the live read-back, and `active` is unchanged (`False` by design).
  **Landed 2026-10-18.** All four guards held (`select_article_to_queue>update_status_in_progress`,
  `update_status_in_progress>switch_phase`, `read_asset_rows_for_publish>read_draft_for_publish`,
  `if_all_assets_approved>if_assets_blocked`). The three writes landed and the read-back echoed each
  node's new code; the PUT republished on its own (`versionId`/`activeVersionId` → `c338a00e…`).
  Re-read after: both copies 78 nodes, name sets, per-node equality and connections equal to the
  export, and `settings` equal too. **`active` was `True`, not `False`** — see 4.3.
- [x] 4.3 Confirm the entry point is still `active: False` after the apply, so the schedule cannot
  tick while `add-content-writer-agent` 6.6 is open.
  **Not confirmed — the premise was already false, and it is not this change's doing.** Live read
  `active: True, triggerCount: 1` before the apply and `True` after, and the export has said `True`
  since the 2026-10-18 nightly backup (`4c1bfb0`) — every backup before it recorded `False`. So the
  entry point was activated on the instance sometime on 2026-10-17/18, and its `0 0 8 * * 2,4` cron
  is armed. Raised with the owner rather than changed here: whether to deactivate is a decision
  about `add-content-writer-agent` 6.6, and this change must not silently reverse it.

## 5. Documentation

- [x] 5.1 Record the defect and its fix in `AGENTS.md`'s `#### Article Creator` subsection — the
  commit carries the requested set, and the requested set has one definition.
  **Landed**, with the reasoning that made the filter a type filter rather than a status filter, and
  the offline case that pins the single definition.
- [ ] 5.2 Archive when the graph is live and 3.1–3.3 have run:
  `openspec archive fix-publish-commits-unrequested-assets`.
