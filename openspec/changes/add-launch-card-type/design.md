# Design

## Context

A launch card is the graphic that announces a thing we ship. The reference that
started this change is 1280x668 — the platform's 1.91:1 announcement/link-card
ratio — and carries, top to bottom: a brand lockup, a status badge, a headline and
its supporting line, the feature set as short pills, a window of the product's own
interface with the orchestrating agent selected in it, and one call to action.

Read literally, that is a **still, lettered, interface-bearing, wide** frame. The
registry has none of those three properties at once.

## Gate findings

Verified by reading the code, not inferred:

1. **No still raster is agent-authored.** `author` is `image` or `agent`; the
   `image` type is the only raster and its author is Gemini.
   `prompts/visual_raster.md` rule 3 — *"Never draw interface chrome, a dashboard or
   a screenshot in either mode"* — and rule 2 — *"Use only names and numbers that
   appear in the source text; never invent a number, reword or add text"* — forbid
   exactly what a launch card is made of.
2. **A still is frame 1 of a render, not a directly authored file.**
   `session-lib.mjs` `transcodeArgs` → `png: ["-y","-i","out.mp4","-frames:v","1","out.png"]`.
   `turnInstruction` for a non-svg, non-deck format tells the composer to write
   `index.html` and render `out.mp4`. So a png artifact is `out.mp4`'s first frame,
   and the composer must compose the finished card **at t=0**.
3. **`build_author_brief` has no still branch.** It branches on deck, then svg,
   then falls through to the animated branch, whose text is *"Render a WxH
   composition that runs about N seconds. Animate deliberately …"*. A png type
   added without a branch therefore yields a random first frame.
4. **`render: "static"` does not mean "still".** `image` (Gemini raster) and `svg`
   (a self-contained *animated* SVG authored directly, never rendered) both declare
   it. The honest signal for the brief is the **format**, which it already branches
   on (`format === 'svg'`).
5. **The form vocabulary is asserted in four places.**
   `test_hook_registry.py::test_the_form_vocabulary_is_one_file` compares
   `prompts/visual_forms.md` against the `FORCES` enum in `visual_studio`
   (2 copies) and the two `FORMS` arrays in `content_feed_curator` (4 copies).
   Adding a form to one and not the others is silently clamped, and the test fails.
6. **Motion rules and a still do not conflict.** `visual_motion_rules.md` forbids a
   *frozen final frame in an animated clip* — "Nothing fully stops". A still is not
   an animated clip, and nothing requires the composition to freeze: it may drift
   after frame 1, which is simply not sampled. So the brief states completeness at
   frame 1 and no rule is exempted.

## Decisions

### D1 — `launch_card` is agent-authored, `static`, `png`, 1.91:1

The composer is the only author that can letter exactly and draw an interface. The
frame is the reference's: 1.91:1, viewport 1280 → 1280x670 (the reference is
1280x668; 1.91:1 is the declared ratio and the render rounds it).

The brief's new branch states the mechanism plainly: *everything is composed in the
first frame; nothing fades, slides or types its way in, because the artifact is that
frame.* That is the one non-obvious instruction this type needs, and it is the
reason the change touches the graph at all.

### D2 — the card's parts live in a new `launch` form

The registry declares how a type is authored and its frame — never a layout. The
parts of the card are a composition shape, which is what the vocabulary file is for,
and it is already fetched into the brief and injected into the judge prompt. `poster`
is the closest existing form and is explicitly *"a single type-led card carrying one
idea and no data series"* — the interface window is what makes a launch card not a
poster, and `ui` is *"show the interface … with callouts on what changed"*, which is
a report on a change, not an announcement. Hence a third form rather than a
reinterpretation of either.

### D3 — no hook defaults to `launch`

`hook_types.json` classifies an article *someone else* wrote; `launch_card` announces
a thing *we* ship. No hook's `when` describes our own release, so no hook declares
the form, and the type is reached by `FORCE=launch` (or by the composer's own choice
under `auto`, since the vocabulary is in every brief). A hook added later that
defaults to it would be a claim about our product, which the curator is not in a
position to make.

### D4 — multi-slide: reviewed, and split in two

Asked directly. Three shapes were considered:

| shape | verdict |
| --- | --- |
| **Timed slides** (the card's items play in sequence, mp4/gif) | **Already expressible, nothing to add.** `SCENES` on an animated type already asks for one item per scene with an opening title scene (`build_author_brief`, and the `ROUNDUP` hook uses it). A launch card that must be multi-slide belongs on `animation_linkedin_video` with `SCENES`, not on a still. |
| **Paged carousel** (LinkedIn document post, N pages as a PDF) | **Real, and a separate change.** Not a property of this type: it needs a new `pdf` format, an authoring path the composer cannot take (it writes HTML/CSS, not a PDF — the image has Chrome, so an HTML→PDF print is the plausible route), and a new publish path (`LinkedIn Post Sharing`'s installed node cannot upload documents, as its node cannot upload video either). Deferred, not rejected. |
| **Static multi-slide** | Does not exist. A still is one frame by definition, which is why the still brief says so. |

So `launch_card` stays one frame, and the multi-slide appetite is served by the
scene plan already in place.

## Alternatives rejected

- **Animated mp4 at 1.91:1** — cheapest option (a registry entry and nothing else),
  and rejected: 1.91:1 is the image/link-card ratio; a feed video at that ratio is
  off-spec, and an animated launch card at 4:5 or 16:9 is already expressible.
- **Gemini at 1.91:1 with a launch raster device** — a registry entry, a hook
  `image` device and a change to `visual_raster.md`. Rejected: rules 2 and 3 exist
  precisely because the model cannot hold exact lettering or draw a real interface,
  and the whole value of the reference is that its text and its window are exact.
- **Reusing `poster` or `ui` as the form** — no committed definition of the card
  would exist, so "when to use it" would live only in a caller's `EXTRA_PROMPT`.
- **A frozen-hold flag on the type** — the registry test forbids `holdSeconds` on an
  animated type and the brief needs no flag: the format already selects the branch.

## Risks

- **[UNVERIFIED] the composer obeys "compose it in the first frame".** The
  mechanism is verified by reading `transcodeArgs`; that a model renders a complete
  card at t=0 is not. Guards: the brief states it as the artifact's definition, the
  vocabulary's `launch` line lists the parts, and a card that misses it is
  diagnosable from the run's `STORYBOARD` report. A probe run is task 5.3.
- **`-frames:v 1` takes t=0 exactly.** An entrance that starts at t=0 is the failure
  mode; a composition that starts complete cannot hit it. If a probe shows otherwise,
  the fix is in the brief, not in the adapter.
- **A still costs the studio its "no holds" property?** No: the property is about a
  clip's final frame, and this type ships no clip.

## Open questions

- Does the paged carousel (D4) earn its own change? It is the format LinkedIn
  rewards most for a launch, but it is a new medium end to end.

## Definition of done

- The registry declares `launch_card`; the vocabulary defines `launch`; the four
  enum copies agree; the brief composes a still; `openspec validate --all` passes;
  `uv run pytest` in `agents/n8n/scripts` passes; the two workflow exports are
  applied to live and the applied result re-read and diffed.
