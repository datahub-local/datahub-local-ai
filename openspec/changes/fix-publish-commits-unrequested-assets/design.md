# Design

## Context

Read off the committed export; each claim is where it comes from.

- `article_content_writer.workflow.json`, node `read_asset_rows_for_publish`: a Data Table `get`
  whose only filter condition is `ENTRY_ID = $('select_article_to_queue').item.json.ENTRY_ID`.
- `build_commit_files`: `const assets = $('read_asset_rows_for_publish').all().map(…)`, then one
  `files.push({ PATH: pathOf(a), ASSET_TYPE: a.type, BINARY: true })` per entry. Nothing checks the
  type against what the entry asked for, so an extra row is an extra committed blob.
- `select_article_to_queue`: derives the requested set — `requested(row)`, which prepends
  `image_wide` when the row names neither raster — and uses it for `pending`, `PENDING_ASSETS` and
  the phase. It runs on every path: `switch_phase` branches on the `PHASE` this node emits, and the
  publish path still reads it (`build_commit_files` takes `CATEGORIES` from it).
- `if_all_assets_approved`: re-derives the same set as `effective`, with a comment that it "has to
  stay the same rule: a gate that prepends a type the selector did not ask for blocks every run
  forever". The coupling is by convention, and the commit path is not party to it at all.
- `PHASE === 'publish'` implies every requested type has a row whose `STATUS` is `APPROVED`: the
  selector computes `pending` as requested types that are missing or not `APPROVED`, and reaches
  `publish` only when `pending` is empty. So the publish path's rows are approved *for the requested
  types* — the type filter is the missing half, not a status filter.

## Gate findings

- **The filter belongs in the commit path, not in the read.** `read_asset_rows_for_publish` exists
  because a resumed publish run never executed the gate and cannot borrow its nodes
  (`test_the_publish_path_owns_its_own_reads`). A Data Table filter cannot express "in this
  entry's requested set" without a second derivation of the set inside the read node, which is
  the duplication being removed. The read stays as it is; the decision moves to the one node that
  knows what it is committing.
- **The rule already has one home; it needs to be read, not copied.** `select_article_to_queue`
  computes it and runs on every path, so emitting it as a field is what removes the gate's copy
  and gives the commit path a source. A third derivation inside `build_commit_files` would be the
  same defect one level down.
- **A status filter is not needed and would be worse than nothing.** `PHASE === 'publish'` already
  guarantees the requested types are approved, so a status condition would only ever drop an asset
  the gate had cleared — turning a correct publish into a commit missing a picture. Filtering by
  type is the whole fix.
- **A dropped row must be visible.** The failure this replaces was silent in both directions: the
  stale row was committed without a word, and deleting it by hand was the only way to notice. The
  commit node logs the types it left out, so the run says so.

## Decisions

- **D1 — `REQUESTED_ASSETS` is a comma-joined string on the selector's item**, beside
  `PENDING_ASSETS`, because that is the shape the flow already uses for `ASSET_TYPES` and what a
  reader of the node output sees.
- **D2 — `if_all_assets_approved` reads the field** rather than re-deriving it. Its blocking check
  keeps its own status logic; only the set comes from elsewhere.
- **D3 — `build_commit_files` filters its own read** by the field, and logs the dropped types.
- **D4 — no cleanup of existing rows.** The change stops the behaviour; deleting a leftover row is
  an operator decision about that entry.

## Risks / Trade-offs

- **A row the entry wants but the selector did not name is now dropped.** That is the point — the
  selector's set is the request. The risk is the opposite one: if the selector's hero rule ever
  diverges from what the draft's markers name, the commit would omit an asset. Both halves are
  asserted offline (`test_a_type_may_pin_the_form_it_means` is not involved; the new case covers the
  drop, and `test_the_hero_reference_replaces_the_marker_where_the_writer_put_it` covers the
  reference), and the gate already blocks a publish whose requested type is unapproved, so a
  divergence fails loudly rather than silently.
- **The export is the backup's output**, so the change is live only once applied with
  `scripts/apply_workflow_changes.py` and read back.

## Open Questions

- **Whether the leftovers should be swept.** `article_assets` may still hold rows for types no entry
  requests. They are now inert, but they are also state a reader will misread. A cleanup task wants
  its own change and an operator's judgement about which rows are stale.
- **Whether `PHASE`'s guarantee should be asserted rather than reasoned about.** The commit path
  depends on `publish` implying no pending requested asset. That is a property of
  `select_article_to_queue` alone today; an offline case pins it, but nothing in the graph enforces
  it if the phase rule changes.

## Definition of done

- `openspec validate --all` passes with this change present.
- `agents/n8n`'s offline suite passes, and the new case fails without the change (a stale row for an
  unrequested type is committed, and the field the commit filters on does not exist).
- The export's two graph copies agree.
- The graph is applied live with `--require-edge`, read back, and the export diffed against live.
