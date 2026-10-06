# Design

## Context

See `proposal.md` — Why, and `specs/visual-brand/spec.md` for the requirements.
What shapes the approach is the current state of the surfaces:

- **The brand already has one canonical home**, in another repository:
  `datahub-local/datahub-local` — `mkdocs.yml` (typefaces: Space Grotesk,
  JetBrains Mono) and `stylesheets/extra.css` (a header literally named
  `MOSS BRAND PALETTE`: `#0E1116` shell, `#F4F2EC` cream, moss ramp
  `#5E8A3F`/`#7FAF5A`/`#A3CF7A`, plus a light scheme and surface idioms). That
  file is the source; nothing here reads it yet.
- **The render service does not look like the site at all.** `src/scene.mjs`
  hard-codes `background: #0a0d12`, `ink: #f5f7fa`, `font-family: Inter, "DejaVu
  Sans", …`; `templates/infographic.html` hard-codes `#0b0d10`/`#f5f7fa` and
  `"DejaVu Sans"`. The image installs only `fonts-dejavu-core`. Neither brand
  typeface is present.
- **The datasets each carry their own colour vocabulary.** `image_motifs.json`
  and `diagram_color_presets.json` (light/dark/neutral/vibrant/monochrome/
  brand-blue/warm/cool) and `diagram_visual_styles.json` describe palettes a
  model may choose from; none is the brand, and `brand-color` is not even a brand
  colour.
- **Prompts leave colour to the model.** `visual_spec.md` asks for "one 6-digit
  hex color, dark-themed"; `linkedin_image_prompt.md` builds art direction from
  `image_motifs.json`; `diagram_generator.md` chooses among the preset datasets.
- **The agent path is the one flow with a free-form brief** (`build_author_brief`
  in `visual_studio.workflow.json`), which today says nothing about a brand.

The mechanism to inject shared data into a prompt already exists and is used for
exactly this kind of vocabulary: `image_motifs.json` is fetched and a Code node
splices it into `visual_spec`/raster placeholders. The brand follows that pattern.

## Goals / Non-Goals

**Goals:**

- One committed token document that is the only place a brand colour or typeface
  is written, with a mechanical test that fails when a surface spells its own.
- A repeatable extraction from the site repo that is a no-op when upstream is
  unchanged.
- The render service, its templates and its layouts rendered from the tokens,
  offline, with the brand typefaces vendored.
- Prompts that describe the brand instead of delegating it to the model.
- The legacy diagram/diagram datasets reconciled so a model choosing among them
  still lands in the brand.

**Non-Goals:**

- A design-token system with a build pipeline (Style Dictionary, `@theme`): the
  token set is a dozen roles and two typefaces, and the repo's convention is a
  committed JSON read at use, not a code generator.
