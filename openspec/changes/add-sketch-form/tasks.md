# Tasks

## 1. The form

- [x] 1.1 Append the definition to `agents/n8n/prompts/visual_forms.md`, after `tiles`:

  ```
  - `sketch`: draw it as a sketched diagram - labelled boxes, arrows and connectors on a wobbly ink stroke whose wobble is a seeded, index-derived offset rather than a random one, the strokes drawing themselves on in reading order and settling into a drawing that stays legible, with no shading, gradient or photographic fill and one slow camera drift to the end.
  ```

  ASCII only, one line, no vocabulary name inside the definition. Read from GitHub `main` at run
  time by both readers, so this half needs no apply.
  **Landed.** One appended line; no form name appears inside it and no non-ASCII byte was added.

- [x] 1.2 Check the line is readable by the two parsers that read the file: the studio's vocabulary
      reader and the curator's `{{ FORMS }}` injection both take every `- \`name\`: definition` line.
      The offline tests that asserted this (`test_hook_registry.py`, `test_visual_studio_registry.py`)
      were removed on 2026-11-07; the gate is now `openspec validate --all` plus the live run, so
      state that in place of a pytest result rather than citing a suite that no longer exists.
  **Landed, and recorded as such.** The line matches the file's existing shape byte for byte
  (`- \`name\`: ` + one line); no test asserts it any more, by the repository rule that forbids
  tests over prompt files.

## 2. The registry

- [x] 2.1 Add two entries to `agents/n8n/datasets/visual_types.json`, after `svg_wide` and before
      `figure`:

  - `sketch`: `name: "Sketch diagram"`, `brandKind: "diagrammatic"`, `author: "agent"`,
    `render: "video"`, `format: "mp4"`, `aspect: "16:9"`, `form: "sketch"`, `durationSeconds: 12`,
    `available: true`, `budget: { fps: 30, frames: 360, viewport: 1280 }`
  - `sketch_svg`: `name: "Sketch diagram (SVG)"`, `render: "static"`, `format: "svg"`, the same
    aspect, form and duration, no `budget` (the animated-SVG types declare none)

  No `secondsPerScene` and no `introScene` on either (D4: one drawing). No `holdSeconds`.
  **Landed.** Both entries in the field order their neighbours use; `frames == durationSeconds x
  budget.fps` (360 = 12 x 30) on the mp4 type.

- [x] 2.2 Prove the file still parses and the pair is well formed where a reader can see it: load the
      dataset and assert each entry's `form` is one the vocabulary declares, the mp4 type's
      `frames == durationSeconds * budget.fps`, and neither type declares `secondsPerScene`,
      `introScene` or `holdSeconds`. A one-off check is right here, not a committed test, because a
      test over this dataset is the kind the repository rule forbids.
  **Landed, as a one-off read.** Both entries load, `form: sketch` is in the vocabulary, 360 = 12 x
  30, and the three absent fields are absent.

## 3. The vocabulary's copies in the graph

- [x] 3.1 `agents/n8n/workflows/visual_studio.workflow.json`, node `normalize_input`: append
      `'sketch'` to `const FORCES = [...]`. Both copies of the graph in the export (top level and
      `activeVersion`) are edited identically.
  **Landed.** `... 'launch', 'tiles', 'sketch']` in both graph copies (2 replacements).

- [x] 3.2 `agents/n8n/workflows/content_feed_curator.workflow.json`, nodes `parse_judge` **and**
      `parse_judge_backfill`: append `'sketch'` to `const FORMS = [...]` in each. Both graph copies,
      both nodes.
  **Landed.** Both nodes, both graph copies (4 replacements).

- [x] 3.3 Run `node --check` over each edited `jsCode` (wrapped in an async function, since a
      top-level `return` is legal there and illegal in a plain script), so the change does not ship a
      syntax error the JSON cannot show. The `test_code_nodes_parse.py` that used to do this was
      removed on 2026-11-07.
  **Landed.** All six literals parse under `node --check` in an `(async () => { ... })()` wrapper.

- [x] 3.4 Confirm the three arrays agree with the vocabulary as sets: the studio's `FORCES`, both
      curator `FORMS`, and the names `visual_forms.md` declares plus `auto`.
  **Landed.** 15 names in each: `auto` + the vocabulary's 14 forms.

## 4. Apply to the live instance

