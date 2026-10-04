# Proposal

## Why

The render service authors every composition from five hand-written HTML/CSS/GSAP
layout modules (`src/layouts/*.mjs`, 363 lines we own and maintain). HyperFrames —
the engine those modules drive — ships a curated catalog of blocks
(`bar-chart-race`, `data-chart`, `world-map`, `count-up`, …) that we partly
re-implement by hand, less well. A **variable-declaring** catalog block renders its
own designed output from values we pass, so adopting one adds capability without a
line of our markup.

**Re-scoped 2026-10-04 after inspecting the catalog.** The original goal was to
remove every hand-written layout. That is unreachable: of a 17-block sample, only 7
declare variables, and against the five layouts they cover only **`comparison`**
(`comparison-split`) and **`stats`** (`chart-story`, `count-up`). No adoptable block
expresses `flow` (connected, ordered nodes) or `timeline` — the candidates are
components or content-hardcoded blocks. So the honest aim is:

> **add catalog data blocks alongside the hand-written layouts** — not remove them.

The end state is a service with more capability, still carrying the layouts that no
block can replace. Bespoke, one-off visuals are a **different** path, covered by
`add-agent-authored-compositions`; this change is about repeatable data shapes a
typed spec should keep answering deterministically.


## What Changes

- **Add a catalog-block adapter** that maps the content spec onto a vendored
  HyperFrames catalog block's declared variables, held per block because each
  block's variables differ.
- **Vendor variable-declaring blocks into the image.** Blocks are fetched from the
  pinned registry at image-build time and committed under
  `agents/n8n/render/vendor/blocks/`, so a render stays offline and reproducible. A
  remote script reference is rewritten to the vendored copy; any other remote
  resource is a hard failure.
- **Adopt only blocks that declare variables.** A catalog component (markup + CSS
  with hardcoded content) would have to have its content rewritten to carry our
  data, which is the hand-written markup this change exists to remove.
- **Restyle lightly**: drive a block's declared colour variables from the spec and
  otherwise leave its own design intact, so vendored files stay close to upstream.
- **Widen the `layout` vocabulary** to the adopted block ids, alongside the existing
  layout names; no layout name changes meaning.
- **Keep the hand-written layouts that no block can replace** (`flow`, `timeline`,
  and the rest until a block is adopted). This is an addition, not a migration away
  from them.
- **Keep the trust boundary unchanged.** The service still accepts a typed spec and
  rejects caller markup. Catalog blocks are ours, shipped in the image; no caller
  HTML is ever accepted or executed.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `visual-studio`: the render service's composition source changes from
  service-authored layout templates to vendored catalog blocks. The requirement
  that the service authors compositions deterministically from versioned templates
  is refined: templates become vendored blocks, still versioned, still offline, and
  still never caller-supplied markup.

## Impact

- `agents/n8n/render/` — new `src/blocks/` adapter and `vendor/blocks/`; `src/layouts/`
  shrinks to nothing as blocks land; `src/spec.mjs` layout vocabulary widens.
- `agents/n8n/render/Dockerfile` — vendoring step; image grows by the vendored blocks.
- `agents/n8n/prompts/visual_spec.md` — the authoring model must know which spec
  fields each block expects.
- `agents/n8n/render/test/` — composition tests shift from our markup to adapter
  tests plus a render smoke per block; the offline-only rule is unchanged.
- No change to the HTTP API, the MCP tool, the n8n workflow's call shape, or the
  NetworkPolicy. `add-hyperframes-render-service`'s deployment stays valid.
