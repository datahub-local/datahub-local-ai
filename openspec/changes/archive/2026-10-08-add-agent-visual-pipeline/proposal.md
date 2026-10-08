# Proposal

## Why

The visual pipeline enumerates every look in code. A typed **content spec** plus a
**layout vocabulary** (`stats`, `flow`, `timeline`, `comparison`, `bars`), a markup
template, and a separate render service all exist so a model can fill in a form. It is
a lot of surface to keep one visual, and it cannot draw the thing that reads best — a
hub-and-spoke diagram, a set of pages, a bespoke animation — without a new layout every
time. The reference visual (a hub with labelled chips and coloured connectors) is not
expressible by any layout today, and adding it means more code to maintain.

An agent given the content can decide the form and author the composition directly. The
deterministic machinery only needs to survive for the one thing it does cheaply and
well: a plain image from Gemini.

## What Changes

- **One composer agent authors the visual.** The existing `pi-render` path (pi + tools +
  headless Chrome) is extended to plan first: from `CONTENT` it decides a **storyboard**
  (form, style, scenes) and then authors and renders the composition in the same turn.
- **The request may force the form** with `FORCE` (`auto | diagram | story | data |
  poster | image`) and the **style** with `STYLE` (a brand scheme: `dark | light`).
- **The registry is three types**: `image` (Gemini, png), `animation` (composer, mp4),
  `animation_linkedin` (composer, gif).
- **Retire** the typed content spec, its validators, the `spec_markup`/`spec_raster`/
  `spec_service` authors, the markup templates, the render-service call, and the render
  service itself (deployment, MCP tool, layout modules).
- **Keep** the Gemini image path and the brand schemes extracted from
  `datahub-local.alvsanand.com`.

## Capabilities

### Modified Capabilities
- `visual-studio`: authoring is one agent turn (plan + compose); the registry is three
  types; the trigger carries `FORCE` and `STYLE`.
- `agent-authored-compositions`: the composer plans the storyboard as part of the same
  turn, rather than only executing a brief.

## Impact

- **This repo**: `visual_studio.workflow.json` loses the spec/markup/render-service
  branches and gains `FORCE`/`STYLE`; `datasets/visual_types.json` shrinks to three
  types; `prompts/visual_spec.md` and `templates/infographic.*` are removed;
  `agents/adapters/pi-render/` authoring guide gains the planning step.
- **datahub-local-core** (`blocked by`, cross-repo): remove the render deployment and
  its NetworkPolicy.
- **datahub-local-ai-mcp** (`blocked by`, cross-repo): remove the `render` server and
  its tool.

## Non-goals

- The blog pipeline (`add-content-writer-agent`) and the LinkedIn text gate
  (`fix-linkedin-post-review-gate`) are untouched.

## Archive order

Archive after `add-agent-authored-assets`, whose contract this extends.
