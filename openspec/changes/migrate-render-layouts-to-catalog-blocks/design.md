# Design

## Context

The render service (`agents/n8n/render/`) takes a typed content spec and authors a
composition itself. Today that authoring is five hand-written modules
(`src/layouts/{stats,flow,timeline,comparison,bars}.mjs`) that each build an HTML
string, inline CSS and a GSAP timeline, over a shared shell in `src/scene.mjs`.
363 lines we own.

HyperFrames 0.8.123 — the engine those modules drive — ships a curated catalog of
data/graphics blocks. Verified against the pinned package and registry:

- `hyperframes catalog --json` lists blocks with `type`, tags, declared
  `dimensions` and `duration`.
- `hyperframes add <name>` writes the block into `compositions/` and prints an
  include snippet: `<div data-composition-id="…" data-composition-src="…">`. A
  block is installed as a separate composition and **referenced**, not pasted.
- A block declares its own typed variables in
  `data-composition-variables` (`string|number|color`, with `default`/`min`/`max`),
  reads them back through `window.__hyperframes.getVariables()` falling back to
  `window.__hfVariables`, and applies a literal fallback per variable so it still
  renders when the runtime is absent.
- The registry resolves to
  `https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry`, and
  `hyperframes.lock.json` records a content hash per installed file.
- A scaffolded project's `index.html` loads GSAP from jsDelivr — a CDN reference
  we must not inherit, because the service renders offline.

So a block is a typed, versioned, data-driven template — the same shape as our
layout modules, but better designed and authored upstream.

## Goals / Non-Goals

**Goals:**

- Add catalog data blocks **alongside** the hand-written layout templates, adopting
  a layout's block wherever the catalog has one. Removing every layout is not
  reachable (see the catalog findings): no adoptable block expresses `flow` or
  `timeline`, so those keep their modules.
- Make the adopted catalog blocks part of the layout library, vendored into the
  image so renders stay offline and reproducible.
- Keep the spec-only HTTP contract and the "model output is data" boundary exact.
- Let a spec address a block's declared variables, so one block serves more than
  one idea.

**Non-Goals:**

- Accepting caller-supplied markup or script, in any form, from any trust level.
- Replacing the shell (title, rule, footer, background) — only the content region
  moves to blocks.
- Changing the n8n workflow's call shape, the MCP tool, or the type registry's
  contract.
- Reaching upstream's full catalog at once; this lands one block per layout.

## Decisions

### D1. Vendor blocks at image-build time, keyed by content hash

`hyperframes add` is run during `docker build` (or by a committed vendoring script
run before it) against the pinned `0.8.123` registry, writing into
`agents/n8n/render/vendor/blocks/<name>/`. The script records the upstream hash so a
re-vendor is reviewable, and the vendored files are committed so the image build is
offline and reproducible.

*Alternatives considered:* fetch the registry at render time — rejected; the
container has no network by design and an upstream change would silently alter
output. Vendor the whole catalog — rejected; it bloats the image and pulls blocks
we do not use, each with its own art direction to reconcile.

### D2. The adapter maps spec fields onto declared variables

One module (`src/blocks/adapter.mjs`) loads a vendored block, reads its
`data-composition-variables`, and produces the include markup plus the variable
payload handed to the runtime. Mapping is per block, held in a small table beside
the registry entry, because each block's variables differ (`bar-chart-race` wants
`series`/`periods`/`accent`; a `number-wheel` wants one value).

A field the block does not declare is dropped, not injected — the block's own
`default` applies. A value is coerced to the declared type or rejected.

*Alternatives considered:* one universal mapping over our `blocks[]` — rejected;
blocks do not share a data shape, so a universal rule would need a translation
layer per block anyway, with worse errors. Pass our whole spec as vars — rejected;
undeclared keys would leak into blocks that iterate their variable list.

**Verified integration constraints (2026-10-04, rendered in-container):**

