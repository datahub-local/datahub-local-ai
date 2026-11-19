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
- [x] 1.5 Rebuild the writer image, pin the digest and roll out before any graph apply
      names the outline task. **Done twice over**: 2026-11-18 (the outline/`glm-5.3` image,
      digest `6351a258…`) and 2026-11-19 (the audience/coherence/research pass,
      digest `a81b2f9b…`, CI green, bot-pinned, ArgoCD synced, pod running).

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
- [x] 3.2 ~~`curator_judge.md` angle carve-out~~ — superseded: the angle field is
      removed entirely (D8), so the registry opening (3.1) is the whole news fix; nothing
      in the judge prompt names the change because the judge writes no direction.
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

## 5. Evidence passthrough (the judge writes no direction)

- [x] 5.1 `content_feed_curator.workflow.json`: the judge's `angle` field is removed
      end to end — `curator_judge.md` (bullet, examples, output schema), `parse_judge`,
      `admit_to_backlog` (`EXTRA_PROMPT: j.angle` goes; `EXTRA_PROMPT` returns to
      human-only) and the digest's brief line. `grep 'j.angle'` is 0; `MODEL` is
      `glm-5.3` in both copies (`MODEL_FALLBACK` unchanged). A judge answer that still
      returns an angle is ignored (harness-fed, verified). The earlier
      `ANGLE`/`EVIDENCE` columns were duplicates and are already reverted out of the
      append.
- [x] 5.2 `linked_in_post_sharing.workflow.json`: the animated branch prefixes the
      studio call's `CONTENT` with "The article's concrete detail: <`RATIONALE`>" only;
      the still fallback passes `EVIDENCE` (from `RATIONALE`) to `LinkedIn Image
      Creator`; the angle half is gone from both paths. The post writer brief needs no
      direction field — the writer takes its position from the article text it reads.
