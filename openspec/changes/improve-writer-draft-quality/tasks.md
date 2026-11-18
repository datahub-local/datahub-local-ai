# Tasks

## 1. Outline turn (adapter)

- [x] 1.1 `agents/adapters/pi-writer/prompts/article_outline.md`: propose 2-3 candidate
      indexes from the entry fields, the row's source seed and `article_structures.md`;
      each option is a shape id, a one-line outcome and ordered section names with a
      one-line job each; answer inside one `<outline>` block.
- [x] 1.2 `session-server.mjs`: `task: "outline"` — article lane only, `--no-tools`, same
      session; parse the block into options the graph reads as data. Degrade, never
      throw: unparseable → `options: []` + `error` naming the fault; unknown task still
      400 by name; the post lane refuses it. Full suite 91/91.
- [x] 1.3 `article_task.md` and `article_improver.md`: render `{{ OUTLINE }}` with the
      rule that the article is the approved outline, sections in its order, feedback
      outranking it; the gate (`article_review.md`) gains no outline check.
- [x] 1.4 `session-lib`/tests: outline parse coverage in
      `agents/adapters/pi-writer/test/` (empty, malformed, well-formed answers), matching
      the aspect-findings test style; `node --test` green — `test/outline.test.mjs` (10)
      plus `session-server.test.mjs` extended for the task and its degraded answer.
- [ ] 1.5 Rebuild the writer image (it now carries the outline prompt, the post angle
      fill and the two `{{ OUTLINE }}` sections), pin the digest into
      `agents/sympozium/values/default.yaml.gotmpl`, and roll out before
      any graph apply names the outline task. `blocked by` the image pipeline.

## 2. Outline phase (article graphs)

- [x] 2.1 `article_content_writer.workflow.json` (both copies): after the claim,
      `if_outline_present` gates on the row's `OUTLINE` cell — a set cell drafts directly
      (a stale-claimed or re-approved row never re-asks), an empty cell runs
      `execute_article_outline` (`TASK: outline`, `onError: continueErrorOutput`).
      89 → 97 nodes; the creator is 22 → 25.
- [x] 2.2 `notify_outline_approval`: Slack `sendAndWait` customForm listing each option's
      shape, outcome and numbered section names; required dropdown `Option 1/2/3/Cancel`
      + `Edits` textarea; `Cancel` routes to the existing cancel path. Retry is one
      attempt, then the existing `build_failure` path (`ERROR` row + notification; the
      failure nodes say "Article run failed", so an outline failure is not reported as a
      draft failure).
- [x] 2.3 `build_outline_pick` assembles the chosen index (+ `Edits` appended) and
      `update_article_outline` writes it to `article_queue.OUTLINE`;
      `execute_article_creator` passes it as `OUTLINE` (this execution's pick first, the
      row cell as fallback), and the creator's draft and improve requests carry it in
      `brief.outline`. The column is hand-added by the owner — done.
- [x] 2.4 `notify_article_review` appends the approved outline's section names.
- [x] 2.5 Verification: structural checks over both files, both copies (25/28 and 97/113
      nodes/edges, all rules clean); `node --check` over every Code node; a Node harness
      executing every new/edited jsCode against live-shaped stubs (request build, answer
      normalization across transport/HTTP/adapter-error shapes, pick assembly, review
      message, the directive-aware FEEDBACK, both sides of the OUTLINE mapping); every
      `=`-expression in both exports syntax-checked. One shared-node note left as
      measured: an outline cancel writes `CANCELLED` but the cancel confirmation's
      asset-row read is the same possibly-empty shape a first-round draft cancel already
      has. `[UNVERIFIED] live`

## 3. News opening (push-only)

- [x] 3.1 `agents/n8n/datasets/hook_types.json`: `RELEASE` and `NEWS_REACTION` `opening`
      values name the headline change in the first lines, then the take. **Done**; the
      file carries 0 `{{` occurrences, so the empty-template_vars fetch rule holds.
- [x] 3.2 `agents/n8n/prompts/curator_judge.md`: angle rule gains the release carve-out —
      the headline change may be the angle's subject. **Done**.
- [x] 3.3 No gate edit: `linkedin_post_review.md` judges the hook opening through the
      existing directive check. Confirmed by reading; the offline guard tests were
      deleted in `02fe540`, so the check is review plus the next live run. Verify a
      `RELEASE`-hooked row's next draft names the change in its opening lines.
      `[UNVERIFIED] until the next live run`

## 4. Retry directive menu (both lanes)

