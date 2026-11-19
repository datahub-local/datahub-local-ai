# Tasks

## 1. Placement on the asset

- [ ] 1.1 `derive_asset_plan` (both copies): each item carries `PLACEMENT` (`lead` or
      `inline`) and, for an inline figure, `HEADING` + `SECTION` (it already carries
      the latter two) — one derivation, read by the brief and the commit.
- [ ] 1.2 `build_commit_files` (both copies): the lead is referenced full-width after the
      opening; each figure is referenced inside a figure block at the site's inline width,
      alt text from its section heading, at its `figure_<k>` path.

## 2. Briefs

- [x] 2.1 `split_pending_types`' figure `EXTRA_PROMPT` (the brief composer, not
      `derive_asset_plan`): carries the section and the rule that the lead image already
      states the article's thesis — the figure shows this section's mechanics, never a
      second overview. Live 2026-11-19.
- [ ] 2.2 The figure brief states the inline reading size: one idea, labels legible at
      80% of the text column, no code text as imagery.
- [ ] 2.3 `visual_motion_rules.md` (or the type's declared brief): the lead is the page's
      one moving asset; figures are still.

## 3. The publish chain, per item

- [x] 3.1 `asset_publish_url`, `asset_signed_url`, `asset_bytes_from_download` (both
      copies): one item per input, identity carried per item — the two parsers pair through
      n8n's `itemMatching(i)` (their input is the MCP answer, which replaces `json`), and
      the download step matches each item's own `S3_KEY` against the plan. No `first()`,
      no global-node lookups. Verified live in `activeVersion`; harness 2-in → 2-out on
      every step, single-asset unchanged.
- [x] 3.2 `collect_tree_entries`' count assertion stays as the regression detector; the
      harness reproduces the recorded "1 blobs for 2 assets" failure given one answer for
      two binaries.

## 4. Verify

- [x] 4.1 Offline: harness the chain (2 items and 1 item), the plan's fields, the figure
      brief's text; adapter suite 103/103; structural checks both copies.
- [ ] 4.2 Live: one two-asset article commits hero and figure in one commit; the page
      renders the lead full-width and the figure inline; the two visuals do not restate
      each other. `[UNVERIFIED]` until run.

## 5. Docs

- [ ] 5.1 `docs/agent/n8n.md`'s publish-chain paragraph describes the single-asset-era
      chain (`first()` parses); update it to the per-item contract and the paired-item
      constraint (a JSON-returning HTTP node replaces `json`, so identity rides the
      paired item, not the payload).
- [ ] 5.2 The article-lane asset section states the placement contract (lead at the text
      width, figure inline at 80%, alt from the heading) once task 1.2 lands.
