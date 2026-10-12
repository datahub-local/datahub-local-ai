# Tasks

## 1. Vocabulary and prompt

- [x] 1.1 Add `agents/n8n/prompts/visual_forms.md` — the ten forms and what each asks for
- [x] 1.2 Replace the inline form list in `agents/n8n/prompts/curator_judge.md` with `{{ FORMS }}`
- [x] 1.3 `BENCHMARK` and `COST` default to `chart` in `agents/n8n/datasets/hook_types.json`; update `_comment_visual`

## 2. Studio graph

- [x] 2.1 Add `download_visual_forms` → `visual_forms` (both copies); wire `visual_rules → download_visual_forms → visual_forms → download_registry`
- [x] 2.2 `normalize_input` (both copies): the enum is the ten forms, `image` dropped
- [x] 2.3 `build_author_brief` (both copies): read the fetched vocabulary and append it to the brief; no inline definitions

## 3. Curator graph

- [x] 3.1 Add `download_visual_forms` (both copies); wire `parse_hook_registry → download_visual_forms → fetch_candidates`
- [x] 3.2 `parse_judge` and `parse_judge_backfill` (both copies): `FORMS` is the ten forms
- [x] 3.3 Both judge prompt nodes pass `{{ FORMS }}` from the fetched file

## 4. Test

- [x] 4.1 `test_visual_studio_graph.py`: the vocabulary is fetched and reaches the brief; the enum matches the file
- [x] 4.2 `test_hook_registry.py`: the enum, the two `FORMS` arrays and the file agree; the judge prompt carries `{{ FORMS }}`; `BENCHMARK`/`COST` are `chart`
- [x] 4.3 `uv run -- pytest agents/n8n/scripts/ -q` (324 passed) and `ruff check` pass

## 5. Apply

- [x] 5.1 Applied live 2026-10-12 with `scripts/apply_workflow_changes.py --changes --require-edge`: `Visual Studio` (`2pSrRNmYR2jkX1JG`, 31 nodes) and `Content Feed Curator` (`iIA5QN5HuK21TmBX`, 50 nodes) were rewired, re-read and diffed — the live draft, `activeVersion`, connections and settings equal the export, `active: True`
- [ ] 5.2 [UNVERIFIED] Confirm a forced `FORCE=chart` renders a chart and an unknown form fails naming it
- [ ] 5.3 [BLOCKED] The live `download_visual_forms` reads `prompts/visual_forms.md` from the default branch; until it and the `{{ FORMS }}` judge prompt are pushed, both workflows fail at the fetch. The prompt/registry push must land with the apply.

## 6. Docs

- [x] 6.1 Update the `FORCE` paragraph in `AGENTS.md`