- [x] 4.1 `article_content_writer.workflow.json`: `notification_retry_or_cancel` gains
      the required `Directive` dropdown (6 options, `Other` last); the FEEDBACK expression
      on `execute_article_creator` prepends `[<directive>] ` for anything but `Other` —
      a directive alone with an empty textarea is feedback. Old-form, no-form and `Other`
      cases reproduce today's value.
- [x] 4.2 `linked_in_post_sharing.workflow.json`: the post text retry form gains the same
      dropdown and mapping. **Done**: required `Directive` dropdown (values in that order,
      `Other` last); the FEEDBACK expression prepends `[<directive>] ` for anything but
      `Other`; old-form, no-form and empty cases verified byte-identical to today.
- [x] 4.3 Structural checks and Node-harness execution of the edited jsCode over both
      exports; no prompt file changes. (The offline pytest guards are gone — deleted in
      `02fe540` — so verification is the archived changes' shape: hand checks plus
      executing committed jsCode against stub items.) Both halves done: 0 structural
      problems across all six touched exports, harness green on every new expression.

## 5. Angle and evidence passthrough

- [x] 5.1 `content_feed_curator.workflow.json`: `admit_to_backlog` (both copies) writes
      `ANGLE` and `EVIDENCE` from the parsed verdict, with `build_queue_rows` and the
      append node's mapping+schema carrying both columns (a column the append does not
      name is a write the run fails on). `content_queue` gains both columns by hand before
      the next curator run. Known gap, accepted: the backfill pass does not write them, so
      a repaired row keeps blank cells — the D5 blank-degrade case.
- [x] 5.2 `linked_in_post_sharing.workflow.json`: the post writer brief carries the row's
      `ANGLE` (declared input on `linked_in_post_creator.main_trigger`, into
      `build_post_request`'s brief); the animated branch prepends the detail/angle block
      to the studio call's `CONTENT` (empty row = today's CONTENT); the still fallback
      passes `EVIDENCE`/`ANGLE` to `LinkedIn Image Creator`, whose
      `download_image_prompt.template_vars` now carries both keys — verified against
      DownloadTemplate's own logic: `missing: []`.
- [x] 5.3 `agents/n8n/prompts/linkedin_image_prompt.md`: gains an `{{ EVIDENCE }}` /
      `{{ ANGLE }}` block beside `{{ POST_CONTENT }}` — the detail that justified
      admission is named for the director. **Done, but push-gated**: `check_template_vars_present`
      stops the run on a placeholder the caller lacks (measured against `HEAD`:
      `missing: ['ANGLE','EVIDENCE']`), so the `linked_in_image_creator`
      graph apply (5.2's wiring) must land before or with this file's push — see design
      D8.
- [ ] 5.4 A queued row's angle and evidence survive to the visual brief; a blank cell
      degrades to today's behaviour. `[UNVERIFIED] until the next live run`
- [x] 5.5 The adapter renders the angle into the post drafting prompt: `## Angle`
      section in `linkedin_post.md` filled from `brief.angle` (follow it unless Reviewer
      Feedback names another; empty = ignore); the review prompt gains nothing — the
      angle is direction, not a gate check. Suite 93/93; the two new tests fail with the
      fill removed.
- [ ] 5.4 A queued row's angle and evidence survive to the visual brief; a blank cell
      degrades to today's behaviour. `[UNVERIFIED] until the next live run`

## 6. Model upgrade

- [x] 6.1 `agents/sympozium/values/default.yaml.gotmpl`:
      `sympozium_pi_writer.model.name` → `opencode-go/glm-5.3`. **Done**; `helm template`
      over the chart renders the writer's `Agent`/`AgentRuntime` with the new model while
      `pi-render` keeps `deepseek-v4.1-flash`. No comment added.
- [x] 6.2 Cross-repo: `datahub-local-core` routes `glm-5.3` on LiteLLM (owner-confirmed)
      and pricing needs no per-model edit — `releases/data/files/litellm/opencode_pricing.py`
      is a generic mirror that copies **every** `opencode_go/*` row from LiteLLM's own cost
      map onto the `openai/<id>` dispatch key, so `glm-5.3` is priced as soon as the map
      carries it. Verified by reading the file.
- [ ] 6.3 Rollout (`helmfile apply` in `agents/sympozium/`), then one live outline + draft
      run on the new model; the drafting turn's word-count discipline still holds.
      `[UNVERIFIED]`

## 7. Live applies and verification

- [ ] 7.1 Show the owner the export diffs, then apply each graph with
      `scripts/apply_workflow_changes.py` `--changes` batches guarded by
      `--require-edge`; read back, re-activate, diff against the exports.
- [ ] 7.2 Drive one article row end to end from a webhook probe: outline form → approval
      → draft follows the outline → retry directive reaches the improved draft.
- [ ] 7.3 `openspec validate --all` and the full adapter test run green.