- A block included by `data-composition-src` is loaded as a **sub-composition**,
  and its relative asset paths resolve against **the block's own location**, not
  the host's. So the vendored block and `vendor/gsap.min.js` must be written into
  the render directory preserving that relative layout — rewriting the CDN
  reference to `./vendor/gsap.min.js` only works if the block file sits one level
  beside `vendor/`. The render step currently writes `index.html` + `vendor/`, so
  the adapter's output must place blocks accordingly or inline the script.
- The **host** composition must register `window.__timelines["main"]`. Our shell
  already does; without it the renderer waits 45 s per attempt and reports
  `sub_timeline_readiness_timeout`. A host that intentionally drives no GSAP
  timeline can set `data-no-timeline` instead.
- `bar-chart-race` rendered correctly at 960×540 / 4 s / 96 frames from a
  minimal host, confirming the include shape and the variable read-back work.

**Per-instance overrides go on the include element, not on a global (verified
2026-10-04).** HyperFrames documents two different attributes with different jobs:

- `data-composition-variables` on the sub-composition's own root — a JSON **array
  of declarations** (`{id, type, label, default}`), i.e. the schema.
- `data-variable-values` on the **host element that embeds it** — a JSON **object
  keyed by variable id**, i.e. this mount's overrides.

Precedence is defaults → host `data-variable-values` → CLI `--variables`. The
adapter must therefore put the mapped payload on the include markup it generates,
not in `window.__hfVariables`. Setting the global looks correct (the runtime does
read `window.__hfVariables` via `so()`) and silently does nothing for a sub-comp,
because the block's own script resolves against the host element's attribute. This
was found by rendering the block and watching its sample data survive both a nested
and a flat global payload; only the attribute form changed the output. Confirmed in
the render: the block drew our title, our series and our suffix.

### D3. Adopt variable-declaring blocks only; restyle lightly

Verified against two blocks (2026-10-04): **only variable-declaring blocks are
adopted.** A block that declares `data-composition-variables` renders its own
designed output from our spec, which is the capability we are buying. A **component
does not** — `animated-bar-chart` is markup + CSS with a hardcoded sample and no
declared variables, so binding a spec to it means substituting its content, which is
hand-written markup, i.e. the thing this change exists to remove. Components are
therefore not adopted.

Restyling is a **light touch**: drive the block's declared colour variables (accent,
and any colour the block exposes), and leave the block's own design otherwise
intact. A clash that cannot be fixed through a declared variable is accepted rather
than patched, so vendored files stay close to upstream and a re-vendor stays a clean
diff.

*Alternatives considered:* adopt components and rewrite their content — rejected;
it reintroduces our markup. Full restyle of every block to the house theme —
considered and rejected by the user; the per-block cost and upstream divergence are
not worth it, and accepting each block's design keeps the vendored file honest.

*Alternatives considered:* use blocks unstyled — rejected; output stops looking
like one product. Fork each block wholesale — rejected; it discards upstream fixes
and hides what we changed.

### D4. Note the duplicate trust consequence explicitly

Blocks are ours: they are installed in the image, never requested. The service keeps
rejecting `html`/`markup`/`script`/`css` keys, and the adapter never accepts a block
body or a block name from the caller. A caller selects a **layout name** from a
closed set the registry defines — it cannot name an arbitrary file.

*Alternatives considered:* expose block bodies to trusted callers — rejected in
`add-hyperframes-render-service` D2 and unchanged here.

### D5. Migrate one block per layout, behind the existing API

`layout` keeps accepting today's names; the adapter adds block ids as they land.
`src/layouts/<name>.mjs` is deleted only when a block replaces that layout's role
and its render smoke passes. The 19 composition tests stay green throughout; each
migration adds an adapter test and a render smoke for the new block.

*Alternatives considered:* delete all five at once — rejected; it breaks the spec
contract and the tests in one step with no intermediate check.

## Risks / Trade-offs

- **Blocks are art-directed for their own use, not ours.** → Drive declared colour
  variables first and keep edits as a reviewable patch (D3); accept that some
  blocks need more editing than others and curate which ones we adopt.
- **Vendored blocks drift from upstream.** → Record the upstream hash at vendor
  time so drift is visible and re-vendoring is a deliberate diff.
