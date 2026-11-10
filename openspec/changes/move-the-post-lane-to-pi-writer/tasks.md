# Tasks

## 1. The post lane in the adapter

- [x] 1.1 `session-lib.mjs`/`session-server.mjs`: accept `lane: "post"` alongside the existing
  `task` values, default an absent lane to `article`, and refuse an unknown combination by name
  (a post task with no `post` text, an article task with no `article`). Article requests behave
  exactly as before: verify with the existing adapter suite, which must pass unchanged.
- [x] 1.2 Move the six files into `agents/adapters/pi-writer/prompts/`: `linkedin_post.md`,
  `linkedin_post_system.md`, `linkedin_post_rules.md`, `linkedin_post_review.md`,
  `linkedin_variety.md`, `ai_speak.md`. Wording is unchanged except the header line of
  `linkedin_variety.md` that names `set_variety_directives`; the rules template now fills
  `{{ MIN_WORDS }}`, `{{ MAX_WORDS }}` and `{{ AI_SPEAK }}` from the brief and the adapter's own
  `ai_speak.md`. Verify every placeholder resolves and no prompt names an n8n node.
- [x] 1.3 `session-lib.mjs`: `chooseDirectives({ variety, hook, hookOpening, minWords, maxWords, random })`
  — the weighted draw for format, length band and closing, the hook line, the length target inside
  `[MIN_WORDS, MAX_WORDS]`, and the four-line directive block. Store the result in the session
  directory before the draft turn and reuse it for every later turn of the same session; draw a
  fresh set only when the file is absent.
- [x] 1.4 `session-server.mjs`: the draft turn renders the system prompt, the post prompt and the
  rules into one Pi session and answers `<output>…</output>`; the review turn renders the review
  prompt with the caller's `post.text`, the stored directives, the rules, the URL and the feedback,
  and answers `<output>true|false</output><explanation>…</explanation>`. The answer carries the
  same text shape the two n8n Code nodes already parse.
- [x] 1.5 Tests under `agents/adapters/pi-writer/test/`: the seeded draw (weights, the length target
  inside the range, the hook line, one set per session), the draft answer shape, the review answer
  shape, a review with no stored directives drawing and recording a set, and the article lane's
  tasks unchanged. No network and no real `pi`: the server test uses the existing stub.

## 2. The workflow

- [x] 2.1 `linked_in_post_creator.workflow.json`, both copies: delete `create_post_ai`,
  `check_rules_llm`, `ai_model`, `ai_model_fallback`, `download_ai_speak`,
  `download_post_rules_prompt`, `download_variety_directives`, `download_post_prompt`,
  `download_post_system_prompt`, `download_post_review_prompt`, `variety_directives` and
  `set_variety_directives`, and the edges that connect them. Keep `main_trigger`,
  `set_workflow_vars`, `download_hook_registry`, `parse_hook_registry`, `parse_llm_output`,
  `if_enabled_check`, `parse_llm_check_output`, `switch_check_rules_llm`, `set_output` and
  `set_error_max_tries`.
- [x] 2.2 Add `build_post_request` (Code: `lane`, `task: "draft"`, `session_id: post-<row>`,
  `brief` with `content`, `url`, `post_type`, `min_words`, `max_words`, `extra_prompt`, `feedback`,
  `previous_post`, `hook`, `hook_opening`, `attempt`; the address from `$env.ARTICLE_WRITER_URL`),
  `request_post` (HTTP POST, timeout as the article lane's), `read_post_answer` (map the body to
  `{ text }`), and the review pair `build_review_request` / `request_review` / `read_check_answer`.
  A retry edge from `switch_check_rules_llm` feeds `build_post_request`; the gate's `explanation`
  joins the feedback there, as `download_post_prompt` did.
- [x] 2.3 Keep the hook registry read: `download_hook_registry` + `parse_hook_registry` are the
  only remaining download; resolve the row's `HOOK` to its `opening` and pass `hook` and
  `hook_opening` as values. Do not copy the registry into the adapter.
