# Design

## Context

See [proposal.md](proposal.md) — Why. The facts that shape the approach, read
from the exports and datasets:

- **The hook is stored as prose.** `content_queue` has no `HOOK` column; the judge's
  hook lives only in the `Hook: X.` prefix on `EXTRA_PROMPT`. `build_expire_rows`
  parses it back out to choose a TTL. `image_motifs.json` parses it again to pick
  an image treatment. Two readers, one string.
- **Three hook lists exist.** `curator_judge.md` (6), `linked_in_post_creator`'s
  `set_variety_directives` (4 always + 2 conditional), and
  `image_motifs.json`'s `hooks` (6 + default). `image_motifs.json`'s own comment
  claims the list lives in the curator, which is stale.
- **The post's hook is random.** `set_variety_directives` does `pick(hooks)`,
  `pick(format)`, `pick(closing)`. The judge's `angle` reaches the generator only
  as prose inside `EXTRA_PROMPT`.
- **Media is hand-set and single.** `POST_MEDIA` is read but never written here;
  one asset per post; the media branch is `convert_animation`/`convert_image` on
  the same publish node.
- **The composer already sequences scenes.** `build_author_brief` sends the
  content, form, style and the type's frame; the composer plans a storyboard
  (form, style, scenes) and authors it in one turn. `animation_linkedin` is 8 fps,
  48 frames, 776 px, 9 s, inside LinkedIn's GIF cap. A multi-scene clip already
  works — what is missing is a *decision* that a given article is a sequence.
- **`FORCE` names the forms.** `auto | diagram | story | data | poster | image`,
  validated in `normalize_input`. `datasets/diagram_types.json` (14 archetypes) is
  dead — only `test_brand.py` reads it.

## Goals / Non-Goals

**Goals:**

- One hook list, one source, consumed by classifier, generator and media.
- The hook and the visual intent decided once, from the article, and carried in the
  queue as columns.
- The post's media selected from that intent, not from a human cell.
- A roundup/state-of article rendered as a sequence, one item per scene, with no
  new media kind.

**Non-Goals:**

- A carousel / multi-image post (a separate change; the media branch assumes one
  asset).
- Reviving `diagram_types.json` as a per-row diagram picker; the composer still
  owns its form within the `FORCE` the row names.
- A LinkedIn engagement read-back loop; hook variety is a judgement, not a bandit.
- Changing the six `FORCE` form values.

## Decisions

### D1. One registry, and nothing copies it

`datasets/hook_types.json` is the only list. The judge prompt receives the hook
ids as a rendered `{{ HOOKS }}` var built from the registry, rather than repeating
them in prose; `set_variety_directives` and the sharing media branch read the same
file. A test fails if any hook id appears in more than one dataset, the same shape
as `test_brand.py`.

*Alternatives considered:* expand each of the three lists in place and add a
sync test — rejected; it keeps three copies and a test whose only job is to catch
them drifting, which the one file removes. Put the list only in the judge prompt —
rejected; the generator and media need it too, and a prompt is not a lookup table.

### D2. The hook set is intent-shaped, 15–20 hooks

Grouped by what the article gives the author, not by tone:

| Group | Hooks | Default visual |
| --- | --- | --- |
| Argument | `CONTRARIAN`, `MISCONCEPTION`, `TRADE_OFF`, `PREDICTION` | `diagram` / `poster` |
| Evidence | `HARD_NUMBER`, `BENCHMARK`, `COST` | `data`, motion |
| News | `NEWS_REACTION`, `RELEASE`, `VULNERABILITY` | `poster` / `image` |
| Reference | `ROUNDUP`, `COMPARISON`, `LANDSCAPE`, `CHECKLIST`, `ARCHITECTURE` | `data` / `diagram` |
| Narrative | `WAR_STORY`, `POSTMORTEM`, `MIGRATION`, `LESSONS` | `story` / `diagram` |