- Re-rendering the site or touching its CSS.
- Deciding which existing asset samples are re-rendered and committed beyond the
  one acceptance render (samples are the render change's concern).

## Decisions

### D1. The token document is `agents/n8n/datasets/brand.json`, read directly

`datasets/` is where the prompt-injected vocabularies already live and where
`DownloadTemplate` can fetch from. The brand joins them. The render service
imports it directly (`import brand from "../../datasets/brand.json" with { type:
"json" }` — Node 22 supports import attributes), so there is no generated copy to
drift. The Dockerfile COPYs `datasets/brand.json` next to the render source.

Shape — named **roles**, not raw hex at the point of use, so a surface asks for
`ink`, not `#F4F2EC`:

```
{
  "typography": { "text": "Space Grotesk", "code": "JetBrains Mono" },
  "shape": { "radiusCard": "0.75rem", "radiusPanel": "1rem", "radiusPill": "99rem",
             "hairlineAlpha": 0.1, "shadow": "none" },
  "schemes": {
    "dark":  { "shell": "#0E1116", "surface": "...", "surfaceRaised": "...",
               "ink": "#F4F2EC", "inkMuted": "...", "accent": "#7FAF5A",
               "accentStrong": "#A3CF7A", "accentDeep": "#5E8A3F",
               "codeBg": "#0a1008", "codeInk": "#c8e6a8" },
    "light": { "shell": "#F4F2EC", "ink": "#0E1116", "accent": "#7FAF5A",
               "accentStrong": "#5E8A3F", "accentDeep": "#3d5c28", ... }
  },
  "defaultScheme": "dark",
  "photographic": { "artDirection": "dark studio, matte subjects, soft moss light, ..." }
}
```

*Alternatives considered.* A committed `brand.css` for the render service plus a
JSON for prompts — rejected: two copies of one palette, and the failure mode is
invisible. A code generator emitting CSS/JS from JSON — rejected: a second
artifact checked against the first, which is the "committed generated copy"
problem the repository already avoids in `agents/sympozium`. Reading the site over
HTTP at render time — rejected: the render is offline by contract.

### D2. Vendor the two typefaces into the render image

`Space Grotesk` and `JetBrains Mono` are OFL and shipped as files under
`agents/n8n/render/vendor/fonts/`, loaded by the shell with `@font-face` and a
`local()`/`url()` pair, exactly as GSAP is vendored. The Dockerfile copies them
and no `@import url(fonts.googleapis.com…)` ever reaches a composition, so the
offline render stays offline. JetBrains Mono is needed only where a figure or a
code-like token is shown; the shell loads it for `.mono`.

*Alternatives considered.* Keep `DejaVu Sans` and only swap colours — rejected:
type is half the identity the user asked for, and the site's headings are
Space Grotesk. Load from Google Fonts — rejected: the render has no network.

### D3. Caller accents are mapped to the ramp, never rendered free-form

A caller (or a frozen `SPEC_JSON`) may still carry an `accent`. The studio maps
it onto the scheme's accent roles — nearest by hue/lightness, or the scheme
default when it is not a colour — so an out-of-brand value is never rendered as
given and a legacy spec still renders. The authoring prompt, by contrast, offers
only the brand roles, so a freshly authored spec needs no mapping.

*Alternatives considered.* Reject an out-of-brand accent — rejected: it would
break frozen specs and the `SPEC_JSON` contract for no visual benefit. Silently
ignore the accent and always use the default — rejected: it discards a legitimate
choice between the ramp's roles.

### D4. Two kinds are declared in the registry, not inferred per surface

`visual_types.json` gains a `brandKind` per type, defaulting `diagrammatic`;
`hero_static` is `photographic`. The authoring stage routes the prompt by kind:
diagrammatic types get the UI token block, the hero gets the photographic art
direction. This keeps the registry the single place a type is described, which is
the capability the registry already exists for.

*Alternatives considered.* Infer from `render: raster|animated|…` — rejected: the
mapping is not one-to-one (a future raster diagram exists) and inference is the
kind of hidden rule the registry exists to make explicit.

### D5. Prompts receive the brand as a resolved `{{ BRAND }}` block

The workflow builds a short, literal brand block from `brand.json` (palette roles
and the two typefaces) and passes it as a template variable, as
`image_motifs.json` is spliced today. The prompt states the brand; it does not
dump the JSON. The raster prompt receives the `photographic.artDirection` string
instead of the palette.

*Alternatives considered.* Hardcode the palette in each prompt — rejected: the
drift this change exists to remove. Download `brand.json` into the prompt
verbatim — rejected: it would put a schema where the policy wants a short,
literal instruction.

### D6. A test enforces the single source mechanically

A test walks the generator surfaces — `agents/n8n/render/src/**`,
`agents/n8n/templates/*`, the four prompts, and `visual_types.json` — and fails
on a hex literal or a `font-family` that is not a value in `brand.json`, with an
allow-list for tests, `vendor/` (upstream blocks and fonts), and `icons.json`.
This is the mechanism that keeps D1 true over time; the same shape as the
`bodega` `persist_docs` test that fails a blank description. It is why the
legacy datasets must be reconciled rather than left beside the brand.

*Alternatives considered.* Review-only — rejected: the repository already records
that an unenforced rule drifts (the `toolsAllow` comments, the n8n error-workflow
rule). A test is the enforcement.

### D7. Reconcile the existing datasets rather than add a brand beside them

`diagram_color_presets.json` collapses to the brand's two schemes (the other six
are not the brand and a model must not be offered them); `diagram_visual_styles.json`
keeps its composition names but states that the palette is always the brand's;
`image_motifs.json` gains the photographic art-direction tokens.