- [x] 2.4 Apply live with `apply_workflow_changes.py --changes --require-edge` after confirming each
  premise edge, re-activate, and re-read: both copies identical, the retired nodes absent from both,
  the workflow active. Do not add a test that asserts the export (owner rule, 2026-11-07).
  **Landed 2026-11-09:** dry run confirmed all five premise edges; applied both workflows, re-read
  live equals the committed exports (creator 16 nodes, sharing 52), both `active=true`, and the creator
  carries no `langchain` node.
- [x] 2.5 `linked_in_post_sharing.workflow.json`, both copies: add `ROW_NUMBER` to
  `execute_post_creator`'s inputs (`select_article_to_post.row_number`) and its schema, so the
  session id is `post-<row>`; the contract's other inputs are unchanged.
- [x] 2.6 Publish the `pi-writer` image: the prompts and the session server are in it, so the live
  lane cannot serve `lane: "post"` until `publish-images.yaml` has built it and pinned the digest in
  `agents/sympozium/values/default.yaml.gotmpl`, and ArgoCD has rolled the session.
  **Landed 2026-11-09:** publish run `42705454198` completed, pin `a04ab52` (`87f201c2…`), ArgoCD
  hard-refreshed and the deployment rolled; the pod lists all six post prompt files.
- [ ] 2.7 Verify the two paths offline as far as possible and then live: `ENABLE_CHECK=true` with a
  forced rejection (the explanation appears in the next attempt) and `ENABLE_CHECK=false` (the first
  draft reaches `set_output`). The adapter contract was smoke-tested live on 2026-11-09: a
  `post-smoke-*` session drafted (directives drawn, `<output>` body) and its gate rejected it with a
  named subject-switch reason. The n8n side still needs one scheduled/pick-up run for each branch.

## 3. Removal and documentation

- [x] 3.1 Delete the six moved files from `agents/n8n/prompts/`. Leave
  `linkedin_post_classify.md` alone: it is already retired and unused; note that in the PR rather
  than reviving or deleting it here.
- [x] 3.2 Update `docs/agent/n8n.md`: the post-lane sections that say the rule pair is `prompts/
  linkedin_post_rules.md` + `prompts/linkedin_post_review.md` and "live on push" (the 2026-09-30 and
  2026-10-12 notes), the hook-registry paragraph, and the AI-speak paragraph (line ~1121) now say
  both turns read one directory in the adapter and a wording fix needs an image rebuild. The two
  model nodes and the prompt downloads are gone; the hook registry still feeds the curator, the post
  generator and the image lane.
- [x] 3.3 Update `agents/adapters/pi-writer/README.md`: the request table gains `lane` and the post
  brief fields, and the artifacts/answer shapes gain the post's two text answers. State that the
  service is reached as `ARTICLE_WRITER_URL` for both lanes and that the post lane has no tools.
- [x] 3.4 Update the prompt-policy paragraph in `AGENTS.md` that names
  `agents/n8n/prompts/*.md` + `DownloadTemplate`: it must now say the article and post prompts live
  in `agents/adapters/pi-writer/prompts/` and that the remaining `DownloadTemplate` reads are
  datasets and the lanes that still use them.

## 4. Verification

- [x] 4.1 `node --test 'agents/adapters/pi-writer/test/*.test.mjs'` passes, including the new post
  tests and the unchanged article tests.
- [x] 4.2 `openspec validate --all` passes and `openspec list` shows the change.
- [x] 4.3 Run the n8n review of the diff (`agents/n8n/README.md` rules): both graph copies equal,
  every premise edge declared, no prompt `DownloadTemplate` left in the post creator (the hook
  registry remains), no `ai_languageModel` edge in either copy.
- [ ] 4.4 `[UNVERIFIED]` Live: one row drafted, gated and approved; one row rejected with a reason
  the retry carries; `ENABLE_CHECK=false` on a third row. Record the execution ids here.
  `ARTICLE_WRITER_URL` needs no check: `article_content_writer` already exercises it through
  `article_creator`, which reads it in every request builder.