- [x] 4.1 Ask the owner before writing, per the repository rule: show the diff of the three `jsCode`
      edits (live vs the export) and the plan, and get an explicit answer.
  **Answered 2026-11-17: apply, then run both types once.**

- [x] 4.2 Dry run `scripts/apply_workflow_changes.py`, guarded by `--require-edge` for the edges the
      change assumes, picked from the export's own connection graph (an edge into and out of
      `normalize_input`; the edges through `parse_judge` and `parse_judge_backfill`).
  **Landed.** Guards used: `api_trigger > normalize_input`, `normalize_input > download_brand`,
  `judge_llm > parse_judge`, `parse_judge > loop_judge_finalists`,
  `judge_llm_backfill > parse_judge_backfill`, `parse_judge_backfill > update_backfill_columns` —
  all six reported `edge ok` against live before the write. The first dry run wrote the field at the
  node's top level and the script's own warning said so (`normalize_input.'jsCode' does not exist`);
  the spec was corrected to `parameters.jsCode` before `--apply`.

- [x] 4.3 Apply (field-level `--set` on those nodes' `jsCode`; never a whole exported body), then
      re-read: `activeVersion` carries the edit, `active` is still true, and the export's node-name
      set, connections and touched nodes match the live read-back.
  **Landed.** `Visual Studio` 47 nodes, `Content Feed Curator` 52, both `active: True -> True` (no
  deactivate/activate cycle needed), node-name sets equal to the export, `connections` equal, every
  touched node deep-equal to its export, and `activeVersion` also carrying `'sketch'`.

- [x] 4.4 Measure the run-time refusal: execute the applied `normalize_input` with `FORCE=sketch`
      (accepted) and `FORCE=nonsense` (throws, naming the enum), so "loud on a missing copy" is
      measured rather than assumed.
  **Measured 2026-11-17** on the applied node, with a stub `$input`: `FORCE=sketch` returns
  `FORCE: sketch`; `FORCE=nonsense` throws `unknown FORCE: nonsense (expected one of auto, ...,
  tiles, sketch)`; a blank `FORCE` resolves to `auto`; a request without `CONTENT` still throws
  `CONTENT is required`.

## 5. Behaviour verification

- [ ] 5.1 `POST /webhook/visual-studio` with `ASSET_TYPES=sketch`, `FORCE=sketch`, no `SESSION_ID`:
      `STATUS: COMPLETE`, one mp4 asset, `ffprobe` 1280x720 / ~12 s / 30 fps, key
      `visual-studio/<RUN_ID>-sketch.mp4`.
      **Blocked on the push, and the first attempt proves why.** Run 16947 (2026-11-17, executor:
      enums applied, registry edited locally) answered `HTTP 200`, `STATUS: FAILED`, one asset
      `sketch` with `STATUS: UNKNOWN`, `ERROR: unknown asset type: sketch`. The registry is fetched
      by `download_registry` through `DownloadTemplate` from `BACKUP_GITHUB_REPO_*` on `main`, so a
      type exists live only once the dataset is pushed — the enum apply alone cannot make it
      resolvable.

- [ ] 5.2 The same for `ASSET_TYPES=sketch_svg`: an `.svg` asset whose first frame is the drawing's
      opening state and whose `STORYBOARD` names the sketch form and its seed.

- [ ] 5.3 Check the picture against the definition, since that is the only test of a form: a labelled
      diagram on a wobbly stroke, drawn on in reading order, no shading or gradient, in the requested
      brand scheme, with the drawing still legible at the end and no frozen tail. Record what the
      renders show, including anything the definition failed to produce.

- [ ] 5.4 Confirm the feed lane's routing without a real post: a `content_queue` row carrying
      `VISUAL_FORM=sketch` reaches the studio as `FORCE=sketch` with `ASSET_TYPES=animation_linkedin_video`.

## 6. Documentation

- [x] 6.1 Update `docs/agent/n8n.md`, Visual Studio section: the type list gains the sketch pair, the
      `FORCE` enum gains `sketch`, and the section records the non-obvious fact — the wobble and the
      draw-on are authored (seeded offset, `stroke-dashoffset`), because `rough.js`,
      `DrawSVGPlugin` and a sketch typeface are all absent from the image.
  **Landed.**

- [ ] 6.2 Archive only when 4.x and 5.x have landed: `openspec archive add-sketch-form`, folding the
      delta into `openspec/specs/visual-studio/spec.md`, then `openspec validate --all`.