- [x] 5.3 `agents/n8n/prompts/linkedin_image_prompt.md`: carries one
      `{{ EVIDENCE }}` line beside `{{ POST_CONTENT }}`, filled from `RATIONALE`; the
      `{{ ANGLE }}` line is removed with the angle itself. **Push-gated**:
      `check_template_vars_present` stops the run on a placeholder the caller lacks, and
      `HEAD`'s image creator passes no `EVIDENCE`, so the `linked_in_image_creator` graph
      apply (5.2's wiring) must land before or with this file's push — see design D9.
- [ ] 5.4 A queued row's evidence survives to the visual brief; a blank cell degrades to
      today's behaviour. `[UNVERIFIED] until the next live run`
- [x] 5.6 The adapter states the outline's precedence: where the row's `DESCRIPTION`
      itself sketches a structure, the approved outline outranks it — in
      `article_task.md`, `article_improver.md`, and (as "refine, not replace") in
      `article_outline.md`. Found in review: a human-authored board brief may carry its
      own structure, and the draft would otherwise read two competing plans.

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
- [x] 6.3 Rollout, then one live outline + draft run on the new model. **Done, twice**:
      row 4 (2026-11-18 evening, both turns) and row 4 again (2026-11-19 morning) ran
      the outline turn and the drafting turn on `glm-5.3` through the real gateway, and
      the drafting turn's word-count discipline held (975 of 1200).
- [ ] 6.4 The curator judge's `MODEL` moves to `opencode-go/glm-5.3`
      (`set_workflow_vars`, both copies; `MODEL_FALLBACK` stays `glm-5.3-flash`): the
      decisions that bind the writer — hook, visual intent, postability — are made by the
      tier that writes. Judge calls are small and bounded per run, so the cost is cents.
      Applied with the curator graph in 9.1. `[UNVERIFIED] until the next live run`

## 8. Writer-side classification

- [x] 8.1 `curator_judge.md` and `content_feed_curator.workflow.json`: the judge sheds
      `hook` and `visual` too — `curator_judge.md` is 34 lines, selection only
      (`postability`, `blocked`, `evidence`). The judge's registry/forms fetches are
      removed (11 nodes, backfill chain included), `admit_to_backlog` writes `HOOK`/
      `VISUAL_FORM`/`SCENES` blank with `POST_MEDIA=ANIMATED`, and a verdict still
      carrying `hook`/`visual` is ignored (harness-fed). The backfill re-judge pass is
      retired; intake, ranking, ceiling and digest untouched.
- [x] 8.2 `linked_in_post_creator.workflow.json`: a blank row `HOOK` puts the rendered
      eligibility list on the brief; a set `HOOK` keeps today's resolve path. The answer
      parse resolves `hook = assigned || post.hook || <hook>ID</hook>`, validates against
      `byId` in code, and emits the registry's visual defaults with named failures.
- [x] 8.3 `linked_in_post_sharing.workflow.json`: `update_hook_columns` writes `HOOK`,
      `VISUAL_FORM`, `SCENES` at draft-parse and stamps the run's row snapshot so the
      media branches read the classification without a consumer edit.
- [x] 8.4 Adapter: `## Hook` section, `<hook>` parse with named errors, the chosen hook
      stored in `directives.json` (a retry does not re-choose; a swept session re-draws
      per the existing rule), `post: { text, hook, directives }` on the answer.
- [x] 8.5 Verified offline: full suite **100/100**, structural checks both copies, 16/16
      Node-harness cases, `j.angle` count 0, and the curator export no longer references
      the hook registry or `{{ HOOKS }}`/`{{ FORMS }}` anywhere. `[UNVERIFIED] live until
      9.1`
- [x] 8.6 The flagged TTL consequence is closed by reasoning, not left open: blank
      `HOOK` at admission means `build_expire_rows` sees `ttl_days.default` for a queued
      row — but the 7-day ceiling cancels in-play rows regardless and is deliberately
      shorter than every hook TTL (the recorded fact in AGENTS.md), so the TTL was never
      the binding constraint for `QUEUE` rows; published rows carry their hook (written
      at draft-parse), so `PUBLISHED_AT` TTLs still apply per hook. No policy change
      needed. `[UNVERIFIED] against the live sheet's actual values`

## 9. Live applies and verification

- [x] 9.1 Applied live 2026-11-18 via `apply_workflow_changes.py` `--changes` batches,
      one spec per workflow generated from the live-vs-export diff, each guarded by an
      anchor edge present in both graphs. All six verified in `activeVersion`. Two
      lessons added to the tool's usage: a `nodes` entry REPLACES the whole named field
      — `parameters` must be the full object, not a fragment (a `{message}`-only spec
      wiped a Slack node's five other keys and activation refused until the full object
      was re-applied); and after any single-node apply, re-read `activeVersion` and run
      the deactivate/activate cycle — the PUT edits the draft and the published version
      lags until then (parse_outline landed, the first review-message PUT did not).
- [ ] 9.2 Drive one article row end to end from a webhook probe: outline form → approval
      → draft follows the outline → retry directive reaches the improved draft. One post
      row end to end: blank `HOOK` → the writer answers `<hook>` → the row is classified
      before the visual branch reads it. **Half verified live 2026-11-18**: row 4's
      outline turn ran on `glm-5.3`, the bounded form posted and was approved, `OUTLINE`
      was written to the row, the draft ran to the improvement pass; row 48 was drafted
      with a writer-chosen `BENCHMARK` hook and `update_hook_columns` wrote the row
      before the approval wait. **Two live defects found and fixed**: the outline form
      and the review message both died as Slack `invalid_blocks` — model text of 4.4 kB
      and 3.2 kB in single 3 000-character sections — bounded live (names-only + a
      2 800 cap; reviewer notes sliced to 800/500). The review form still has to
      complete a run, and so has the visual/publish half of the post lane.
- [x] 9.3 `openspec validate --all` and the full adapter test run green.
- [x] 9.4 ~~Prompt gaps found in the first live draft~~ — promoted to group 10 and
      implemented there, on the owner's direction, the morning after.

## 10. The audience, coherence and research pass

Found in the first live `glm-5.3` draft (row 4, dbt comparison, `AUDIENCE=LOW`) and
ordered by the owner the morning after. All of it lives in the writer image's prompts, so
it ships with the next image rebuild; the block-relevance rule from 9.4 is folded in
here too.

- [x] 10.1 The audience is honored and checked: `article_task.md` states the level as a
      contract (every sentence at the level, a section only a deeper level needs is out,
      and the final pass re-reads for it); `article_outline.md` phrases outcomes and
      section jobs at the row's level; `article_review.md` gains the audience check; the
      clarity aspect reports level failures. **The level already reached the gate**:
      `build_review_request` has carried `brief.audience` (from
      `set_workflow_vars.AUDIENCE`), and the adapter's review render has filled
      `{{ AUDIENCE }}` and `{{ AUDIENCES }}` — no export edit. What was missing: the live
      article gate is `task: "audit"`, not `"review"`, so `article_audit.md` had the level
      *label* and no definitions and no level check. The check and `{{ AUDIENCES }}` are
      now in both prompts, so the gate that runs sees what the drafter sees. Also fixed
      while there: `article_writer_system.md` said "floor" and `article_review.md`'s term
      check ended "a term the level assumes is a failure to explain" — both contradicted
      the level. The clause is gone; the system prompt says "at the level it names".
- [x] 10.2 Cross-section coherence, checked: `article_task.md` Shape gains the rule
      (each section opens on what the previous established, nothing explained twice, no
      contradictions, a section the chain does not need is cut); `article_review.md`
      lists the coherence check, and `article_audit.md` carries it as finding 6;
      `article_aspect_flow.md` covers relation between sections, with the registry's
      `flow` focus saying so.
- [x] 10.3 The research budget rises to thirty lookups (six searches, twenty-four
      scrapes) and research becomes outline-directed: the approved outline is the research
      plan, walked section by section until each is grounded on pages this run read, with
      the seed page as the start and not the ceiling. Adapter suite 100/100; no proxy or
      allowlist change. `[UNVERIFIED] live until 10.6`
- [ ] 10.4 Block relevance, from 9.4: a block earns its place only where the prose needs
      it; never repeat one; the recommended path's command is the one shown.
- [x] 10.5 The `[sqlfluff]` ledger-matching miss — **diagnosed from the live transcript
      and fixed**: the lint page's scrape was truncated by the tool-output cap, the
      `{"markdown": …}` wrapper was cut mid-string, `unwrapScrapeText`'s JSON.parse threw
      and fell back to the escaped raw text, whose literal `\n` sequences glued the block's
      lines into single tokens — no `findExcerpt` match, no ledger entry, a gate rejection
      of a block the session verifiably read. The unwrap now unescapes the truncated
      wrapper best-effort; the live block matches as `mode: "quoted"`. Suite 102/102 with
      a fails-without-the-change check.
- [x] 10.6 Rebuild the writer image, pin the digest (the CI pin job), roll the pod, and
      re-run the row 4 test with the owner's `ARTICLE_FEEDBACK` in place.
- [x] 10.7 **Blocks serve the outline's outcome** (owner review of the first new-image
      draft, 2026-11-19): a comparison pasted three shell one-liners that carried none of
      the deciding axes. `article_task.md`'s block rule no longer sets a quota —
      walk-throughs and how-tos earn blocks; a comparison, decision or analysis carries a
      block only when the command itself is the axis being compared; `article_structures.md`
      states the same on its one-block rule. The approved outline's outcome is the arbiter.
