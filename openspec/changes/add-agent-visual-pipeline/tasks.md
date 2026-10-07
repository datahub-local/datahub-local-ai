# Tasks

## 1. Registry

- [ ] 1.1 Replace `datasets/visual_types.json` with three types: `image` (author `image`, Gemini, png), `animation` (author `agent`, mp4), `animation_linkedin` (author `agent`, gif, aspect 4:5, inside the platform cap); verify the file parses and no retired id remains
- [ ] 1.2 Update `parse_registry` for the new `author` values (`image`, `agent`) and carry `FORCE`/`STYLE` from the trigger

## 2. Trigger contract

- [ ] 2.1 Add `FORCE` (`auto|diagram|story|data|poster|image`) and `STYLE` (`dark|light`) to `normalize_input` on all three triggers, defaulting to `auto` and the brand default scheme; verify an unknown value fails loudly naming it
- [ ] 2.2 Remove `SPEC_JSON` from the contract and from the run record

## 3. Composer (plan + author)

- [ ] 3.1 Extend the `pi-render` authoring guide to plan first: emit a short storyboard (form, style, scenes) and then author the composition; honour `FORCE` and `STYLE`
- [ ] 3.2 `build_author_brief` passes `FORCE`, `STYLE`, the brand block and the type's format/size budget to the composer; verify the brief carries them
- [ ] 3.3 Record the storyboard in the run record so a bad visual is diagnosable

## 4. Retire the deterministic path

- [ ] 4.1 Remove the `spec_markup`/`spec_raster`/`spec_service` branches, `spec_from_param`, `parse_spec`, `download_html_template`, `download_svg_template`, `merge_assets`' markup builders and the render-service nodes from `visual_studio.workflow.json`
- [ ] 4.2 Delete `prompts/visual_spec.md` and `templates/infographic.html`/`infographic.svg`
- [ ] 4.3 Keep the Gemini raster path for `image` unchanged
- [ ] 4.4 Apply live with `--require-edge` guards, republish, and re-read the graph

## 5. Retire the render service (cross-repo)

- [ ] 5.1 `datahub-local-core`: remove the render deployment and its NetworkPolicy
- [ ] 5.2 `datahub-local-ai-mcp`: remove the `render` server and its tool; update the tool-count expectation
- [ ] 5.3 Remove `agents/n8n/render/` from this repo (the service, its layouts, its publish target)

## 6. Tests and docs

- [ ] 6.1 Replace the layout/compose tests with tests over the three-type registry, the `FORCE`/`STYLE` contract and the graph (no spec branch, no render-service node)
- [ ] 6.2 Update the `#### Visual Studio` and `#### LinkedIn post media` sections of `AGENTS.md` to the agent-first pipeline
- [ ] 6.3 Run the offline n8n suite and the pi-render adapter tests