*Alternatives considered.* Leave the datasets and only brand the new path —
rejected: the legacy `image_content_generator` flow would keep producing
off-brand assets, which is exactly the split the proposal is closing.

### D8. The extraction is a documented step against a sibling checkout

`agents/n8n/scripts/extract_brand.py` reads a checkout of
`datahub-local/datahub-local` pointed at by `BRAND_REPO` (the pattern
`workflows/dbt/semantic/compile.py` uses for `MCP_REPO`), parses `mkdocs.yml` for
the typefaces and `stylesheets/extra.css` for the `MOSS BRAND PALETTE` block, and
writes `brand.json` deterministically (sorted keys, fixed indent, a trailing
newline). A missing checkout is a readable error, not an `ImportError`-shaped
crash. It is run by a human at sync time; nothing runs it in CI.

*Alternatives considered.* Parse the published `extra.css` over HTTP — rejected:
the sync would then depend on what is deployed rather than what is committed, and
the two diverge during a deploy.

## Risks / Trade-offs

**[Changing the shell changes every existing asset's bytes.]** → The render smoke
asserts structure, duration and frame count, not colours, so it stays green; the
committed demo samples are re-rendered as part of acceptance. Any external
consumer that pinned an asset by hash is not a thing here.

**[Vendored fonts grow the image and carry a licence.]** → Space Grotesk and
JetBrains Mono are OFL-1.1; their `OFL.txt` ships beside them under
`vendor/fonts/`, the same posture as that of the vendored GSAP and blocks.

**[The legacy `image_content_generator` flow is not exercised by CI and may be
dormant.]** → Its datasets are reconciled by review; its live behaviour is
recorded as manually verified or `[UNVERIFIED]` in the tasks rather than assumed.
This does not block the new path.

**[A frozen `SPEC_JSON` carrying an old accent renders as the mapped ramp role,
which may differ from what was approved.]** → Accepted: the requirement is that
no out-of-brand colour is rendered; the mapping is deterministic and testable, and
the asset is reviewed again on re-render.

**[The enforcement test's allow-list can hide a real literal.]** → The allow-list
is three entries and is asserted by the test itself (a stray entry fails); a new
surface that needs a literal must justify it in the list, which is the review
point.

## Migration Plan

1. Land `brand.json`, the extractor and the enforcement test first; at this point
   every existing surface fails the test, which is the work list.
2. Brand the render service (shell, layouts, block adapter defaults) and vendor
   the fonts; offline render acceptance.
3. Brand the templates (`infographic.html`, `infographic.svg`) and thread
   `{{ BRAND }}` plus `brandKind` through the workflow and registry.
4. Update the four prompts and the raster art direction.
5. Reconcile the legacy datasets.
6. Carry the brand into the `pi-render` brief.
7. Acceptance: one offline render per kind, one live raster image, and the
   enforcement test green.

Rollback is per step: removing the enforcement test restores the previous
surfaces untouched, and each surface is independently revertible.

## Open Questions

- Whether motion timing (the site's ~0.18–0.35 s ease transitions) should be a
  brand token or stay per-layout. Deferrable: it changes no requirement and can
  be added to `brand.json` later without touching a task.
- The exact wording of the photographic art direction is a judgement to settle
  during implementation against one real hero render; the requirement is only
  that it exists and is carried to the generator.
