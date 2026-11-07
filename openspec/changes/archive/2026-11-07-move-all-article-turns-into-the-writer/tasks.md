# Tasks

## 1. The writer owns the turns

- [x] 1.1 `session-server.mjs`: accept `task` (`draft` default, `review`, `aspects`, `improve`).
- [x] 1.2 `review` renders `article_review.md` and answers `review: { pass, explanation }`.
- [x] 1.3 `aspects` loads `article_aspects.json`, runs one turn per aspect, answers
  `findings: [{ aspect, focus, error, text, count }]`.
- [x] 1.4 `improve` renders `article_improver.md`, runs `--no-tools`, writes the `<article>`
  block it returns, and answers the article.
- [x] 1.5 Review, aspect and improve turns run without tools and continue the draft's session.
- [x] 1.6 The registry is validated at boot; a missing or empty registry stops the pod.
- [x] 1.7 `session-lib.mjs`: `splitArticle`, `articleWordCount`, `articleWordLimit` shared with
  the response and the tests.
- [x] 1.8 Tests: review verdict, aspect entries, improve write-back, no-draft refusal, article
  split and word budget. `node --test 'agents/adapters/pi-writer/test/*.test.mjs'` passes.

## 2. The prompts move

- [x] 2.1 `git mv` the review, three aspect and improver prompts to
  `agents/adapters/pi-writer/prompts/`.
- [x] 2.2 `git mv` `article_aspects.json` beside them; its `prompt` values are now filenames.
- [x] 2.3 No copy remains under `agents/n8n/prompts/` or `agents/n8n/datasets/`.

## 3. `Article Creator`

- [x] 3.1 Add `build_review_request`, `request_review` and `parse_review_verdict`.
- [x] 3.2 Remove `ai_model`, `ai_model_fallback`, `check_article_llm`,
  `download_article_review_prompt`, `download_writer_rules` and `download_article_audiences`.
- [x] 3.3 The gate imports no model credential; the retry still carries the reviewer's reason.
- [x] 3.4 Remove the dead `MODEL` and `MODEL_FALLBACK` assignments from `set_workflow_vars`.

## 4. `Article Content Writer`

- [x] 4.1 Add `build_aspects_request`, `request_aspects`, `build_improve_request` and
  `request_improve`.
- [x] 4.2 Rewrite `merge_aspect_findings` for the adapter's entries and `check_improved_draft`
  for the HTTP response shape.
- [x] 4.3 `select_final_draft`: a request that returned no article is `FAILED`, not `NONE`.
- [x] 4.4 Remove the aspect/improver model nodes, the prompt-download chain, `split_aspects`
  and the writer-rules fetch.
- [x] 4.5 Tests: an HTTP failure is `FAILED`, an aspect failure is reported, a bad review
  verdict rejects, and the ledger twin still holds.

## 5. Documentation

- [x] 5.1 `docs/agent/n8n.md`: the review, aspect and edit turns, the prompt location, the push
  order (image first) and the failure reporting.
- [x] 5.2 `agents/adapters/pi-writer/README.md`: the four tasks and the request fields.

## 6. Gate

- [x] 6.1 `node --test 'agents/adapters/pi-writer/test/*.test.mjs'`.
- [x] 6.2 `uv run -- pytest agents/n8n/scripts/ -q`, with the two pre-existing
  `test_post_feed_mix.py` failures recorded on main.
- [x] 6.3 `openspec validate --all`.
- [ ] 6.4 Workflow invariant check on both graph copies (names, positions, references,
  reachability, no langchain node) — run before the pull request.

## 7. Deployment (owner approval, not this pull request)

- [ ] 7.1 Build and publish the multi-arch `pi-writer` image.
- [ ] 7.2 Pin the new digest in `datahub-local-core` and wait for the rollout.
- [ ] 7.3 Show the graph diff and apply both workflows with
  `agents/n8n/scripts/apply_workflow_changes.py --changes ... --require-edge ...`.
- [ ] 7.4 Re-run row 3 through the entry point and read the execution. [UNVERIFIED] until then.
