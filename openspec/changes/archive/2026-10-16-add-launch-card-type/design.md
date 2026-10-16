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
2. **A still is a frame of a render, not a directly authored file.**
   `session-lib.mjs` `transcodeArgs` derives `png` from `out.mp4`; `turnInstruction`
   for a non-svg, non-deck format tells the composer to write `index.html` and render
   `out.mp4`. **Which frame was a decision this change got wrong first, and the
   probe measured it:** see D1.
3. **`build_author_brief` had no still branch.** It branches on deck, then svg, then
   falls through to the animated branch, whose text is *"Render a WxH composition
   that runs about N seconds. Animate deliberately …"*. A png type added without a
   branch therefore yields a frame nobody chose.
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
   an animated clip, and the still branch ships no clip, so no rule is exempted and
   the brief needs no suppression of motion.

## Decisions

### D1 — `launch_card` is agent-authored, `static`, `png`, 1.91:1, sampled from the render's final frame

The composer is the only author that can letter exactly and draw an interface. The
frame is the reference's: 1.91:1, viewport 1280 -> 1280x670 (the reference is
1280x668; 1.91:1 is the declared ratio and the render rounds it).

**Which frame was wrong on the first attempt, and the probe is what found it.** The
first implementation took `out.mp4`'s *first* frame (`-frames:v 1`) and asked the brief
for a card complete at t=0 with nothing fading in. The type's first live run
(execution 13581, 2026-10-16) produced a **blank** png: 4,107 bytes, 8-bit RGB,
1280x670, **exactly one colour** (`#0c1016`) across 100% of the frame. The composer had
authored the composition correctly — 25 KB of HTML, a 7-second render at 210 frames,
the card reproduced faithfully — but with the entrance animation the framework's own
motion rules ask for, so t=0 is the empty page.

Re-measured against that same render, from the pi-render session itself:

| sample | bytes | distinct colours | non-background |
| --- | --- | --- | --- |
| frame 1 (`-frames:v 1`) | 4,107 | 1 | 0.0% |
| final frame (`-sseof -0.1`) | 251,865 | 12,257 | 54.5% |
| one second before the end (`-sseof -1`) | 246,944 | 11,709 | 54.7% |

So the fix is on the **sampler**, not in the brief: `transcodeArgs("png")` now takes the
final frame, and the brief states that the artifact is that frame, that entrances may
run, and that nothing may leave, dim or hide before the end. A brief that demands
"nothing animates in" is a request for the composer to disobey the motion grammar, and
that is not a contract worth relying on — the artifact must not depend on the composer's
timing at all. It is a one-line change in the adapter, so it applies to any future still
type rather than to `launch_card` alone.

**Closing verification, live, after the fix** (`bd70a54`, adapter re-pinned `e45e410`,
session rolled): execution **13588**, run `COMPLETE`, asset `RENDERED`, `image/png`,
1280x670, `S3_BYTES` **359,894**, and the decoded frame carries **12,307 distinct
colours** with its background covering only 8.2% of the pixels — against 4,107 bytes and
one colour before. The colour count is within 50 of the 12,257 measured on 13581's final
frame, which is what "the sampler takes the frame the measurement predicted" looks like.

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

- **[RESOLVED by measurement] the sampler, not the composer, decides whether the still
  is blank.** The first implementation relied on the composer composing a complete card
  at t=0 and it failed in production (D1). The final-frame sampler removes the
  dependency; the residual risk is a composition that *exits* its content at the end,
  which the brief forbids in one line and which the framework's motion rules do not ask
  for (they forbid ending frozen, not ending empty).
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
