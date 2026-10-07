# Tasks

- [x] 1.1 `git mv` `docs/specs/001…005` into
  `openspec/changes/archive/2026-10-07-retire-docs-specs/designs/` and remove the
  empty `docs/specs/`; verify `git status` reports renames, not delete+add.
- [x] 1.2 Verify the moved records' sibling links still resolve: all six files
  sit in one directory, so the bare-filename links do.
- [x] 2.1 Repoint live references: `AGENTS.md`,
  `agents/sympozium/MEMORY.md`, `workflows/dbt/semantic/bodega.yaml`,
  `workflows/dbt/semantic/finance.yaml`, `workflows/dbt/semantic/README.md`,
  `workflows/dlt/projects/finance/__init__.py` and its `providers/`.
- [x] 2.2 Leave `openspec/changes/**` records (active and archived) untouched as
  history.
- [x] 3.1 Replace `AGENTS.md`'s "Design specs (`docs/specs/`)" section with the
  OpenSpec workflow, keeping the surviving principles.
- [x] 4.1 `grep -rn 'docs/specs'` matches only the archive and this change.
- [x] 4.2 Note the pre-existing broken `001` schema link in the design rather
  than patching the archived record.
