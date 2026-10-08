# Proposal

## Why

`add-agent-visual-pipeline` retired the deterministic spec/render path and replaced the
visual type registry with three types — `image`, `animation`, `animation_linkedin`. Its
archive synced the delta requirements it recorded, but the `visual-studio` and
`visual-brand` main specs still name concepts that no longer exist: a static "hero", an
"infographic", "animated SVG", `motion_clip`, `SPEC_JSON` and "spec-driven" assets. A
reader of the current-behaviour spec would implement a pipeline that was deleted. This
change reconciles those remaining requirements with the pipeline that actually runs.

## What Changes

- **`visual-studio`**: reframe the surviving requirements that still speak the retired
  vocabulary — the asset-set example, the "static hero" guarantee (now the `image`
  type), the unavailable-type example (now an agent-authored type with no composer
  session), "model output is data" (a brief is data; the composer's authored markup is
  the intended artifact), and the brand requirement (diagrammatic `image`/`animation`
  and a photographic image). No requirement's meaning changes; the wording moves onto
  the three-type registry.
- **`visual-brand`**: same reconciliation for the two-kind requirement and the Purpose
  line, which still list infographics, animated SVG and a "hero".
- Edit the `visual-brand` Purpose directly (a Purpose is not a requirement and cannot
  travel in a delta).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `visual-studio`: the asset-set, static-image-availability, declared-but-unavailable,
  model-output-is-data and brand requirements are reworded onto the three-type registry.
- `visual-brand`: the "follows the brand for its kind" requirement is reworded onto the
  two current kinds; its Purpose is corrected directly.

## Impact

Specification text only. No code, workflow, registry or chart change: the running
pipeline already matches the reconciled wording. Touches
`openspec/specs/visual-studio/spec.md` and `openspec/specs/visual-brand/spec.md` on
archive.

## Non-goals

- Re-introducing or renaming any visual type; the registry is the source of truth and is
  not edited.
- Changing the `image` type's `brandKind` or the photographic/diagrammatic split.
- Editing archived change artifacts.
