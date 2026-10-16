# Proposal

## Why

The studio can produce a lettered visual only as something that **moves**: every
agent-authored type is a clip, a self-contained animated SVG, or an HTML deck. The
one still raster in the registry, `image`, is authored by the Gemini image model
and is barred by its own prompt from the two things a launch graphic is made of:
`prompts/visual_raster.md` rule 3 forbids interface chrome and any screenshot, and
rule 2 forbids rewording or adding text, so the headline, the feature chips and the
product window cannot be produced faithfully. There is also no wide frame: the
registry offers 4:5 and 16:9, and the platform's announcement/link-card ratio
(1.91:1) is expressible by no type at all.

The observed gap is concrete: a **product launch card** — brand lockup, one status
badge, a headline and its supporting line, the feature set as short chips, a window
of the product's own interface, and one call to action. It is the graphic you post
when the subject is a thing we ship, and today the studio cannot make one.

## What Changes

- Add a `launch_card` type to `agents/n8n/datasets/visual_types.json`: authored by
  the composer agent, rendered static, `png`, 1.91:1. It is the first
  agent-authored **still raster**, and the first wide frame.
- Add a `launch` form to the single committed vocabulary,
  `agents/n8n/prompts/visual_forms.md`, so the card's parts are defined once and
  reusable. A form is the right home: the registry declares only the output frame.
- Teach the brief to compose a still: `build_author_brief` gains a `png` branch
  asking for the whole card in the composition's **first frame**, because the still
  is produced as that frame of the render (`agents/adapters/pi-render/session-lib.mjs`,
  `transcodeArgs`: `-frames:v 1`). Without the branch the artifact is an arbitrary
  first frame of an entrance animation.
- Extend the `FORCE` enum in `visual_studio.workflow.json` and the two `FORMS`
  arrays in `content_feed_curator.workflow.json` with the new form, and the
  vocabulary comment in `datasets/hook_types.json` — one vocabulary in four places,
  which `scripts/test_hook_registry.py` already asserts.
- Record when to use the type, and why the alternatives were rejected, in this
  change and in `AGENTS.md`.

**No new form is wired to a hook.** The hook registry classifies *third-party*
articles; a launch card announces *our own* product, so it is chosen by `FORCE`
(or by the composer under `auto`), not by a hook default.

## Non-goals

- **No paged carousel.** A multi-page LinkedIn document post (PDF) is a new medium:
  a new format, a new authoring path and a new publish path in
  `LinkedIn Post Sharing`, whose installed node cannot upload documents. Reviewed
  and deferred; see `design.md`.
- **No animated 1.91:1 type.** 1.91:1 is the platform's image/link-card ratio, not
  a feed-video ratio; an animated launch card at 4:5 or 16:9 is already expressible.
- **No change to the image (Gemini) path**, no new MCP server, no cluster change.

## Capabilities

### Modified Capabilities

- `visual-studio`: the type registry declares a seventh type, a still raster, and
  the system gains a defined way to produce one (the composition's first frame).

## Impact

- **`agents/n8n/datasets/visual_types.json`** — one new type entry.
- **`agents/n8n/prompts/visual_forms.md`** — one new form line. Live on push.
- **`agents/n8n/datasets/hook_types.json`** — the vocabulary comment only. Live on
  push.
- **`agents/n8n/workflows/visual_studio.workflow.json`** — the `FORCE` enum and the
  `build_author_brief` still branch, in both copies of the graph. **Not live until
  applied** with `scripts/apply_workflow_changes.py --apply` (approval required).
- **`agents/n8n/workflows/content_feed_curator.workflow.json`** — the two `FORMS`
  arrays, in both copies. Same apply gate.
- **Tests** — `scripts/test_visual_studio_registry.py` (the declared-id list and the
  still-type invariants) and `scripts/test_visual_studio_graph.py` (the still
  branch). `scripts/test_hook_registry.py` already gates the four-place vocabulary
  and needs no change.
- **`agents/adapters/pi-render`** — **no change**. The still rides the existing
  `png` transcode.
