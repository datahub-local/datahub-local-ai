# Design

## Context

Visual Studio authors an asset in one composer turn: the brief goes to the `pi-render` session, which
plans a storyboard, writes a HyperFrames composition (or, for an `svg` type, a standalone SVG) and
renders it. The workflow never sees the markup. So a new *look* is expressible entirely as a form —
a definition in `prompts/visual_forms.md`, which the brief carries verbatim — and a new *deliverable*
as a registry entry.

The composer's sandbox fixes the technical space:

- **No network at render time.** Only `gsap.min.js` is vendored (`agents/adapters/pi-render/vendor/`),
  so `rough.js` and Excalidraw's own renderer cannot be loaded from a CDN inside a composition.
- **GSAP here is the core build.** `DrawSVGPlugin` is a Club plugin and is not in `gsap.min.js`, so a
  stroke cannot be drawn with `drawSVG`; `stroke-dasharray`/`stroke-dashoffset` on the timeline is the
  portable equivalent.
- **The brand is one document** (`brand.json`): palette and typefaces are Space Grotesk and JetBrains
  Mono, and the spec forbids the composer introducing a typeface the brand does not define. Only
  DejaVu is installed as a fallback in the image; Excalifont/Virgil is not present.
- **The motion rules already name the technique**: "Seed imperfection where a handmade feel is
  wanted, with an index-derived offset — never a clock and never unseeded randomness."

## Decisions

### D1 — Sketch is a form, and a type pins it

The look composes with the existing render paths (video and `svg`), so it belongs in the vocabulary,
not in a branch. Two types pin it, because choosing a type is choosing its shape (`svg_wide` already
does this with `diagram`), and because the automated lanes can only name types: the article lane by
`ASSET_TYPES`, the feed by `VISUAL_FORM` reaching `FORCE`.

### D2 — Two deliverables, both wide

`sketch` is an mp4 at 16:9 (12 s, 30 fps, 360 frames, viewport 1280): a clip for a player or a post.
`sketch_svg` is a self-contained animated SVG at 16:9 with the same 12 s: the article body's medium,
where text must stay crisp at any width and the file stays small. They are separate ids rather than
one type with two formats because every existing type has exactly one output format, and the graph
routes on it.

No 4:5 variant: the feed lane publishes `animation_linkedin_video` and takes only the *form* from the
row, so a 4:5 sketch is reachable today via `FORCE`/`VISUAL_FORM` on a feed type. A type is only
needed where the medium differs.

### D3 — No new dependency: the wobble is authored

`rough.js` would roughen a path for us and `DrawSVGPlugin` would draw it on, but adding either is an
image change (vendor + Dockerfile copy + lockfile) for something the composer can do with primitives
it has:

- the wobble is a **seeded, index-derived offset** on an authored polyline or quadratic path — the
  motion rules' own rule for a handmade feel, deterministic and reproducible from the seed;
- the draw-in is `stroke-dasharray` = path length and `stroke-dashoffset` animated to 0, staggered by
  reading order, which is exactly what creates the "sketching itself" read.

The alternative — roughening with a blur or displacement filter — is rejected: `authoring.md` warns
that full-frame filter effects are the most expensive thing the screenshot-capture render can be
asked to do, and the visual review would judge a blurred drawing.

### D4 — One drawing, not scenes

A sketch assembles into a single diagram, so both types declare no `secondsPerScene` and no
`introScene`: a caller's `SCENES` must not stretch it into a sequence, and a title card would break
the illusion that one drawing is completing. This is the `tiles` precedent, for the same reason.

### D5 — Lettering stays the brand's

The form describes strokes; it does not name a typeface. A sketch keeps Space Grotesk lettering in
the brand palette, so `Brand.json` stays the only copy of the look and the spec's "no typeface the
brand does not define" requirement holds. The hand-drawn read comes from the geometry, which is the
part a model can control deterministically.

## Risks

- **A type is inert until the dataset is pushed.** The registry is fetched at run time by
  `download_registry` through `DownloadTemplate` from `BACKUP_GITHUB_REPO_*` on `main`, so the graph
  enum can be applied live and the studio still answers `unknown asset type: sketch` (measured
  run 16947, 2026-11-17). The form file has the same property. Verification therefore needs the
  push, not only the apply.
- **The composer may read "sketch" as "rough font"** and reach for a comic face it does not have,
  falling back to DejaVu. The definition therefore names the device (wobble, draw-on, seeded offset)
  and forbids the substitutes (shading, gradient, photographic fill), which is the same shape that
  made `tiles` land.
- **A 12 s clip with many paths** is a heavier composition than `tiles`. The composer's own
  `--low-memory-mode` render and the review stills are unchanged; if the first live render is slow,
  the fix is fewer nodes, not a second type.
- **The SVG file can grow** with per-path wobble. The `svg_wide`/`figure` types already ship authored
  SVGs, so the ceiling is a review finding, not a new failure mode.
- **An unseeded wobble would render differently every turn**, making a correction turn unable to
  preserve what the critic approved. The seeded-offset rule already covers it; the render's
  `STORYBOARD` names the seed so a reviewer can check.

## Open questions

- **The mp4 and the svg took different shapes.** Run 16955 opened on a title scene and sequenced
  five scenes; run 16965 is one frame. D4 asked for one drawing and got it only in the SVG, because
  the type declares no `introScene` and absence is not a prohibition. If the mp4 should be one
  drawing too, the form definition has to say so (and forbid a title card) — the registry has no
  field for "never a title scene".
- **The mp4's draw-on is slow against its scene length.** At 7.5 s of 12 the frame held roughly 5%
  of its ink, mid-way through scene 4. Options measured nothing yet: a longer
  `durationSeconds` (18), a `SCENES` cap on the type, or a per-scene stagger rule in the form.
  [UNVERIFIED] which of the three fixes it, and whether an unattended viewer reads a half-drawn
  scene as broken or as drawing.
- **A static svg has no encoder, so its self-declared length is unenforced.** Run 16965's sidecar
  says `duration: 15` against the type's 12 s; nothing conforms an SVG, and the still capture uses
  the declared 12 s. Harmless here (the settled frame is the last one), but it means the container
  guarantee documented for `mp4` does not exist for `svg`.
- [UNVERIFIED] Whether the article lane should prefer `sketch_svg` for a step-by-step section. That
  is the `figure` slot's brief (`add-variable-figure-slots`), not this change; this change only makes
  the type available to a caller that asks for it.

## Definition of done

- `prompts/visual_forms.md` carries the `sketch` definition and the three graph enums agree with it.
- `visual_types.json` declares both types and every field the registry's neighbours declare.
- `openspec validate --all` passes, and `docs/agent/n8n.md` names both types and `sketch` in `FORCE`.
- After the owner approves the apply: the studio's `normalize_input` accepts `FORCE=sketch` live and
  refuses an unknown value naming the enum; the curator's two nodes accept it.
- One live run per type: `STATUS: COMPLETE`, `ffprobe` shows 16:9 at 12 s for the mp4, and the
  artifact's `STORYBOARD` names the sketch form and a seed.