Each entry carries `when` (eligibility), `opening` (the shape the post's first lines
take; format, length and closing stay the generator's own variety), and `visual`
(`form`, `motion`, `scenes`). `ROUNDUP` is the dremio
case: `form: data`, `motion: true`, `scenes: <item count>` — one trend per scene.

### D3. The judge decides once; the row carries the result

The judge already reads the full article. It gains two outputs beside `hook`:
`visual` (`form`, `motion`, `scenes`). `admit_to_backlog` writes `HOOK`,
`VISUAL_FORM`, `ANIMATED`, `SCENES` as columns. `EXTRA_PROMPT` keeps the angle for
the generator but is no longer the hook's storage.

*Alternatives considered:* a second classifier at publish time — rejected; it is a
second model read of the same article and re-introduces the disagreement this
change removes. Derive the visual from the hook alone in code — rejected for
roundups, where `scenes` is a fact only the reader has.

### D4. The creator stops re-picking the hook

`set_variety_directives` reads `HOOK` from the row and maps it to the registry's
`treatment`; format, length and closing stay randomly picked (the answer chosen in
discussion — rhythm still varies post to post). `classify_content` (is_news /
has_hard_number) is retired: eligibility is the judge's job now.

*Alternatives considered:* make all four deterministic — rejected; it trades a
templated feed for a deterministic one, and hook diversity already comes from the
judge. Keep `classify_content` as a guard — rejected; it gates a hook the judge
already chose with knowledge of the article.

### D5. Sharing drives the studio from the row; POST_MEDIA is an override

The media branch passes `ASSET_TYPES` from `ANIMATED` (`image` vs
`animation_linkedin`) and `FORCE` from `VISUAL_FORM`, and forwards `SCENES` into
the brief. A row with a manual `POST_MEDIA` keeps today's behaviour, so existing
hand-set rows and `MANUAL`-origin rows are unchanged.

### D6. A roundup is a multi-scene clip, not a carousel

`scenes` reaches the composer through the brief; the composer authors one item per
scene with the page indicator convention (`add-composer-self-review` D6) and
renders the existing `animation_linkedin`. This needs no new type, no new publish
path and stays inside the GIF cap. A true carousel is deferred.

*Alternatives considered:* N images attached to one post — rejected as a separate
change; the publish node selects one asset, and multi-asset publishing is a larger
surface than the visual-decision fix this change is about.

### D7. The curator self-heals the queue it wrote before the columns existed

A row admitted before the columns existed has no visual intent, so it would publish with
the writer choosing the shape and no motion. The curator therefore re-judges queued `AUTO`
rows whose `HOOK` is empty, a bounded number per run (`select_unclassified_queue` → a loop
that fetches the article, runs the same judge prompt and writes the four columns), so the
backlog is backfilled over a few days rather than in one spike of calls. Once every queued
row is classified the selector returns nothing and the branch is a no-op.

*Alternatives considered:* a deterministic backfill from the `Hook: X.` prefix — rejected
because all six legacy hooks map 1:1 into the registry, so it is exact for the hook but
cannot upgrade a coarse label to a new hook (a state-of article labelled `CONTRARIAN`
never becomes the `ROUNDUP` sequence), which is the point of re-judging. A one-off backfill
workflow — rejected in favour of the self-heal, so a row that slips through, or a column
cleared by hand, is repaired on the next run.

## Risks / Trade-offs

- **A longer hook list can confuse a small model.** → The registry's `when` field
  and the existing "when in doubt, answer false" posture bound the choice; the
  judge prompt still names the ids it may return.
- **A new column set is a schema change to a live sheet.** → Columns are added by
  the append mapping, which is additive; a missing column degrades to empty, and
  the sharing branch falls back to the still-image path, which is the current
  behaviour.
- **The judge may set `scenes` poorly.** → `scenes` is bounded (a small integer,
  capped at the GIF frame budget's practical scene count) and a missing value
  falls back to the composer's own storyboard.
- **Retiring `classify_content` touches a live workflow.** → It is a node removal;
  applied with `--require-edge` and published with a deactivate/activate cycle,
  then the export is diffed against live.
- **Two prompt files must move together** (`curator_judge.md` for the choice, the
  registry for the list). → The registry is the list; the prompt names no hook ids
  of its own, so there is nothing to drift.

## Migration Plan

1. Add `datasets/hook_types.json`; commit (the judge and generators read `main`).
2. `curator_judge.md`: emit registry hook + visual intent; the workflow injects
   `{{ HOOKS }}`.
3. `content_feed_curator`: `parse_judge` validates against the registry;
   `admit_to_backlog`/`build_queue_rows` add the four columns. Apply live.
4. `linked_in_post_creator`: consume the row's hook; retire `classify_content`.
   Apply live.
5. `linked_in_post_sharing`: media branch reads the intent; `POST_MEDIA` override
   kept. Apply live.
6. `visual_studio`: brief accepts `SCENES`. Apply live.
7. Manual acceptance: run one roundup (the state-of article) end to end and confirm
   a multi-scene GIF, and one article-hook row and confirm the post opens on the
   classified hook with the matching `FORCE`.

Rollback: revert the three workflow exports and the prompt; the sheet columns can
stay (they degrade to empty) and the still-image path is the pre-change default.

## Open Questions

- Does `HOOK` warrant retiring the `Hook: X.` prefix entirely, or keep it so
  `build_expire_rows` needs no change? Preference: move the reader to the column
  and drop the prefix, so there is one representation.
- Should `SCENES` be an integer or a list of scene titles? Preference: an integer
  now (the composer names the scenes); a list is a later enrichment if the composer
  keeps inventing the wrong ones.
- Whether `image_motifs.json`'s `hooks` moves into the registry's `visual` block or
  stays a separate image-treatment map read from the registry hooks. Preference:
  move it, so the registry is the one hook-to-visual source.