- [x] 10.9 The exception in 10.7 was rationalized away on the very next run (one
      `python -m pip install dbt` block in a comparison), and the owner's answer was
      structural: **the outline declares each section's content form**. `prose | list |
      table | code`, chosen in the outline turn from the outcome, the extras and the
      audience; the draft writes each section in its named form; a fence belongs only to
      a `code` section. The gates count in code: `parse_article` and
      `check_improved_draft` reject a draft with fences when the approved outline names
      no `code` section (and reject a fence count above the `code` count), data-not-throw,
      mirrored as the budget check is. **Shipped live 2026-11-19** (image `392e2439…`,
      graphs applied + verified in `activeVersion`; outline approval form shows each
      section's form). One discovery: `check_improved_draft` had been removed with the
      one-authoring-turn change and was restored on the improve path, so the dormant
      `TASK: improve` route cannot reintroduce an unplanned fence. An outline whose
      sections carry no form (a pre-change row) skips the check.
- [ ] 10.8 The research rule should tell the writer to read a truncated scrape's spill
      file: the lint-page scrape was cut by the tool-output cap, its full text spilled to
      a file the model never read, and the `[sqlfluff]` block it wrote from memory was
      correctly flagged unsourced by the audit — then incorrectly kept by the improver.
      Two gaps: the spill-read instruction in `article_task.md`, and the improver's
      contract on unapplied findings. Found live 2026-11-19.
