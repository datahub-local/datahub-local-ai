# Proposal

## Why

A type named twice in a row's `ASSET_TYPES` is requested twice. `requested()` in
`select_article_to_queue` splits the field, trims it and filters blanks, then applies the hero rule —
it never de-duplicates, so `svg_wide,svg_wide` yields `['image_wide', 'svg_wide', 'svg_wide']` and
both `REQUESTED_ASSETS` and `PENDING_ASSETS` carry the type twice. Visible in execution 14018 on
2026-10-18, whose test row held exactly that value: `PENDING_ASSETS: "image_wide,svg_wide,svg_wide"`.

Downstream, `split_pending_types` fans the pending set out one studio call per entry, so the type is
authored twice; two asset rows result; and `build_commit_files` pushes two files at the same
`docs/img/<slug>-svg_wide.svg` path. The run never reached that far, so the collision has not been
observed — it is read off the graph. The studio call, at least, is certain: the splitter maps over
the pending string.

The set has one definition since `fix-publish-commits-unrequested-assets` — the selector derives it
and the publish gate and commit path read it. That is the right place to fix this: de-duplicating
there covers every consumer at once instead of adding a guard to each.

## What Changes

- `select_article_to_queue`'s `requested()` de-duplicates the row's `ASSET_TYPES` before applying the
  hero rule, so `REQUESTED_ASSETS`, `PENDING_ASSETS` and every consumer of them name each type once.

Not changed: `split_pending_types`, `build_commit_files`, the studio, and the sheet. A row that lists
a type twice is still a typo — this makes it harmless rather than telling anyone.

## Capabilities

### Modified Capabilities

- `content-writer`: the requested asset set names each type once.

## Impact

- **`agents/n8n/workflows/article_content_writer.workflow.json`**: one expression in
  `select_article_to_queue`. Both graph copies.
- Live apply needed; the entry point is `active: False`.
- **Not changed**: everything else, including `Article Creator` and the LinkedIn lane.
