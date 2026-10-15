# Proposal

## Why

The composer is told to "use the `data` form" or "use the `poster` form" and nothing
in the repo says what those mean. The names are our vocabulary, not the framework's,
so the composer infers the composition and the judge — which may override a hook's
default form — has the same gap. And the enum carried `image`, which is the raster
*medium* (the Gemini image author), not a composition shape: no hook defaults to it
and the still path ignores `VISUAL_FORM` entirely, so it was a bare word that could
only confuse.

The form set is also thin for this author's material: a benchmark, a cost table, an
incident timeline or a code snippet has no form of its own.

## What Changes

- The visual forms SHALL be defined in one committed vocabulary,
  `prompts/visual_forms.md`, fetched by the studio (into the composer's brief) and by
  the curator (into the judge prompt as `{{ FORMS }}`), so the judge that overrides a
  hook's default and the composer that builds it read the same definitions.
- `FORCE` SHALL be `auto`, `diagram`, `story`, `data`, `poster`, `code`, `chart`,
  `timeline`, `quote` or `ui`. `image` is removed — it is the raster medium, not a
  composition form.
- `BENCHMARK` and `COST` SHALL default to `chart`. `code`, `timeline`, `quote` and
  `ui` are reachable by the judge's override; no hook defaults to them.

## Capabilities

### Modified Capabilities

- `visual-studio`: the `FORCE` enum is the ten forms, `image` is dropped, and the
  forms are defined in one vocabulary both the judge and the composer read.

## Impact

- **`agents/n8n/prompts/visual_forms.md`** (new): the one copy of the form vocabulary.
- **`agents/n8n/prompts/curator_judge.md`**: the form list is replaced by `{{ FORMS }}`.
- **`agents/n8n/datasets/hook_types.json`**: `BENCHMARK` and `COST` default to
  `chart`; `_comment_visual` names the ten forms.
- **`agents/n8n/workflows/visual_studio.workflow.json`**: `download_visual_forms` →
  `visual_forms` fetch the vocabulary (both copies); `normalize_input` takes the ten
  forms; `build_author_brief` appends the vocabulary to the brief.
- **`agents/n8n/workflows/content_feed_curator.workflow.json`**:
  `download_visual_forms` fetches the vocabulary (both copies); `parse_judge` and
  `parse_judge_backfill` accept the ten forms; both judge prompts pass `{{ FORMS }}`.
- **`agents/n8n/workflows/visual_studio_test.workflow.json`**: the `FORCE` hint comment.
- **`agents/n8n/scripts/`**: tests tie the enum, the two curator `FORMS` arrays and the
  vocabulary file together, and assert the vocabulary reaches both consumers.
- Applied live with `scripts/apply_workflow_changes.py --changes` (a graph edit adds
  nodes, so it is not a field-level `--set`).

## Non-goals

- Changing the asset types or the media decision. This is the composition form only.
- A `figure`/`screenshot` form: the composer cannot see the source's images.
- Making every new form a hook default; only `chart` is.
