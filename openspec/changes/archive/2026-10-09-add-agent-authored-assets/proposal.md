# Proposal

## Why

The agent-authored path works — a `pi` agent authored and rendered a bespoke
composition in-cluster on 2026-10-05 (`agents/render-samples/pi-authored/`), with
nobody writing the source. But nothing consumes it: it runs only as a hand-driven
Sympozium session, and its artifact never leaves the pod. `LinkedIn Post Sharing`
and the article workflows still get only the deterministic assets Visual Studio can
express from a typed spec.

This change makes the agent a first-class **author** in Visual Studio, backed by the
existing pi-render session, so `LinkedIn Post Sharing` — and any future workflow that
generates docs — can request an agent-authored asset through the same `ASSET_TYPES`
contract it already uses. No caller learns a second API.

## What Changes

- **Add an `agent` author to the Visual Studio type registry.** A type declaring
  `author: agent` is produced by sending the request's `CONTENT` (the brief) to the
  pi-render session and returning the rendered file as the asset's content, exactly
  as the `render: video` type returns the render service's MP4. The deterministic
  two-stage family (`raster`, `spec_raster`, `spec_markup`, `spec_service`) is
  unchanged.
- **Give the pi-render session an artifact contract.** The session returns Pi's
  text; the render lands on its PVC. The adapter SHALL write each run's artifact to a
  per-run directory and serve it back over HTTP, so a workflow can fetch it.
- **Make the session reachable and reproducible.** A production (non-spike) session
  with an additive NetworkPolicy admitting n8n, a pre-created workspace larger than
  the engine's disk gate (the controller's fixed claim is 50 MiB short and cannot
  render), and an idle policy that does not stop the workload before or during a
  workflow call.
- **Request it from `LinkedIn Post Sharing`.** The animated-media path gains an
  opt-in that requests the agent-authored type; the deterministic animated type and
  the still-image fallback keep working, so an agent failure costs one post its
  motion, not its media.
- **Keep one reusable contract.** Visual Studio returns the asset as content, so a
  future doc workflow requests the agent author the same way `LinkedIn Post Sharing`
  does.

## Capabilities

### New Capabilities

None. This wires an existing capability into a consumer; it does not add a new
behavioral capability of its own.

### Modified Capabilities

- `visual-studio`: adds an `agent` author kind — a type whose asset is authored by
  the pi-render agent from the request's `CONTENT` and returned as content, distinct
  from the deterministic two-stage family.
- `agent-authored-compositions`: adds the caller-facing contract — a workflow can
  request an authored composition and receive the rendered artifact over HTTP from a
  deployed, reachable, adequately sized session.

Archive order: archive `migrate-render-layouts-to-catalog-blocks` **before** this change.
Both MODIFY `Authoring is two-stage`, and this change carries the union (the template and
catalog-block rules **and** the `author: agent` carve-out); archiving it first would let the
earlier change's narrower text replace the requirement and drop the carve-out.

## Impact

- `agents/adapters/pi-render/session-server.mjs` — a per-run artifact directory and
  an HTTP fetch endpoint; the prompt names where the artifact is written.
- `agents/adapters/pi-render/deploy/` — the production session objects (policy,
  runtime, agent, session), the n8n NetworkPolicy and the pre-created PVC; the
  current manifests are `sympozium.ai/spike: "true"`.
- `agents/n8n/datasets/visual_types.json` — a new type with `author: agent`.
- `agents/n8n/workflows/visual_studio.workflow.json` — an agent-author branch beside
  `if_raster`/`if_video`; applied live with `scripts/apply_workflow_changes.py`.
- `agents/n8n/workflows/linked_in_post_sharing.workflow.json` — the `POST_MEDIA`
  opt-in for the agent-authored type.
- `agents/n8n/scripts/` — a structural test over both workflow exports.
- No change to the render service, the `visual-studio` trigger contract, the
  `visual_studio_table`, or the existing deterministic types. The pi-render session
  remains a Sympozium object; nothing here makes it a core-owned service.
