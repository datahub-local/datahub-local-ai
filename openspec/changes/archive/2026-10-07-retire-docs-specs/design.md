# Design

## Context

Two spec systems coexisted:

- `openspec/` — `openspec/changes/<active>/` with `proposal.md`, `design.md`,
  `tasks.md` and capability deltas under `specs/<capability>/spec.md`, folded
  into `openspec/specs/<capability>/spec.md` on archive. `openspec validate`
  gates it and `openspec list` reads it.
- `docs/specs/` — five standalone records in the `AGENTS.md` convention.

`AGENTS.md` documented the second in detail (numbering rules, sibling links, the
"decision record, not a plan" principle, the repo-wide-grep-on-rename rule). The
`openspec/changes/` records already cite `docs/specs/NNN` by path, so the two
systems were coupled in one direction with no reverse pointer.

## Decision

**`docs/specs/` is retired; `openspec/` is the only spec system.** The six
design files move into one archived change, `2026-10-07-retire-docs-specs`, under
`designs/`, kept verbatim. A new design record is an `openspec/changes/<id>/`
directory; a completed one is archived.

### Why one archived change, not five, and not five capabilities

- **Not five archived changes.** An archived change is a completed *change*. The
  five records are design documents that never had a change lifecycle; wrapping
  each in an invented `proposal.md` would fabricate rationale it never had.
- **Not five capability specs.** `openspec/specs/<capability>/spec.md` is a set
  of `Requirement`/`Scenario` deltas describing current behaviour. The five
  records are prose design with rationale, rejected alternatives and gate
  findings — the format deliberately rejected by OpenSpec's requirement grammar.
  Converting them would lose exactly the content the convention says to keep.
- **One archive directory** preserves the set, keeps their sibling links
  resolving (all five sit in `designs/`), and keeps the migration's own rationale
  beside the payload.

### What is preserved from the old convention

The principles in `AGENTS.md` that are not specific to the file layout survive
and are restated in the OpenSpec workflow: a spec is a decision record and is not
deleted when its work lands; renaming is a repo-wide grep, not a `docs/` one;
every unverifiable fact is marked. The layout-specific parts (the `NNN` file
number versus the logical number, the sibling-link blockquote) do not apply once
`openspec/changes/<id>/` names the change and `openspec/changes/archive/<date>-<id>/`
orders it.

## Migration

1. `git mv` the six files into `designs/`; remove the empty `docs/specs/`.
2. Repoint live references. The moved files reference each other by bare filename
   in the same directory, so those keep resolving.
3. Replace the `AGENTS.md` section with a pointer to the OpenSpec workflow.

### The one pre-existing break

`001-bodega-spec.md` links `../agents/n8n/schemas/bodega_invoice.schema.json`,
which resolves under `docs/specs/` to a non-existent `docs/agents/…`. It was
broken before the move and is left as-is: an archived record is not re-edited,
and the correct path (`../../../../../agents/n8n/schemas/…` from `designs/`) is
recorded here rather than patched into the archive.

## Risks

| Risk | Mitigation |
|------|------------|
| A live pointer is missed and dead-ends | `grep -rn 'docs/specs' --include='*.md' --include='*.yaml' --include='*.py'` after the move; only archive/ and this change may still match. |
| A moved sibling link breaks | All six files share one directory, so the bare-filename links still resolve; verified by reading the heads of `002`–`005`. |
| The archived change is added to `openspec list` | It is created under `archive/`, which `openspec list` does not read; `openspec validate --all` does not validate `archive/`. |

## Definition of done

- `docs/specs/` does not exist and `openspec/changes/archive/2026-10-07-retire-docs-specs/designs/`
  holds all six files.
- `grep -rn 'docs/specs'` matches only the archive and this change.
- `AGENTS.md` documents `openspec/` as the spec system and no longer special-cases
  `docs/specs/`.
