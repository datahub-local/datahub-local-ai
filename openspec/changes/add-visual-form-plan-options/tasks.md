# Tasks

## 1. The adapter turns

- [x] 1.1 `agents/adapters/pi-render/prompts/forms.md` and `prompts/plans.md`: the stage
      contracts — `forms` returns `{"options":[{"id","form","why","sketch"}]}`; `plans`
      returns `{"options":[{"id","plan":{...}}]}` with the existing plan fields, and
      `prompts/plan.md` stays the one copy of the plan schema. One JSON object, nothing
      else. The form vocabulary is the existing `PLAN_FORMS` list.
- [x] 1.2 `agents/adapters/pi-render/session-lib.mjs`: `parseFormOptions(answer)` and
      `parsePlanOptions(answer)`; each option validated (form in the vocabulary; plan
      through the existing `parsePlan`); an invalid option is named, not guessed at.
      `formOptionsInstruction` / `planOptionsInstruction` add the stage, the option count
      and the loss of tools.
- [x] 1.3 `agents/adapters/pi-render/session-server.mjs`: accept `task: "forms"` and
      `task: "plans"`; both run with no tools, write nothing, and return
      `{forms, error}` / `{plans, error}` plus the raw answer. `plans` reads the chosen
      `form` from the request.
- [x] 1.4 `agents/adapters/pi-render/Dockerfile`: carry the prompt if it is a new file.
- [x] 1.5 `agents/adapters/pi-render/test/`: form-option parse (valid, unknown form,
      unreadable), plan-option parse (valid, one invalid option, unreadable), and the
      instructions name the stage and the option count. Run `npm test`.

## 2. The critic prompts

- [x] 2.1 `agents/n8n/prompts/visual_review_forms.md`: a text critic that reads the post,
      the content, the person's feedback and the options, and returns
      `{"choice":"<id>","why":"..."}`. The rubric is the one in `visual_review_plan.md` plus
      "does this shape carry the content the post announces?".
- [x] 2.2 `agents/n8n/prompts/visual_review_plans.md`: a text critic that ranks the plan
      options and returns `{"choice":"<id>","why":"..."}`. The existing plan checks
      (person's requirements, arc, one idea per scene, close, metaphor, standalone) are the
      ranking rubric.
- [x] 2.3 `agents/n8n/workflows/visual_studio.workflow.json`: `download_form_review_prompt`,
      `download_plan_options_review_prompt`, `review_forms`, `review_plans` HTTP nodes on
      the same gateway/model as `review_plan`; 300 s timeout, `neverError`, text response.

## 3. The workflow stages

- [x] 3.1 `build_forms_brief`: from the author brief and the resolved `FORCE`/`FORM`,
      produce the forms request (`task: "forms"`, `options: 3`, no tools).
- [x] 3.2 `parse_forms`: carry the options; `execute_forms` posts to the adapter.
- [x] 3.3 `parse_form_choice`: validate the critic's `choice` against the option ids; pick
      the first option when the answer is unreadable; set `FORM_OPTIONS`, `FORM_CHOICE`,
      `FORM`, `OPTIONS_FALLBACK`.
- [x] 3.4 `build_plans_brief`: from the chosen form and the author brief, produce the plans
      request (`task: "plans"`, `form`, `options: 3`).
- [x] 3.5 `parse_plans` / `parse_plan_choice`: validate each option through the plan parser;
      pick the critic's choice; set `PLAN_OPTIONS`, `PLAN_CHOICE`, `PLAN`, `PLAN_APPROVED`,
      `OPTIONS_FALLBACK`; a chosen plan is approved without the single-plan retry loop.
- [x] 3.6 `if_needs_form`: true when `REVIEW_ROUND === 0`, no approved plan, the type
      declares no form, and `FORCE` is `auto`; its true branch runs the form stage. Its
      false branch runs `if_plan_options_start`, true when `REVIEW_ROUND === 0`, no
      approved/exhausted plan, and a form is fixed (`FORM` non-empty or `FORCE` not
      `auto`); true routes to `build_plans_brief`, false to the existing `if_needs_plan`.
      The single-plan path remains the fallback when a stage cannot run; a correction turn
      or an approved/exhausted plan goes straight to authoring.
- [x] 3.7 `build_author_brief` carries `FORM_OPTIONS`/`FORM_CHOICE`/`PLAN_OPTIONS`/
      `PLAN_CHOICE`/`OPTIONS_FALLBACK` onto the asset beside `PLAN`/`STORYBOARD`; the
      approval message names a fallback.
- [ ] 3.8 Wire the graph in both copies of the export and `tidy_workflow.py --write` — done;
      the `--changes`/`addNodes` spec is committed at `live-apply.json`. Applying it with
      `apply_workflow_changes.py` waits for the rebuilt adapter image; re-read
      `activeVersion` and confirm `active` after the apply.

## 4. The post lane

- [x] 4.1 `build_hook_columns`: keep writing `HOOK`; stop writing the writer's
      `VISUAL_FORM`/`SCENES` to the row. Pass the writer's form and scenes as
      `SUGGESTED_FORM`/`SUGGESTED_SCENES`; compute `FORM_PIN` from the row snapshot at run
      start (`select_article_to_post.VISUAL_FORM`), so only a human edit pins.
- [x] 4.2 `execute_visual_studio` inputs: `ASSET_TYPES=animation_linkedin_video` for the
      animated branch; `FORCE=FORM_PIN || 'auto'`; `SUGGESTED_FORM`/`SUGGESTED_SCENES` as
      hints. The 6 s `poster_gif` is no longer selected by the animated branch.
- [x] 4.3 `check_animation_result` / media approval: accept either type but expect
      `animation_linkedin_video`; name `FORM_CHOICE`/`PLAN_CHOICE` and a fallback in the
      approval.
- [ ] 4.4 One row with a writer-only form (no human pin) must produce the 30 s video and a
      form chosen by the critic; one row with a human `VISUAL_FORM` pin must keep the pin
      and skip the form stage.

## 5. Specs, docs, verification

- [x] 5.1 `docs/agent/n8n.md`: the two stages, the hint/pin split, the type change, the
      fallback, and the option records on the asset.
- [x] 5.2 `openspec validate add-visual-form-plan-options --strict`.
- [ ] 5.3 Rebuild and pin `pi-render`; live-run the Genie Migrate row and confirm the form
      options, the plan options, the chosen plan and the 30 s video, or name the fallback.
- [ ] 5.4 Run the article `svg_wide` visual through the plan options: the form stage is
      skipped and the chosen diagram plan is used. Repeat with a pinned `FORCE` on an
      agent type: the form stage is skipped and the plan-options stage runs with the pin.
