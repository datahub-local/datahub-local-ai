# Design

## Context

- `build_author_brief` builds one `sceneLine`; it asks for a title scene only when
  `SCENES > 1`.
- `SCENES` reaches the studio from `content_queue.SCENES`, which the curator writes from
  the judge's `visual.scenes`, which defaults to 0 for every hook. The post lane therefore
  sends a blank count and the composer plans the storyboard.
- `parse_registry` maps a type's fields onto the request; `agent_result` copies the
  container onto the asset so a review turn does not re-declare it.
- The adapter samples a clip at 25/50/75% plus the settled final frame.

## Goals / Non-Goals

**Goals:**

- Any animated clip produced from the post lane opens on a scene that names the subject.
- The requirement is data: a type declares it, the brief reads it.

**Non-Goals:**

- Changing the judge, the hooks or `SCENES`; a roundup's count still means content items.
- A title for a pattern loop (`tiles`), an SVG diagram, a still, or a deck (whose first
  slide is already its title).
- Changing the declared-count arithmetic (`N + 1`), which already works.

## Decisions

### D1. Key the intro on the type, not on the count

A count is a caller's plan for content items; an introduction is a property of a clip that
sequences content. Run 14335 has six scenes and a blank count, and it is exactly the case
the count-gated rule misses. *Alternative considered:* make the judge set `scenes` on every
hook — rejected, because a count would then invent content divisions for a narrative and
change the clip's duration (`SCENES * secondsPerScene`).

### D2. The registry declares it

`introScene: true` on the three animation types, read by `parse_registry` into
`INTRO_SCENE`. A hardcoded id list in `build_author_brief` would be a second copy of the
registry, and the repo's rule is that a type's shape is its data.

### D3. Only the video branch receives the line

`sceneLine` is shared by the deck, SVG, PNG and video branches. The new `introLine` is
inserted in the video branch alone, so a future type that declares `introScene` on another
render mode cannot silently change a deck or a still.

### D4. The declaration rides on the asset

A review turn builds its item from `agent_result`, not from `parse_registry`, so
`INTRO_SCENE` must be copied there or turn 1 would drop the line the first turn was given
(the same failure `ASPECT`/`FRAMES` had on 2026-10-17).

### D5. The first still reaches the opening

Offsets 10/40/70% keep three samples plus the final frame, so the critic's cost is
unchanged while the opening is now in the first still. A fixed 10% is ~3 s on a 30 s clip
and ~0.9 s on the 9 s GIF; the intro is briefed first, so both land inside it.

## Model prompt audit (2026-10-19)

Every workflow export was read for model-facing instructions: `agent`/`chainLlm` text,
HTTP bodies sent to LiteLLM, `toolWorkflow` descriptions, and Code nodes that build prompt
strings. "Compliant" means the instruction comes from `agents/n8n/prompts/*.md` (or a
reviewed dataset) through `DownloadTemplate`.

| Workflow | Surface | Source | Verdict |
| --- | --- | --- | --- |
| `article_creator` | `create_article_ai`, `create_article_ai_plain`, `check_article_llm` | `article_writer_system.md`, `article_writer.md`, `article_review.md`, `ai_speak.md`, `article_structures.md` | compliant |
| `article_creator` | `research_sources`, `read_page` tool descriptions | `article_tools.md` (G2, fixed) | compliant |
| `content_feed_curator` | `judge_llm`, `judge_llm_backfill` | `curator_judge.md` + `hook_types.json`, `visual_forms.md` | compliant |
| `image_content_generator` | `AI Agent` → `generate_image` | `diagram_generator.md` | compliant |
| `image_content_generator` | `suggestedImagePrompt` prefilled in the edit form | `diagram_prompt_prefill.md` (G5, fixed) | compliant |
| `linked_in_image_creator` | `create_image_prompt_ai` | `linkedin_image_prompt.md` | compliant |
| `linked_in_image_creator` | subject/fusion/avoid and hook section wording | `linkedin_image_prompt.md` (G3, fixed); code emits lists | compliant |
| `linked_in_post_creator` | `create_post_ai`, `check_rules_llm` | `linkedin_post.md`, `_system`, `_rules`, `_review`, `ai_speak.md` | compliant |
| `linked_in_post_creator` | format / length / closing directive lists | `linkedin_variety.md` (G4, fixed) | compliant |
| `visual_studio` | `raster_director`, `critique`, `critique_raster` | `visual_raster.md`, `visual_review_composition.md`, `visual_review_raster.md` | compliant |
| `visual_studio` | authored brief | `visual_motion_rules.md`, `visual_scene.md`, `visual_forms.md` + count lines | compliant (G1 fixed) |
| `visual_studio` | critic body labels ("The brief the composer was given:") | inline | allowed — mechanical joins, not rules |
| `article_content_writer`, `content_board_curator`, `linked_in_post_sharing`, `visual_studio_test` | — | no model prompt of their own | n/a |

### D6. The scene contract is a prompt file

A definition is not a count. The brief says how many, in what order and where the title
sits; it never says what a scene *is*. That contract goes in `prompts/visual_scene.md`,
fetched once and appended to the brief the way the motion rules are, so the composer reads
one definition and a change to it is a prompt-file change. *Alternative considered:* a
"Scenes" section inside `visual_motion_rules.md` — no graph change, but it files a
definition of the composition's unit under motion rules, where the next reader will not
look for it.

### D7. Gaps are fixed at their source, not restated

G2 moves the two tool descriptions into a prompt file read by the tool nodes. G3 moves the
motif section wording into `linkedin_image_prompt.md`, leaving `parse_image_motifs` to emit
lists. G4 moves the directive lists into a prompt file that `set_variety_directives`
selects from. G5 moves the suggested-prompt template next to `diagram_generator.md`. Each
gap is a prompt edit plus an expression change; none needs a new model call.

### D8. The rule is enforced offline

`agents/n8n/scripts/test_prompt_sources.py` reads every export's both copies and asserts
that each model node's text resolves to a `download_*` file node (or a builder node named
in an allowlist with the reason), that every `DownloadTemplate` target exists in
`prompts/`/`datasets/`, and that the allowlist still names only accepted gaps. A new inline
prompt fails the test rather than reaching a model.

## Risks / Trade-offs

- **A title costs clip time.** On the 9 s GIF it is roughly a sixth of the clip. →
  Accepted: the clip is the post's cover, and a cold open was the measured defect.
- **A 10% still can catch the entrance.** → The title is the first beat and its enter is
  short; the still is judged for geometry, and the settled frame remains the final one.
- **The composer can ignore the line.** → Nothing enforces it beyond the brief; the
  critic now sees the opening, so a missing intro is at least visible as a fit-to-brief
  finding.

## Migration Plan

1. Edit the registry, the workflow export (both copies) and the adapter.
2. Run the three test files and `ruff check`.
3. **Push the prompt files to `main` first.** Every fetch reads GitHub `main`; a graph that
   names a file not yet there fails on a 404. Measured 2026-10-19: the graph was applied
   before the push, all five workflows wrote and re-activated, and they were rolled back to
   the pre-change graphs within minutes so no run could hit the missing files.
4. Apply the workflow nodes live with `--require-edge`; deactivate/activate each workflow
   whose node set changed; rebuild and roll the pi-render image for the still offsets.
5. Read one live post clip's first still and confirm it shows the subject.

Rollback: revert the export and the registry, apply back; the adapter change is
independent and harmless on its own.

## Open Questions

- None.