- **Spec vocabulary becomes less uniform.** A map block wants geography, a race
  wants a time series. → `prompts/visual_spec.md` names which fields each block
  expects, and the adapter drops undeclared fields instead of failing.
- **The image grows.** → Vendor only the blocks adopted; a block is tens of KB.
- **A block may reference a CDN** (the scaffolded project does). → The vendoring
  step strips or vendors any remote script reference; the offline render test (no
  network) is the gate.
- **A block's own JS runs in the render browser.** It is upstream code we have
  reviewed and pinned, not caller input — the same posture as the vendored GSAP.

## Migration Plan

1. Add the vendoring step and the adapter; `bar-chart-race` is the first adopted
   block. Both paths render; `bars` keeps working.
2. Drive the block's declared colour variables (the light touch of D3); verify
   offline and against the shell.
3. Adopt and verify a block for each layout the catalog can back (`comparison` via
   `comparison-split`; `stats` via `chart-story`/`count-up`), deleting only that
   layout module once its block's render smoke passes.
4. Keep the layout modules no block can replace (`flow`, `timeline`) and update
   `prompts/visual_spec.md` to describe the block vocabulary alongside them.

Rollback is per step: a block that does not pass its render smoke is dropped and
its layout keeps rendering. Nothing else in the service changes.

## Open Questions

- ~~Which block replaces `flow`?~~ **Answered by the catalog findings:** none does;
  `flow` keeps its hand-written layout, and so does `timeline`.
- ~~Whether the restyle should live as patched vendored files or as an override
  stylesheet applied by the adapter.~~ **Answered by D3:** neither — a light touch
  drives declared colour variables and otherwise accepts the block's design.

## Catalog findings (2026-10-04)

The catalog has **164 blocks**. Whether a block can back a layout was tested by
installing a spread and reading each one's `data-composition-variables`, not by
their names or tags — the first pass guessed wrongly from descriptions alone.

Of a 17-block sample, **7 declare variables**: `before-after-wipe`, `chart-story`,
`comparison-split`, `conic-progress-ring`, `count-up`, `number-wheel`,
`oscilloscope-trace`. The rest are **components** or content-hardcoded blocks
(`flowchart`, `flowchart-vertical`, `hw-pipeline`, `data-chart`, `mk-line-graph`,
`apple-money-count`, `mk-progress-stat`) and are **not adoptable** under D3.

Fit against the four remaining layouts:

| Layout | Candidate | Note |
| ------ | --------- | ---- |
| `comparison` | `comparison-split` | `split`/`orientation`/`labelA`/`labelB`. Direct fit. |
| `stats` | `chart-story` | `type: bars`, `data`, `labels`, `unit`, `emphasize` — ranked figures with exact supplied values. |
| `stats` | `count-up` | one figure per mount (`start`/`end`/`prefix`/`suffix`) — one block per number, so several mounts are needed for a list. |
| `flow` | **none found** | `flowchart`/`hw-pipeline` are not variable-driven. `constellation-hub` (nodes + connectors) is a **component**. No adoptable block expresses connected, ordered nodes. |
| `timeline` | **none found** | `beat-timeline` is a component; the timeline-shaped blocks are orchestration primitives, not a labelled sequence. |

Consequences for the plan:

- `comparison` and `stats` **can** migrate.
- `flow` and `timeline` **cannot**, from this catalog, so `src/layouts/flow.mjs` and
  `src/layouts/timeline.mjs` stay. The change's end state is therefore **"catalog
  data blocks added alongside the layouts"** for those two, not "layouts removed" —
  which is a narrower outcome than the proposal assumed and should be reflected in
  it.
- Two adapter gaps surfaced: variables typed **`enum`** (a declared option set,
  e.g. `accent: 'green'`, `type: 'bars'`) and **`boolean`** are not handled by
  `coerce`, which currently treats an unknown type as a plain string. Enum values
  must be checked against the declared options, and the runtime already warns
  (`runtime_unknown_enum_value`) when an undeclared one is passed.
