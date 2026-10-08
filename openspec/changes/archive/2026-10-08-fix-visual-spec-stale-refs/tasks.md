# Tasks

## 1. Sync the main specs

- [x] 1.1 Sync the `visual-studio` delta into `openspec/specs/visual-studio/spec.md`: remove the static-hero, declared-but-unavailable and shared-brand requirements and add their re-issued forms (`image` type, composer-session example, current kinds), and modify the requested-set, asset-set and model-output requirements; verify no retired term remains (`grep -nE 'hero|infographic|animated SVG|SPEC_JSON|spec-driven|motion_clip' openspec/specs/visual-studio/spec.md` is empty)
- [x] 1.2 Sync the `visual-brand` delta into `openspec/specs/visual-brand/spec.md`: re-issue the kind requirement for a diagrammatic `image`/`animation` and a photographic image
- [x] 1.3 Edit the `visual-brand` Purpose directly (a Purpose is not a requirement): drop "infographic", "animated diagram" and "hero image" for the current kinds

## 2. Verify

- [x] 2.1 `openspec validate --all` passes with no failure
- [x] 2.2 `grep -rnE 'hero|infographic|animated SVG|SPEC_JSON|spec-driven|motion_clip|two-stage|content spec' openspec/specs/` returns nothing
