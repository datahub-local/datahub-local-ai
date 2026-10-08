# Tasks

## 1. Registry

- [x] 1.1 Replace `datasets/visual_types.json` with three types: `image` (author `image`, Gemini, png), `animation` (author `agent`, mp4), `animation_linkedin` (author `agent`, gif, aspect 4:5, inside the platform cap); verify the file parses and no retired id remains
- [x] 1.2 Update `parse_registry` for the new `author` values (`image`, `agent`) and carry `FORCE`/`STYLE` from the trigger

## 2. Trigger contract

- [x] 2.1 Add `FORCE` (`auto|diagram|story|data|poster|image`) and `STYLE` (`dark|light`) to `normalize_input` on all three triggers, defaulting to `auto` and the brand default scheme; verify an unknown value fails loudly naming it
- [x] 2.2 Remove `SPEC_JSON` from the contract and from the run record

## 3. Composer (plan + author)

- [x] 3.1 Extend the `pi-render` authoring guide to plan first: emit a short storyboard (form, style, scenes) and then author the composition; honour `FORCE` and `STYLE`
- [x] 3.2 `build_author_brief` passes `FORCE`, `STYLE`, the brand block and the type's format/size budget to the composer; verify the brief carries them
- [x] 3.3 Record the storyboard in the run record so a bad visual is diagnosable

## 4. Retire the deterministic path

- [x] 4.1 Remove the `spec_markup`/`spec_raster`/`spec_service` branches, `spec_from_param`, `parse_spec`, `download_html_template`, `download_svg_template`, `merge_assets`' markup builders and the render-service nodes from `visual_studio.workflow.json`
- [x] 4.2 Delete `prompts/visual_spec.md` and `templates/infographic.html`/`infographic.svg`
- [x] 4.3 Keep the Gemini raster path for `image` unchanged
- [x] 4.4 Apply live with `--require-edge` guards, republish, and re-read the graph

## 5. Retire the render service (cross-repo)

- [x] 5.1 `datahub-local-core`: remove the render deployment and its NetworkPolicy
- [x] 5.2 `datahub-local-ai-mcp`: remove the `render` server and its tool; update the tool-count expectation
- [x] 5.3 Remove `agents/n8n/render/` from this repo (the service, its layouts, its publish target)

## 6. Tests and docs

- [x] 6.1 Replace the layout/compose tests with tests over the three-type registry, the `FORCE`/`STYLE` contract and the graph (no spec branch, no render-service node)
- [x] 6.2 Update the `#### Visual Studio` and `#### LinkedIn post media` sections of `AGENTS.md` to the agent-first pipeline
- [x] 6.3 Run the offline n8n suite and the pi-render adapter tests

## Follow-ups (deployment, not code)

The live graph is applied and published, but the composer's instruction travels in
the adapter image, which is only correct after it is rebuilt and its digest pinned:

- [x] Push `agents/n8n/prompts/visual_raster.md`: `DownloadTemplate` fetches it from
  GitHub `main`; until it is pushed the live raster path fails on the retired
  `{{ SPEC_JSON }}` placeholder.
- [x] Rebuild and re-pin the `pi-render` adapter image: `prompts/authoring.md` is
  baked into the image, so the plan-first instruction is not live until the image is
  republished and its digest pinned. The adapter is now self-contained (it no longer
  derives from the retired render image), which unblocks that build. (done 2026-10-08:
  CI run `37729997108` built and published the multi-arch index, then the `pin` job
  committed `5956742` recording `sha256:e3294d2a…` in
  `sympozium_pi_render.digest` and `agents/adapters/pi-render/deploy/session.yaml`;
  ArgoCD synced to that revision and the session reports the new
  `status.resolvedImageDigest` with `phase: Ready`. The baked prompt carries the
  `## Plan first` section. A live authoring turn from the n8n pod
  (`session_id: verify-planfirst-20261008`, format `mp4`) returned `200` in 79 s and
  its report opens with the storyboard — form `diagram`, the dark scheme, five scenes
  in order; the artifact fetched over `GET /artifacts/…/out.mp4` is `video/mp4`,
  1,118,698 bytes, and `ffprobe` on the session reads h264 1080×1350, 180 frames,
  6.000 s.)
