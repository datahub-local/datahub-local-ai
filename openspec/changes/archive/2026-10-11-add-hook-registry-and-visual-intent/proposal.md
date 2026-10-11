# Proposal

## Why

The planned post's **hook** is decided twice, and the second decision is a dice
roll. The curator's judge reads the full article and assigns one of six hooks
(`curator_judge.md`); `admit_to_backlog` writes it as the `Hook: X.` prefix on
`EXTRA_PROMPT` and it is read back for the TTL and, separately, to pick the image
composition (`datasets/image_motifs.json` → `hooks`). But `LinkedIn Post Creator`
never reads it: `classify_content` reduces the article to two booleans and
`set_variety_directives` **randomly picks** the hook, format, length and closing
from those. The hook that shapes the post text and the hook that shapes the image
can therefore disagree, and neither comes from the one pass that read the article.

The **media** decision is not made by the system at all. `POST_MEDIA` is read by
`linked_in_post_sharing` (`['ANIMATED','AGENT'].includes(...)`) but is written by
no workflow here and is not one of the `content_queue` columns `build_queue_rows`
appends — it is a hand-set sheet column. The visual *form* (`FORCE` =
`auto|diagram|story|data|poster|image`) is never set per row, so the composer
always gets `auto`. A "State of the Open Lakehouse" roundup — whose obvious
treatment is a sequence of trends, one per scene — falls through to whatever the
composer guesses.

Six hooks are too few to express what an article *is*; the judge labels a survey,
a benchmark and an architecture post with the same coarse value, so the post and
the visual cannot follow the intent.

## What Changes

- **One hook registry.** A new `agents/n8n/datasets/hook_types.json` is the single
  list (15–20 hooks). Each entry declares when it is eligible, the **post
  treatment** (opening shape, format hint, closing) and a **default visual intent**
  (`form`, `motion`, `scenes`). The registry is read by the judge, the post
  creator and the sharing media branch — replacing the three lists that exist
  today (`curator_judge.md`'s enum, `linked_in_post_creator`'s array,
  `image_motifs.json`'s `hooks`).
- **The judge classifies once.** `curator_judge.md` selects a `hook` from the
  registry and a `visual` intent in the same call that reads the article. The
  intent may override the registry default when the content warrants it (a roundup
  sets `scenes` to its item count).
- **The queue carries the decision as columns, not prose.** `admit_to_backlog`
  writes `HOOK`, `VISUAL_FORM`, `ANIMATED` and `SCENES` beside the existing fields,
  so nothing scrapes the hook back out of `EXTRA_PROMPT`.
- **The creator stops re-picking the hook.** `set_variety_directives` reads `HOOK`
  from the row and maps it through the registry; format, length and closing stay
  randomized so the feed does not read as templated. `classify_content` is retired.
- **Sharing drives Visual Studio from the row.** The media branch passes
  `ASSET_TYPES` (from `ANIMATED`) and `FORCE` (from `VISUAL_FORM`) and, for a
  roundup, the `SCENES` plan. A manually set `POST_MEDIA` remains a per-row
  override.
- **A list becomes readable:** a roundup or state-of article is authored as a
  multi-scene composition — one item per scene — in the existing
  `animation_linkedin` type. No new media kind and no carousel.

## Capabilities

### New Capabilities

- `post-hook-taxonomy`: a single declarative registry of post hooks and their
  default visual intent, shared by the classifier, the post generator and the
  media branch.

### Modified Capabilities

- `linkedin-post-publishing`: the queue carries the classified hook and visual
  intent as columns; the draft's hook is the one classified from the article; the
  post's media is selected from the row's intent rather than a hand-set column.
- `visual-studio`: an authoring request may carry a scene plan, and the brief
  passes it so a multi-scene composition renders one item per scene.

## Impact

- `agents/n8n/datasets/hook_types.json` — new registry (data change).
- `agents/n8n/prompts/curator_judge.md` — emits the registry hook and a visual
  intent; the hook list is injected from the registry, not copied into the prompt.
- `agents/n8n/workflows/content_feed_curator.workflow.json` — `parse_judge`
  validates against the registry; `admit_to_backlog` and `build_queue_rows` carry
  the new columns.
- `agents/n8n/workflows/linked_in_post_creator.workflow.json` —
  `set_variety_directives` consumes the row's hook; `classify_content` retired.
- `agents/n8n/workflows/linked_in_post_sharing.workflow.json` — the media branch
  keys on the row's intent and passes `FORCE`/`SCENES`.
- `agents/n8n/workflows/visual_studio.workflow.json` — the authoring brief accepts
  an optional scene plan.
- `agents/n8n/scripts/` — a registry-drift test, and updates to the existing
  structural tests.
- No cluster, Sympozium, MCP or Superset change. Prompts and datasets are read
  from GitHub `main`, so those halves are live on push; the three workflow edits
  are live only after `scripts/apply_workflow_changes.py`.
