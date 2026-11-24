# Tasks

## 1. The story rules

- [x] 1.1 `agents/n8n/prompts/visual_scene.md`: one idea per scene, the arc (intro names
      the subject and the question, the conclusion answers it), the close carries the
      conclusion and the Source together, one explanatory line when the shapes alone do not
      make the idea, cut a label before that line, shape/icon/emoji/attention semantics.
- [x] 1.2 `agents/n8n/prompts/visual_forms.md`: a "choosing the form" map from the post's
      argument to the form, with the hook's `visual` as the fallback.
- [x] 1.3 `agents/n8n/prompts/visual_review_composition.md`: the story-first order, the
      person's requirements as invalidating findings, per-scene takeaway, arc, attention,
      metaphor, close and copy priority; keep the ledger protocol and geometry checks.
- [x] 1.4 `agents/n8n/prompts/visual_review_plan.md`: the text-only plan critic with the
      same requirement/arc/attention/metaphor checks and the ledger answer.
- [x] 1.5 `agents/n8n/workflows/visual_studio.workflow.json`: `prepare_stills` /
      `encode_stills` pass the composer's `STORYBOARD` and the approved `PLAN` to the critic;
      `build_author_brief` puts the person's feedback before the content.

## 2. The form choice

- [x] 2.1 `agents/adapters/pi-writer/prompts/linkedin_post.md`: the form section and the
      `<form>ID</form>` tag, with the mapping by argument.
- [x] 2.2 `agents/adapters/pi-writer/session-lib.mjs`: `renderFormList` and
      `parsePostForm`, an unknown id is a named error; `session-server.mjs` passes `FORMS`
      on the brief and returns `post.form`.
- [x] 2.3 `agents/adapters/pi-writer/test/post.test.mjs`: the form tag, the assigned form,
      and the unknown id.
- [x] 2.4 `agents/n8n/workflows/linked_in_post_creator.workflow.json`: parse `<form>` from
      the answer and write `VISUAL_FORM` when the row is empty; the row still wins.
- [ ] 2.5 Rebuild and pin the writer image; verify a live post returns a form and the media
      branch reads it.

## 3. The plan turn

- [x] 3.1 `agents/adapters/pi-render/prompts/plan.md`: the structured storyboard contract,
      one JSON object and nothing else.
- [x] 3.2 `agents/adapters/pi-render/session-lib.mjs`: `planInstruction` and `parsePlan`
      (first JSON object, null plus error when unreadable).
- [x] 3.3 `agents/adapters/pi-render/session-server.mjs`: `task: "plan"` runs Pi without
      tools, returns `{plan, raw}`, and does not transcode, still, check or sweep.
- [x] 3.4 `agents/adapters/pi-render/Dockerfile`: carry `prompts/plan.md`.
- [x] 3.5 `agents/adapters/pi-render/test/`: the plan parse and the instruction; the
      authoring path unchanged.

## 4. The plan gate

- [x] 4.1 `agents/n8n/workflows/visual_studio.workflow.json`: add `if_needs_plan`,
      `execute_plan`, `parse_plan`, `download_plan_review_prompt`, `review_plan`,
      `parse_plan_verdict`, `if_plan_ok`, `plan_feedback`; wire
      `build_author_brief -> if_needs_plan`, the plan loop, and `if_plan_ok -> execute_author`.
- [x] 4.2 `build_author_brief` carries the approved `PLAN`; `agent_result` carries it on the
      asset; the plan is skipped when `REVIEW_ROUND > 0`.
- [x] 4.3 Add the graph changes to a `--changes` spec and run `tidy_workflow.py`; verify both
      graph copies and `node --check`.

## 5. Apply and verify

- [ ] 5.1 Finish `close-visual-review-holes` 7.4: deploy the adapter image, roll the
      session, apply both workflow exports, re-activate, and confirm the approval names the
      open findings.
- [ ] 5.2 Replay the five labelled runs through the plan/story criteria; confirm 17579's
      missing conclusion, 17587's fade-out and cut lines, and the four diagram runs' wrong
      form are named.
- [ ] 5.3 One live `animation_linkedin_video` run on row 48: plan approved before render,
      close has both, no open findings at approval, or the findings are named.
- [x] 5.4 Update `docs/agent/n8n.md` and the `visual-studio` / `linkedin-post-publishing`
      spec deltas; `openspec validate add-human-story-gate --strict`.
