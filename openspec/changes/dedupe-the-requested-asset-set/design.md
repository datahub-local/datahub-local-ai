# Design

## Context

- `article_content_writer.workflow.json`, `select_article_to_queue`:
  ```js
  const requested = (r) => {
    const list = String(r.ASSET_TYPES || '').split(',').map((s) => s.trim()).filter(Boolean);
    const hasHero = list.includes('image_wide') || list.includes('image');
    return hasHero ? list : ['image_wide', ...list];
  };
  ```
  No de-duplication. `svg_wide,svg_wide` → `['image_wide', 'svg_wide', 'svg_wide']`.
- Execution 14018 (2026-10-18), `select_article_to_queue`'s own output:
  `REQUESTED_ASSETS` was not yet a field, but `PENDING_ASSETS` was `"image_wide,svg_wide,svg_wide"` —
  the same derivation, printed.
- `split_pending_types`: `const pending = String(row.PENDING_ASSETS || row.ASSET_TYPES || 'image_wide')`
  then `pending.map((type) => …)` — one item per entry, so a duplicate is two studio calls.
- `build_commit_files`: `pathOf(a) = 'docs/img/' + slug + '-' + a.type + '.' + a.ext` — the path is
  the type, so two assets of one type are two files at one path.

## Gate findings

- **The selector is the only place this needs fixing.** Since
  `fix-publish-commits-unrequested-assets` the set is derived once and read by
  `if_all_assets_approved`, `build_commit_files` and the selector's own `pending`, and
  `split_pending_types` reads the `PENDING_ASSETS` derived from it. One de-duplication covers all of
  them.
- **Order does not matter, but the hero rule still runs after.** The hero rule is a membership test,
  so `[...new Set(list)]` before or after it gives the same set; de-duplicating first keeps the
  emitted length honest.
- **A Set, not a filter on first occurrence.** `[...new Set(list)]` is the whole change; an
  index-of filter would be the same logic written longer.

## Decisions

- **D1 — de-duplicate in `requested()`**, before the hero rule.
- **D2 — no validation.** A duplicated type is not reported; the run proceeds as if it were listed
  once. The alternative is two commits at one path.

## Risks / Trade-offs

- **A bad row is absorbed silently.** Nothing tells the operator that `svg_wide,svg_wide` was
  collapsed. That is the deliberate direction — the sheet is not validated anywhere today, and
  failing the run over a typo in a field the graph can interpret would be worse than interpreting it.
- **A case for the article lane only.** The LinkedIn lane has no equivalent set derivation.

## Open Questions

- **Whether `ASSET_TYPES` should be validated rather than absorbed.** A row naming a type the
  registry does not declare is already handled (the studio reports it and the rest of the set
  proceeds); a row naming one twice is not. Worth deciding with the lane's own verification.

## Definition of done

- `openspec validate --all` passes with this change present.
- `agents/n8n`'s offline suite passes, and the new case fails without the change (a duplicated type
  surviving into `REQUESTED_ASSETS`).
- The export's two graph copies agree.
- The graph applied live with `--require-edge`, read back, and the export diffed against live.
