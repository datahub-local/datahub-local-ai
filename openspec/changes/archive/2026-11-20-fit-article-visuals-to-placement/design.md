# Design

## Context

The article lane authors two kinds of visual today: the lead (`svg_wide`, animated, one
per article) and section figures (`figure`, static, one per `<!-- asset:figure -->`
marker, capped by `MAX_FIGURES`). Both are 16:9 and both are briefed from the draft text:
the lead from the whole article, a figure from its section. The commit writes
`docs/img/<slug>-<type>.svg` and the page references it. What was never stated anywhere is
the *page* the assets land in: a lead is read at full column width under the opening; a
figure is read inside a text column, at 80% width, between two paragraphs.

## Decisions

### D1 — Placement is part of the asset, not an afterthought

`derive_asset_plan` already derives the hero types and `figure_1…N`. Each item gains the
placement it fills (`lead` or `inline`) and, for a figure, the section it sits in. The
brief and the commit read that field rather than re-deriving it from the type name — the
2026-11-10 lesson that one derivation, read by every consumer, is what keeps a marker and
its committed file agreeing.

### D2 — The lead carries the thesis; a figure carries its section's mechanics

The convergence seen on row 4 is not a prompt-quality accident: the section "Three ways to
run the same framework" restates the article's thesis, so a figure briefed with that
section and a lead briefed with the draft were asked for the same picture. The figure
brief now names the difference — the lead image already carries the thesis, the figure
shows the section's flow, step or comparison row, never a second overview. Where a section
genuinely is the thesis restated, the writer is told to place no figure there: the marker
is the writer's choice, and a figure that duplicates the lead earns nothing.

### D3 — One motion per page

The lead is animated (`svg_wide`); figures are static (`figure`). Two animated assets on
one page compete for attention and neither reads as the lead. The registry already
declares this through each type's render kind; the requirement states it so a future type
cannot quietly break it. A page may carry no figure at all — that is a normal article.

### D4 — The publish chain is per-item

The live failure (execution 17163) came from a chain built when one asset was the norm:
`asset_signed_url` read `$input.first()` and a global node, collapsing N assets to one, and
`collect_tree_entries`' count assertion caught it as "1 blobs for 2 assets". The chain is
made per-item with identity carried on each item (no global-node lookups), and the
assertion stays: it is the regression detector for this class.

### D5 — A figure composes for the width it is rendered at

Inline figures render at 80% of the text column; the existing frame (16:9) is right, but
the authoring brief must say the composition is read at that size — one idea, labels that
survive the shrink, no code text as imagery. This is a brief rule, not a new type: the
registry's frame already carries the aspect.

## Risks

- **Duplication returns whenever a section restates the thesis.** The rule names the
  failure and tells the writer to drop the marker; the reviewer sees both visuals in the
  same run, so a duplicate is caught at the approval, not after publish.
- **Two consumers re-deriving placement.** Mitigated by D1: the plan item is the one copy.
- **The chain fix touches live publishing.** It is applied after the export diff is shown,
  with the harness proving 2-in/2-out before the apply, as the 2026-11-18 lessons require.

## Open questions

- Should the committed figure markup carry an explicit width (`<img width="80%">`) or rely
  on the site's figure CSS? Leaning the site's CSS with the existing 80% rule, so the
  article markdown stays plain.
- Should the lead ever be static when the article argues rather than announces? Not now —
  one animated lead per page, regardless of shape.

## Definition of done

- A two-asset article commits both files in one commit, each at its own path.
- The figure's brief carries its section and the no-second-thesis rule; the lead's brief
  carries the draft.
- The published page shows the lead full-width under the opening and the figure inline at
  the text column's width, alt text from the section heading.
- `openspec validate --all` and the adapter suite are green.
