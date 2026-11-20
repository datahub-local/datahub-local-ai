# Design

## Context

The lane is type-keyed end to end: `ASSET_TYPES` is a list of registry ids, the writer leaves one
marker per id, `parse_article` rejects `x2`/`x0`/`not requested`, `split_pending_types` emits one
studio call per pending type, `article_assets` is keyed by `(ENTRY_ID, ASSET_TYPE)`, and
`build_commit_files` writes `<slug>-<type>.<ext>`. Every one of those constraints is useful for the
hero and wrong for section figures, whose number is a property of the draft.

Two facts fix the design space: the selector runs before the draft exists, and the studio authors
one artifact per requested type.

## Decisions

### D1 — Figures are positional slots, not ids

The writer places `<!-- asset:figure -->` with no index. `parse_article` assigns `figure_1…N` in
document order; `build_commit_files` replaces the k-th occurrence with `figure_<k>`. An index in the
marker would be a number the model must count and renumber, which is exactly the `x2`/`x0` failure
the marker check exists to prevent.

### D2 — The writer decides the count; the row caps it

The draft is the only place that knows whether five diagrams are warranted. The row carries
`MAX_FIGURES` (blank = 3); the total, hero included, is capped at 5. The cap is enforced in code and
repeated in the prompt, and the instruction is "only where a diagram carries a step, a comparison or
a flow the prose cannot" — a count with no subject is a padded article.

### D3 — The approved draft is the asset plan in the assets/publish phases

`select_article_to_queue` cannot know the figures before a draft exists. So it keeps deciding the
**phase** from the sheet and the asset rows, but the **requested set** in the assets and publish
phases is derived from the stored draft: the declared hero plus `figure_1…figure_N` from its markers.
In the draft phase the set is only the hero, which is all the drafting prompt may assume. One
function derives it, and `split_pending_types`, the publish gate and `build_commit_files` read it.

### D4 — A figure slot is a synthetic row type

Rows are keyed by `(ENTRY_ID, ASSET_TYPE)`, so slots become `figure_1…figure_N`. That keeps the
upsert key, the per-asset review and the `<slug>-<type>.<ext>` path unchanged. The studio is asked
for the registry type `figure` (one call per slot); the entry point names the returned artifact by
its slot, so the registry gains one id, not N.

### D5 — A figure is briefed with its section

The slot carries the heading and the text of its section: the content between the previous and the
next `##` heading, bounded (1,500 characters) with the heading first. The studio's `CONTENT` stays
the whole draft for tone, and `EXTRA_PROMPT` carries the section with the instruction to illustrate
only that. Without this, five figures are five takes on the same opening.

### D6 — Commit maps by position, alt from the heading

The k-th figure marker becomes `![<section heading> - figure](</img/<slug>-figure-<k>.svg>)`, at the
marker's place in the body. The hero keeps its current path and its hero placement rule.

### D7 — A regenerated article retires its figure rows

A new draft may place a different number of figures, so every `figure_*` row for the entry is
retired (`CANCELLED`) when the article is approved again — the assets phase runs after that
approval — and the new plan is authored from scratch. The hero keeps its existing approval, as it
does today when an article is re-drafted — it is the same subject and has its own review.

### D8 — The raster is still a type, not a path

`image_wide` remains declared and a row that names it still gets it. The default hero stays
`svg_wide`, and the figure type is composer-authored, so the default lane spends no image-model
call.

## Risks

- **Cost.** Each figure is one composer turn plus one Slack approval; a 5-image article is five
  studio runs. The cap and the placement rule are the controls; the design does not parallelise.
- **Count drift.** A human can approve the article, then reject it for text changes; the figure
  plan changes with the draft, and `figure_*` rows are retired and re-authored. Accepted: a figure
  approved for a section that no longer exists is worse.
- **Section extraction.** The heading split can be wrong in a draft with a code fence containing a
  `##` line. Mitigation: split on `^## ` lines outside fences, the same shape `build_commit_files`
  already walks for marker placement.
- **Publish gate coupling.** The gate reads `REQUESTED_ASSETS`; a missed derivation in one consumer
  would either block a run forever or publish an article whose figure marker was replaced by
  nothing. The plan derivation is one function, and its consumers are asserted by the graph's edges.
- **Marker count is bounded by the draft, not by `ASSET_TYPES`.** A row that declares
  `svg_wide,launch_card` still gets the card, while figures are additional. That is intentional;
  `figure` is not a valid `ASSET_TYPES` value.

## Open questions

- Default cap: 3 (total 4) or 4 (total 5)? Start at 3, since the ceiling matters more than the
  maximum.
- Whether a figure may be placed before the first section (a second lead image). No: the hero owns
  that position; a figure before the first heading is rejected as a misplaced slot.

## Definition of done

- A draft with zero, two and five figure markers (five against a cap of 3) reports the right
  `FIGURES` count, and only the last is rejected.
- The assets phase authors exactly the slots in the stored draft, in document order, each with its
  own `figure_<k>` row and Slack review.
- The commit replaces the k-th marker with `figure_<k>.svg` and nothing is left as a marker.
- A row that names `image_wide` still gets the raster; the default hero is `svg_wide`.
- `openspec validate --all` passes and the adapter tests still pass.
