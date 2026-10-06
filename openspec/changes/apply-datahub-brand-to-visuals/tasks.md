# Tasks

## 1. Brand token source

- [ ] 1.1 Add `agents/n8n/datasets/brand.json` with the `typography`, `shape`, `schemes` (dark and light), `defaultScheme` and `photographic` sections and named roles as in design D1; verify it parses as JSON, contains no `{{ }}` placeholder anywhere (it is fetched through `DownloadTemplate`), and names only values read from the site repo's `MOSS BRAND PALETTE` and `mkdocs.yml`
- [ ] 1.2 Add `agents/n8n/scripts/extract_brand.py` reading a `datahub-local/datahub-local` checkout from `BRAND_REPO` (a readable error when absent), parsing the typefaces from `mkdocs.yml` and the palette from `stylesheets/extra.css`, writing `brand.json` deterministically (sorted keys, fixed indent, trailing newline); verify a re-run against an unchanged checkout produces a byte-identical file and no diff
- [ ] 1.3 Add the enforcement test (`agents/n8n/scripts/test_brand.py` or the repo's existing n8n test entry point) that walks `agents/n8n/render/src/**`, `agents/n8n/templates/*`, the four prompts and `visual_types.json` and fails on a hex literal or a `font-family` absent from `brand.json`, with the allow-list from design D6; verify it fails today on `scene.mjs` and `infographic.html` and that a stray new literal fails it
- [ ] 1.4 Add the `brand.json` fetch to `DownloadTemplate`'s known templates and document the sync step in `agents/n8n/README.md`; verify the file is retrievable by template name and the documented command reproduces `brand.json`

## 2. Render service

- [ ] 2.1 Vendor Space Grotesk and JetBrains Mono under `agents/n8n/render/vendor/fonts/` with their `OFL.txt`, add them to the Dockerfile and reference them from the shell with `@font-face`; verify an in-container render under the deployment's security context shows the two faces and reaches no network (`docker run --network none`) — build gate is CI-only
- [ ] 2.2 Make `src/scene.mjs` read the shell from `brand.json` (scheme surface, ink, accent roles, typefaces, radii) instead of the current `#0a0d12`/`#f5f7fa`/`Inter`; verify an offline render is produced and the enforcement test passes on `scene.mjs`
- [ ] 2.3 Make `src/layouts/*.mjs` and `src/blocks/adapter.mjs` take their colours from the brand roles and default the accent to `schemes[defaultScheme].accent`; verify every layout renders offline and no layout file holds a hex literal outside `brand.json`
- [ ] 2.4 Map a caller-supplied `accent` onto the scheme's accent roles (nearest, or the scheme default) so an out-of-brand value is never rendered as given (design D3); verify a spec with a non-brand accent renders in a brand accent and a spec with a brand accent keeps it
- [ ] 2.5 Extend the render tests: a per-scheme structural test asserting the produced composition uses the scheme's shell/ink/accent, and a mapping test for 2.4; verify the suite fails if a role is swapped for a literal

## 3. Templates and registry

- [ ] 3.1 Rebrand `agents/n8n/templates/infographic.html` and `infographic.svg` to the brand tokens (`#0E1116`/`#F4F2EC`/moss, Space Grotesk/JetBrains Mono) by threading the tokens rather than hard-coding; verify the enforcement test passes on both and an animated render still assembles with the declared duration
- [ ] 3.2 Add `brandKind` to every type in `agents/n8n/datasets/visual_types.json` (`diagrammatic` default, `photographic` for `hero_static`) and route the authoring stage by it; verify an unknown `brandKind` fails loudly and every existing type field is unchanged
- [ ] 3.3 Thread a resolved `{{ BRAND }}` block from `brand.json` into the spec-authoring prompt and the `photographic.artDirection` into the raster prompt; verify the rendered prompt text carries the brand block and the raster prompt carries the art direction (offline check of the built prompt)

## 4. Prompts

- [ ] 4.1 Update `agents/n8n/prompts/visual_spec.md` to state the brand instead of asking for an arbitrary hex, per the repository's short-literal prompt policy; verify it names only tokens present in `brand.json` and keeps its existing output-key contract
- [ ] 4.2 Update `agents/n8n/prompts/visual_raster.md` and `linkedin_image_prompt.md` to carry the photographic art direction from `brand.json`; verify neither names a UI hex token and both still resolve through `DownloadTemplate`
- [ ] 4.3 Update `agents/n8n/prompts/diagram_generator.md` so its palette comes from the brand's two schemes rather than the preset datasets; verify the enforcement test passes and the prompt still follows the AI prompt policy (short, literal, no copied schema)

## 5. Legacy datasets

- [ ] 5.1 Collapse `agents/n8n/datasets/diagram_color_presets.json` to the brand's two schemes and update `diagram_visual_styles.json` to state the palette is always the brand's; verify `image_content_generator.workflow.json` still parses and its nodes resolve the reconciled ids — live flow behaviour is `[UNVERIFIED]` (not exercised by CI; record if a manual run is done)
- [ ] 5.2 Add the photographic art-direction tokens to `agents/n8n/datasets/image_motifs.json` without introducing a placeholder; verify the file still loads with an empty `template_vars` (no doubled-curly-brace anywhere, including comments)

## 6. Agent-authored path

- [ ] 6.1 Carry the brand block into the `pi-render` brief built by `build_author_brief` in `visual_studio.workflow.json` (and the adapter if the brief is assembled there); verify the brief text contains the brand tokens and the workflow's `--require-edge` graph is unchanged — apply live per the n8n rules and re-read the published version
- [ ] 6.2 Author one composition through the agent path with the branded brief and verify the rendered video uses the brand palette and typefaces — `[UNVERIFIED]` until a live session run; record the outcome in the task

## 7. Acceptance and record

- [ ] 7.1 Render every diagrammatic kind offline (infographic, animated WebP/GIF, animated SVG, video) and confirm each uses the brand's dark scheme and typefaces, with no network
- [ ] 7.2 Produce one raster hero and confirm its prompt carried the photographic art direction and that the asset is not styled as a UI card
- [ ] 7.3 Re-render the committed render demo samples through the branded shell and update them; verify the documented durations and frame counts still hold
- [ ] 7.4 Update the `visual-studio` section of `AGENTS.md` and `agents/n8n/render/README.md` to name `brand.json` as the single source and the sync command; verify a reader can change a brand colour and see it in the next render without touching a generator
