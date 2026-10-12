# Design

## Context

The visual form is the `FORCE` enum: `auto` plus five concrete forms, declared in
`normalize_input` (the enforcing enum), the two curator `parse_*` nodes, the judge
prompt, the registry comment and the test. The composer's brief named the form and
nothing defined it; the judge prompt listed the names with no meaning. `image` sat in
the enum although the raster author is chosen by `ASSET_TYPE`, not `FORCE`, and the
still path keys on `HOOK`, never `VISUAL_FORM`.

## Gate findings

- `raster_director` does not read `FORCE`; the raster branch is selected by
  `AUTHOR === 'image'`. So dropping the `image` form cannot reach the still path.
- The judge prompt is `prompts/curator_judge.md`, fetched by `download_judge_prompt`
  and `download_judge_prompt_backfill` with `{{ HOOKS }}` from `parse_hook_registry`.
  A `{{ FORMS }}` var needs the file fetched in the curator and passed in both.
- `DownloadTemplate` scans the file for doubled curly braces, so `visual_forms.md`
  carries none.
- `apply_workflow_changes.py` supports `addNodes` and `connections` in `--changes`,
  so a graph edit is expressible; it is idempotent and guards with `--require-edge`.

## Decisions

- **One committed vocabulary, not two copies.** `prompts/visual_forms.md` is the one
  copy, fetched by both consumers exactly as `visual_motion_rules.md` is. The brief
  appends it; the judge prompt substitutes it. This is the rule that a craft decision
  lives in one committed file and is not restated in a workflow.
- **The judge reads it too.** A hook carries a default form, but the judge may
  override it, and an override chosen from bare names is a guess. The same file that
  defines the composer's form defines the judge's options.
- **Drop `image`.** It is the raster medium. Keeping a form value that no hook uses,
  the still path ignores and the composer cannot build is a second meaning for a word
  already used for the asset type.
- **`chart` for `BENCHMARK` and `COST`.** A benchmark and a cost comparison are
  plotted over alternatives, which is a chart, not a single settling figure. The other
  new forms stay reachable by override so the hook defaults change as little as
  possible.

## Risks

- A graph edit on a live workflow changes what runs only after publishing; the apply
  re-activates and the export is diffed against live afterwards.
- The vocabulary file is live on push for the prompt half, but the graph edit is live
  only after the apply, so the two halves land in two steps.

## Open questions

- None.

## Definition of done

- `prompts/visual_forms.md` defines the ten forms; the studio enum minus `auto`, the
  two curator `FORMS` arrays and the file agree.
- The brief appends the vocabulary; both judge prompts carry `{{ FORMS }}`.
- `BENCHMARK` and `COST` default to `chart`.
- `pytest agents/n8n/scripts/` and `ruff check` pass.
- Applied live, re-read, published and diffed against the export.
