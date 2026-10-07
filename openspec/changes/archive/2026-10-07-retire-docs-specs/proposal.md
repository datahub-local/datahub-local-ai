# Proposal

## Why

The repository carries two spec systems. `openspec/` holds the active,
delta-based workflow (`proposal` → `design` → `tasks` → capability deltas →
`archive/`). `docs/specs/` held five free-standing design records in a parallel
convention documented in `AGENTS.md`: `NNN-kebab-case-title.md`, sibling links,
gate findings, a numbered implementation plan, a risk table and a definition of
done.

The two systems describe the same kind of artifact and neither references the
other at its source of truth. The cost is concrete: `004-agents-hosted-model.md`
carries the sympozium decisions, while `openspec/changes/` carries the visual and
finance changes, and a reader looking for "the spec for X" has to know which
system X landed in. `AGENTS.md` itself has to explain the `docs/specs/` numbering
scheme, including its known inconsistency, and operations in `openspec/` reference
`docs/specs/NNN` by path, so the parallel convention leaks into the active one.

This change retires `docs/specs/` into `openspec/` and removes the special-case
convention from `AGENTS.md`.

## What Changes

- **The six design files (five topics) move verbatim** into
  `openspec/changes/archive/2026-10-07-retire-docs-specs/designs/`:
  `001-bodega-spec.md`, `002-01-semantic-layer.md`,
  `002-02-semantic-layer-location.md`, `003-data-quality-and-lineage.md`,
  `004-agents-hosted-model.md`, `005-personal-finance-datalake.md`.
- **`docs/specs/` is removed.** `git mv` keeps history; the archived change is
  the only copy.
- **Live pointers are repointed**, not the archived ones: code comments, the dbt
  semantic registry, the dlt finance provider and `AGENTS.md`. Active and
  archived `openspec/changes/` documents that mention `docs/specs/NNN` as past
  work are left as records.
- **`AGENTS.md`'s "Design specs (`docs/specs/`)" section is replaced** by a
  pointer to the OpenSpec workflow, keeping the principles that survive (a spec
  is a decision record, not a plan deleted when done; a rename is a repo-wide
  grep; mark what could not be verified).

## Capabilities

### New Capabilities

None. This is a documentation-structure migration; it declares no runtime
behaviour.

### Modified Capabilities

None.

## Impact

- Moved: `docs/specs/*.md` → `openspec/changes/archive/2026-10-07-retire-docs-specs/designs/`.
- Repointed: `AGENTS.md`, `agents/sympozium/MEMORY.md`,
  `workflows/dbt/semantic/bodega.yaml`, `workflows/dbt/semantic/finance.yaml`,
  `workflows/dbt/semantic/README.md`, `workflows/dlt/projects/finance/__init__.py`,
  `workflows/dlt/projects/finance/providers/base.py`,
  `workflows/dlt/projects/finance/providers/enablebanking.py`.
- Untouched: `openspec/changes/**` records, active and archived.

## Non-goals

- **No rewrite of the moved content.** It is preserved as written, including its
  known issues (`001-bodega-spec.md`'s two `../agents/…` links were already
  broken before the move; they stay as-is, recorded here rather than patched in
  an archived record).
- **No new capability specs** invented from the prose records. They stay design
  records, not requirement deltas.
- **No change to the sympozium upgrade work**; only its references are repointed.
