# Proposal

## Why

A LinkedIn post clip can open straight on a detail with no scene naming the subject. The
title-scene rule only fires when the caller declares a scene count above one, and the post
lane never declares one: the judge writes `visual.scenes` and every hook in
`datasets/hook_types.json` defaults it to 0, so the brief carries no scene line at all.

Measured on 2026-10-19, studio run 14335 (`lips-72`, `animation_linkedin_video`,
`FORCE=timeline`, `SCENES=''`): the storyboard began on "The exemption" and the clip never
introduced the subject. The intro appeared only in the human retry (run 14342) because the
Slack feedback said "Use a title scene like…" — a person fixed it, not the spec.

Two adjacent gaps made it invisible: the critic's stills are sampled at 25/50/75% plus the
final frame, so the opening scene is in none of them, and the review prompt judges fit to
the brief, which did not ask for an intro.

The same question — *where is that defined?* — exposed a repo-wide one. The word "scene"
appears in no prompt file as a definition; it exists only as a count and a label assembled
in `build_author_brief` jsCode. A review of every workflow found four more model-facing
instructions that live in code rather than in a prompt file (see the audit in `design.md`).

## What Changes

- A registry type may declare `introScene: true`. The three animation types do; the tiling
  loops, the SVG and the stills do not.
- For such a type, the authoring brief asks for an opening title scene naming the subject
  even when the scene count is blank (the composer still chooses its content scenes). A
  declared count above one keeps its current `N + 1` shape; a declared count of one is
  unchanged.
- The clip stills sample the opening: offsets become 10/40/70% instead of 25/50/75%.
- `INTRO_SCENE` rides on the request and on the asset, so a review turn keeps the
  declaration it is correcting.
- A **scene contract** is declared in a prompt file and appended to the brief: what a scene
  is, what the storyboard is, and where the title scene sits. The brief keeps only the
  count and placement arithmetic.
- **AGENTS.md gains the rule**: every model-facing instruction lives in a prompt file or the
  authoring brief; inline instruction prose in code is a gap.
- The audit's other gaps are fixed or recorded per the options chosen (task 8), and
  `test_prompt_sources.py` makes a new inline prompt fail offline.

## Capabilities

### Modified Capabilities

- `visual-studio`: an animated clip SHALL open on a title scene naming the subject,
  whether the scene count is declared or chosen by the composer.

## Impact

- **`agents/n8n/datasets/visual_types.json`**: `introScene` on `animation`,
  `animation_linkedin`, `animation_linkedin_video`, plus `_comment_introScene`.
- **`agents/n8n/workflows/visual_studio.workflow.json`**: `parse_registry`,
  `agent_result` and `build_author_brief` (both copies). Applied live with
  `scripts/apply_workflow_changes.py`, guarded by `--require-edge`.
- **`agents/adapters/pi-render/session-lib.mjs`**: `DEFAULT_STILL_OFFSETS`; needs the
  adapter image rebuilt and rolled out before the critic can see the opening.
- **`agents/n8n/prompts/`**: a new scene contract file, plus the gap fixes chosen in task 8.
- **`AGENTS.md`**: the prompt-source rule.
- Tests: `test_visual_studio_graph.py`, `test_visual_studio_registry.py`,
  `agents/adapters/pi-render/test/session-lib.test.mjs`, a new `test_prompt_sources.py`.
- No hook registry or sheet change.
