# Tasks

## 1. The form

- [x] 1.1 Append the definition to `agents/n8n/prompts/visual_forms.md`, after `launch`:

  ```
  - `tiles`: fill the field - a regular grid of tiles, each carrying an arc or corner motif completed by a seeded walk, under a technical HUD frame naming the pattern and its seed.
  ```

  ASCII only, one line, no vocabulary name inside the definition that is not already a
  form. The file is read from GitHub `main` at run time by the studio (into the brief) and
  by the curator (into the judge prompt as `{{ FORMS }}`), so this half needs no apply.
  **Landed.** Appended after `launch`; the definition is ASCII and names no other form.

- [x] 1.2 Confirm the definition is readable by the readers that parse it: the registry
  test's `^- \`([a-z_]+)\`:` pattern and `test_hook_registry.py`'s `^- \`([a-z]+)\`: .+`
  both match `tiles`, and neither matches a line whose definition is empty. Run
  `uv run pytest scripts/test_visual_studio_registry.py scripts/test_hook_registry.py`
  from `agents/n8n/` and record the result — at this point the two vocabulary tests fail
  on the enum mismatch, which is the expected state until 3.1–3.3 land.
  **Landed, and taken in the other order.** The definition line was added with the graph
  arrays in the same session, so the intermediate failing state was not the state measured:
  the registry test's `^- \`([a-z_]+)\`:` reader picked `tiles` up first (2.3's check), and
  the vocabulary-equality tests passed once 3.1–3.3 were in (3.3's run below).

## 2. The registry

- [x] 2.1 Add two entries to `agents/n8n/datasets/visual_types.json`, after
  `animation_linkedin_video` and before `svg`, with the `_comment_form` field already
  documented at the top of the file:

  - `tiles`: `name: "Tiling loop"`, `brandKind: "diagrammatic"`, `author: "agent"`,
    `render: "video"`, `format: "mp4"`, `aspect: "4:5"`, `form: "tiles"`,
    `durationSeconds: 12`, `available: true`,
    `budget: { fps: 30, frames: 360, viewport: 1080 }`
  - `tiles_wide`: `name: "Tiling loop (wide)"`, the same fields with `aspect: "16:9"` and
    `budget.viewport: 1280`

  No `secondsPerScene` on either (D4: a pattern has no scenes; a caller's `SCENES` must
  not stretch it). No `holdSeconds` (the animated-type rule). No new `_comment_*` key:
  the fields are all ones the file already explains.
  **Landed.** Both entries inserted after `animation_linkedin_video`, in the field order the
  file already uses for its neighbours.

- [x] 2.2 Extend `agents/n8n/scripts/test_visual_studio_registry.py`:

  - add `"tiles", "tiles_wide"` to the exact-ordered list in
    `test_the_registry_declares_the_expected_types`, in registry order (after
    `animation_linkedin_video`, before `svg`);
  - add a case asserting both types declare `form == "tiles"` (already covered as
    *knownness* by `test_a_type_may_pin_the_form_it_means`), `render == "video"`,
    `format == "mp4"`, `durationSeconds > 0`,
    `frames == durationSeconds * budget.fps` (360 = 12 × 30), no `secondsPerScene` and no
    `holdSeconds`, with the two aspects `4:5` / `16:9`.

  **Landed.** The id list gained the pair in registry order, and a new case holds the form,
  both aspects, the viewports, `frames == duration x fps`, the absent per-scene floor and the
  absent hold.

- [x] 2.3 Prove the new case fails without 2.1: revert the two entries, run
  `uv run pytest scripts/test_visual_studio_registry.py`, record the failures (id list and
  the new case), restore them, and record the pass. A test that passes with the entries
  absent asserts nothing.
  **Landed.** With the two entries removed: `2 failed, 20 passed` — the id-list case and the
  new case (`StopIteration` on the missing `tiles`). Restored: that file's 22 pass.

## 3. The vocabulary's copies in the graph

- [x] 3.1 `agents/n8n/workflows/visual_studio.workflow.json`, node `normalize_input`:
  append `'tiles'` to `const FORCES = [...]` (line 8 of the node's `jsCode`). Both copies
  of the graph in the export — top level and `activeVersion` — are edited identically.
  **Landed.** `const FORCES = ['auto', ..., 'launch', 'tiles']` in both graph copies
  (2 replacements in the export).

- [x] 3.2 `agents/n8n/workflows/content_feed_curator.workflow.json`, nodes `parse_judge`
  **and** `parse_judge_backfill`: append `'tiles'` to `const FORMS = [...]` in each. Both
  graph copies in the export, both nodes.
  **Landed.** Both curator nodes, both graph copies (4 replacements).

- [x] 3.3 Run the offline gates from `agents/n8n/` and record the result:
  `uv run pytest scripts/test_hook_registry.py scripts/test_visual_studio_graph.py
  scripts/test_visual_studio_registry.py scripts/test_code_nodes_parse.py`. The first two
  assert that `visual_forms.md`, `normalize_input`'s `FORCES` and both curator `FORMS`
  arrays are one set; `test_code_nodes_parse.py` proves each edited `jsCode` is still
  parseable, which is the class of defect nothing else catches.
  **Landed.** `-q` over those four files: **94 passed** in 4.85 s. The vocabulary-equality
  tests and the `node --check` wrapper both hold with the three arrays edited.

- [x] 3.4 Run the whole `agents/n8n` offline suite and record the count, so the change is
  not landed on the strength of four files:
  `uv run pytest scripts/`.
  **Landed.** `uv run -- pytest agents/n8n/scripts/ -q` from the repository root — the CI
  command — gives **496 passed, 1 skipped**.

## 4. Apply to the live instance

- [x] 4.1 Ask the owner before writing, per the repository rule. Present the diff of the
  three `jsCode` edits (live vs the export) and the plan, and get an explicit answer.
  **Answered 2026-10-17: apply.**

- [x] 4.2 Dry run with `scripts/apply_workflow_changes.py`, guarded by `--require-edge`
  for the edges the change assumes — pick them from the export's own connection graph for
  the node being edited rather than from memory (for the studio, an edge into and out of
  `normalize_input`; for the curator, the edges through `parse_judge` and
  `parse_judge_backfill`). Record the guards used and confirm each premise held.

- [x] 4.3 Apply (field-level `--set` on the `jsCode` of those nodes; never a whole
  exported body), then re-read each workflow: `activeVersion` carries the edit,
  `active` is still true, and the export's node-name set, connections and touched nodes
  match the live read-back. If `active` flipped, re-activate and confirm; an activation
  failure leaves the workflow deactivated, so this is not a step to skip.
  **Landed.** `--changes /tmp/changes.json --apply` wrote the three fields; both workflows
  reported `active: True -> True`, so no deactivate/activate cycle was needed. Read-back
  against the exports: `Visual Studio` 29 nodes, `Content Feed Curator` 50, node-name sets
  equal, `connections` equal, every touched node deep-equal, each carrying `'tiles'` once,
  `activeVersion` also carrying it, `settings` unchanged.

- [x] 4.4 Confirm the run-time refusal is what it was: force a bad value once
  (`FORCE=nonsense`) or read `normalize_input`'s message back, so the "loud on a missing
  copy" claim in the design is measured rather than assumed.
  **Measured 2026-10-17.** The applied `normalize_input` was read back out of live and
  executed under `node` with a stub input: `FORCE=tiles` is accepted and returned;
  `FORCE=nonsense` throws `unknown FORCE: nonsense (expected one of auto, ..., launch, tiles)`;
  a blank `FORCE` still resolves to `auto`; and a request without `CONTENT` still throws
  `CONTENT is required`.

## 5. Behaviour verification

- [ ] 5.1 Exercise the form and the type together: `POST /webhook/visual-studio` with
  `CONTENT`, `ASSET_TYPES=tiles_wide`, `FORCE=tiles` (and no `SESSION_ID`, so the run is
  isolated). Confirm: the run is not `PARTIAL` for the requested type, the artifact is an
  mp4, `ffprobe` gives ≈12 s at 30 fps, the run record's `STORYBOARD` names the `tiles`
  form, and the S3 key is `visual-studio/<RUN_ID>-tiles_wide.mp4`.

- [ ] 5.2 Read the brief the composer actually received (the run record or the node's
  output), and confirm it names the form and carries `prompts/visual_forms.md` verbatim —
  the forced form arrives with its definition, not merely its name.

- [ ] 5.3 Check the picture against the definition, since that is the only test of a form:
  is the field a tiled arc pattern joined into S-curves and circles, is the split seeded
  rather than random per run, does the HUD name the pattern and its seed. Record what the
  render shows, including anything the definition failed to produce — a capsule summary,
  not a claim of quality.

- [ ] 5.4 Measure the determinism the contract asks for: run 5.1 twice with the same
  content and form, and compare the two renders' first and last frames (or the seed the
  composer reports). Same seed → same field; a different seed → record it as a finding,
  since "no unseeded randomness" is the brief's own rule.

- [x] 5.5 Exercise the publishing lane's routing without a real post: confirm that a
  `content_queue` row carrying `VISUAL_FORM=tiles` reaches the studio with `FORCE=tiles`
  and still `ASSET_TYPES=animation_linkedin_video`. Use `Visual Studio Test` or a
  hand-shaped request where a full run is not wanted, and record which was used. If a real
  row is used, leave it as it was found.
  **Verified by reading the live lane 2026-10-17** (no row flipped, no post run): the applied
  `execute_visual_studio` still sends `ASSET_TYPES: animation_linkedin_video`, its `FORCE` is
  `$('select_article_to_post').item.json.VISUAL_FORM || 'auto'`, it carries no `EXTRA_PROMPT`,
  and `check_animation_result` still matches `want = 'animation_linkedin_video'`. So a row whose
  `VISUAL_FORM` is `tiles` reaches the composer as `FORCE=tiles` with the feed's own type.

## 6. Documentation

- [x] 6.1 Correct the spec drift this change found, in the delta already written
  (`specs/visual-studio/spec.md`): the registry requirement now lists `image_wide` and
  `svg_wide`, the trigger requirement's `FORCE` enum carries `tiles`, and the new
  requirement states the type-pins-its-form precedence `build_author_brief:31` implements.
  **Landed** as part of this change, in `specs/visual-studio/spec.md`.

- [x] 6.2 Update the Visual Studio section of `AGENTS.md`, where a reader looks before
  touching this area: the type list gains the `tiles` pair, the form vocabulary gains
  `tiles`, and the section records the one non-obvious fact this change established —
  **the vocabulary is duplicated into the graph in three places** (`normalize_input`'s
  `FORCES`, the curator's two `FORMS` arrays), so adding a form is a registry *and* graph
  change with a live apply, not a prompt push. State the failure mode when a copy is
  missed (a loud `unknown FORCE` at run time, an offline test failure before it).
  **Landed.** The section now reads `Eleven types` with the tiling pair described, `FORCE`
  gains `tiles`, and the FORCE/STYLE paragraph carries the three-copies fact and both
  failure modes.

- [ ] 6.3 Leave every `[UNVERIFIED]` in `design.md` honest after 5.1–5.5: resolve what was
  measured, keep marked what was not, and do not invent a cause for a composer that
  produced a generic grid.

- [ ] 6.4 Archive only when the work is complete: `openspec archive add-tiles-form` moves
  this change under `changes/archive/<date>-add-tiles-form/` and folds the delta into
  `openspec/specs/visual-studio/spec.md`. Until then it stays in `changes/` and
  `openspec validate --all` is the gate.
