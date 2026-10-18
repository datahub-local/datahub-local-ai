# Proposal

## Why

`Article Content Writer` commits an asset row it was never asked for. `read_asset_rows_for_publish`
filters the `article_assets` table on `ENTRY_ID` alone — no type, no status — and
`build_commit_files` turns **every** row that read returns into a committed file, whether or not the
draft has a marker for its type. An entry that once requested `image` and now requests `image_wide`
still has its old `image` row, so the commit carries an extra blob under `docs/img/` that no marker
in the article references: an orphan image in the repository, and a commit that does not match the
asset set the run reported.

Found on 2026-10-17 while applying `add-content-writer-agent` 4.17, and worked around by deleting
the stale row by hand (`article_assets` held one APPROVED `image` row for entry `f2a53c10-…`). A
workaround that has to be repeated by hand on every entry whose requested set changes is not a fix.

The row's requested set is already computed, twice: `select_article_to_queue` derives it with the
hero rule (`requested(row)`, used for `PENDING_ASSETS` and the phase), and `if_all_assets_approved`
derives it again for the gate, with a comment saying the two must stay the same rule. The commit
path is the one consumer that derives nothing and takes whatever the table holds.

## What Changes

- `select_article_to_queue` emits the set it already computes, as `REQUESTED_ASSETS`, so the rule
  has one definition on every path a run can take.
- `if_all_assets_approved` reads that field instead of re-deriving the hero rule, which makes the
  coupling structural rather than a comment.
- `build_commit_files` filters the rows it commits to that set, and logs the types it dropped, so a
  stale row is visible in the run rather than silently committed or silently ignored.

Not changed: the asset path, the review flow, `read_asset_rows_for_publish` (it keeps filtering on
`ENTRY_ID` — the publish path owns its own reads and the filter belongs where the decision is
made), and the Data Table itself.

## Capabilities

### Modified Capabilities

- `content-writer`: the published commit SHALL carry the entry's requested asset set and nothing
  else.

## Impact

- **`agents/n8n/workflows/article_content_writer.workflow.json`**: three nodes
  (`select_article_to_queue` gains a field, `if_all_assets_approved` reads it, `build_commit_files`
  filters on it). Both graph copies. The entry point is `active: False` by design (6.6 of
  `add-content-writer-agent`), so the apply cannot interrupt a scheduled run.
- **Not changed**: `Article Creator`, the prompts, `Visual Studio`, the Data Table, and
  `datahub-local-core`.
- **Existing stale rows are not cleaned up by this change.** The filter stops a stale row from being
  committed; it does not delete it. Removing the leftovers is a separate, human decision.
