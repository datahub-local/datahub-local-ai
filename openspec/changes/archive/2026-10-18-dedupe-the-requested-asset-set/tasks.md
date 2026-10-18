# Tasks

## 1. De-duplicate the set

- [x] 1.1 `select_article_to_queue`'s `requested()` de-duplicates `ASSET_TYPES` with
  `[...new Set(...)]` before applying the hero rule, so `REQUESTED_ASSETS` and `PENDING_ASSETS` name
  each type once. Both graph copies.
  **Landed.** `const list = [...new Set(String(r.ASSET_TYPES || '').split(',').map((s) => s.trim()).filter(Boolean))];`
- [x] 1.2 Add a case to `agents/n8n/scripts/test_article_entry_point.py` that executes the committed
  `select_article_to_queue` with a row naming a type twice, and asserts `REQUESTED_ASSETS` and
  `PENDING_ASSETS` name it once — with the hero rule still applied, and a duplicated hero still one
  hero.
  **Landed.** `test_a_type_named_twice_is_requested_once`, which runs the node through the same
  harness the commit-path case uses (extended to stub `$input`).

## 2. Offline gates

- [x] 2.1 Prove the new case fails without the change: revert the export to HEAD, run, record the
  failure, restore.
  **Landed.** With the export at HEAD:
  `assert 'image_wide,svg_wide,svg_wide' == 'image_wide,svg_wide'` — the duplicate in the message.
  Restored: passes.
- [x] 2.2 Run the gates and record the result: `test_article_entry_point.py`,
  `test_content_writer_graph.py`, `test_code_nodes_parse.py`, `test_workflow_invariants.py`, then the
  whole `agents/n8n/scripts/` suite and `ruff`.
  **Landed.** Full suite passes; both graph copies agree; `openspec validate --all` passes. `ruff`
  reports one error, pre-existing and unrelated (`FURB167` in `test_visual_studio_registry.py`).

## 3. Apply to the live instance

- [x] 3.1 Apply `Article Content Writer` with `--changes` and `--require-edge` on the selector's own
  edges, then re-read and diff against the export.
  **Landed 2026-10-18**, together with the retry-carry change's two workflows. Both guards held
  (`select_article_to_queue>update_status_in_progress`, `update_status_in_progress>switch_phase`),
  the write landed, and the re-read shows no node, connection or setting differing from the export.
- [x] 3.2 Confirm the entry point stays `active: False`.
  **Landed.** `active: False -> False`. Its export still claims a published version, because it was
  deactivated after the last backup; the 02:00 backup reconciles that, and the live object has
  `activeVersion: null`.

## 4. Documentation

- [x] 4.1 Record in `AGENTS.md`'s `#### Article Creator` subsection that the requested set names each
  type once, and why the de-duplication lives in the selector.
  **Landed**, with the live row's own value (`svg_wide,svg_wide`) as the evidence.
- [ ] 4.2 Archive when the graph is live and 2.1–2.2 have run:
  `openspec archive dedupe-the-requested-asset-set`.
