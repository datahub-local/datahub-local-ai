# Design

## Context

Read off the exports and the adapter on 2026-11-09.

- `linked_in_post_creator.workflow.json` is a sub-workflow called by `LinkedIn Post Sharing`. Its
  graph before this change: `main_trigger` → `download_ai_speak` → `download_post_rules_prompt` →
  `set_workflow_vars` → `download_hook_registry` → `parse_hook_registry` →
  `download_variety_directives` → `variety_directives` → `set_variety_directives` →
  `download_post_prompt` → `download_post_system_prompt` → `create_post_ai` → `parse_llm_output` →
  `if_enabled_check` → `download_post_review_prompt` → `check_rules_llm` →
  `parse_llm_check_output` → `switch_check_rules_llm`, whose outputs are retry
  (`download_post_prompt`), pass (`set_output`) and bound (`set_error_max_tries`).
- `create_post_ai` and `check_rules_llm` are the only two `ai_languageModel` consumers. Both are
  `chainLlm` nodes fed by `ai_model` (with `ai_model_fallback`) and by prompt text placed in their
  parameters.
- `set_variety_directives` parses `linkedin_variety.md` sections as `weight | band | directive`,
  draws one format, one length band and one closing, and maps `main_trigger.HOOK` through
  `hook_types.json` to the hook's `opening`.
- `parse_llm_output` strips `<output>…</output>` and rewrites the source line; `parse_llm_check_output`
  reads `<output>` and `<explanation>` and flattens the explanation for the next prompt and the
  bound's error.
- `agents/adapters/pi-writer/`: one `HarnessSession`, `/v1/chat/completions`, a `task` field and a
  prompt directory baked into the image. Every article prompt already lives there; the graph sends
  field values only.
- The post's source text is fetched upstream by the sharing lane. `Content Feed Curator` has already
  chosen the row's `HOOK`; `classify_content` is retired.

## Decisions

### D1. The existing writer session serves both lanes

The post turns go to `pi-writer` — same image, Deployment, PVC and Service — with
`session_id: post-<row_number>`. A second session would mean a second TTL, a second image pin and a
second copy of the server for a turn that is shorter than an article's and needs no browser. The
article lane is separated by the `lane` field, not by infrastructure.

The adapter's `task` already names what a turn does (`draft`, `review`, …). `lane: "post"` selects
the prompt set and the answer shape; an absent `lane` means `article`, so every existing caller is
unchanged. The article tasks are not reused for the post: the post has no ledger, no artifacts and
no research, and folding it into the article contract would make the article's response shape
carry fields it never fills.

### D2. The adapter owns the prompts; n8n sends values

The six files move unchanged in wording, except for the header line in `linkedin_variety.md` that
names `set_variety_directives`. `linkedin_post_rules.md`'s `{{ MIN_WORDS }}`, `{{ MAX_WORDS }}` and
`{{ AI_SPEAK }}` are filled by the adapter from the brief and its own `ai_speak.md`. The rule pair
the drafter and the gate share now sits in one directory, which is the structural fix for the
2026-09-30 and 2026-10-12 failures where the two copies drifted.

The cost is explicit: today a prompt wording fix is live on push because `DownloadTemplate` reads
GitHub `main`. After the move it needs an image rebuild and a digest pin. That is the same trade the
article prompt set already makes, and it is the price of one owner.

`datasets/hook_types.json` does not move. It is a registry with three readers and its `opening`
field is data, not an instruction; n8n resolves the row's `HOOK` to that string and sends it as
`hook_opening`. The adapter never reads the registry. This is the one `DownloadTemplate` call the
lane keeps: the prompt downloads are gone, the dataset read is not a prompt.

### D3. The draw lives in code in the adapter

`chooseDirectives({ variety, hookOpening, minWords, maxWords, random })` in `session-lib.mjs` is the
same weighted draw the Code node performs, with an injectable `random`, so the tests cover the
weights, the length target and the formatting without a model. It returns the four directive lines
and the band names.

The set is chosen once per post and stored in the session directory (`directives.json`) before the
draft turn. The review turn reads it from the same directory, so the gate judges the shape the
drafter was given rather than drawing a second one. A human retry in a later execution continues
`post-<row>` and reuses the stored set; a session that has been swept draws a fresh set and records
it, which is the one case where the directives can change between attempts.

Length is a point inside `[MIN_WORDS, MAX_WORDS]`, not a percentage of the maximum: the old Code
node's comment records that 40% of 300 falls below the 180-word floor, and the directives are
declared mandatory, so the model follows the contradiction down. The new function keeps that
arithmetic.

### D4. The HTTP boundary carries the old node shapes

A draft answers a plain-text body whose content is `<output>…</output>`, and a review answers
`<output>true|false</output><explanation>…</explanation>`. `read_post_answer` and
`read_check_answer` are Set nodes that map the HTTP node's body to `{ text }`, which is exactly the
item shape the two Code nodes already parse. `parse_llm_output` and `parse_llm_check_output` are
therefore untouched, and so are the retry edge, the bound and the publish answer.

Structured JSON would be cleaner at the adapter and would spread the change into both parsers, the
`switch_check_rules_llm` condition and the error text. Keeping the text contract means the only new
n8n behaviour is the two HTTP calls and their mapping.

### D5. The gate is a separate turn, and it receives the draft

`build_review_request` sends `{ session_id, lane: "post", task: "review", post: { text } }` with the
same `URL`, feedback and directives already in the session. Reviewing the text the caller passes —
not whatever the session last wrote — is the article lane's rule (`article` in the review request)
and it matters here for the same reason: the draft of record is the one n8n parsed, not one the
model remembers.

`ENABLE_CHECK=false` still skips the gate; the switch's pass output goes straight to `set_output`.

### D6. Retry stays a re-draft in the same session

`switch_check_rules_llm`'s retry edge now feeds `build_post_request`, which sends the gate's
`explanation` merged into `feedback` exactly as `download_post_prompt` did, plus the previous draft
and `attempt`. The session keeps the directives; the prompt's Reviewer Feedback block keeps its
`HIGHEST PRIORITY` precedence. `MAX_TRIES` is unchanged, so the bound's meaning (`n` drafts) is
unchanged.

### D7. No new address, no new environment variable

The adapter is reached at `ARTICLE_WRITER_URL`, the value n8n already has for the article lane. The
name is older than the second lane; renaming it would touch `datahub-local-core` for no behaviour,
so it stays and its documentation says it serves both. No values file changes: the session already
runs, and the post turn needs no allowlist because it fetches nothing.

### D8. Apply both graph copies and re-read

`linked_in_post_creator.workflow.json` carries the graph twice (`nodes` and `activeVersion.nodes`),
and this change removes nodes and edges. It is applied with `apply_workflow_changes.py --changes`
and `--require-edge` after each premise edge is confirmed, then re-read: both copies equal, the
workflow active, and the retired nodes absent from both. A `PUT` edits the draft only, so the
activate/re-read cycle is part of the task, not an optional check. No new test asserts the export
(owner rule); the live apply and the next run are the check.

## Flow

    n8n LinkedIn Post Creator
      set_workflow_vars          (MAX_TRIES, MODEL, ENABLE_CHECK, POST_TYPE, URL)
      parse_hook_registry        (datasets/hook_types.json → opening for the row's HOOK)
      build_post_request         POST { lane: "post", task: "draft", session_id: post-<row>, brief }
      request_post               → adapter renders prompts, draws directives, writes post.md
      read_post_answer           → { text: "<output>…</output>" }
      parse_llm_output           (unchanged: strip <output>, rewrite Source here)
      if_enabled_check
        build_review_request     POST { lane: "post", task: "review", post: { text } }
        request_review           → adapter renders the gate against the stored directives
        read_check_answer        → { text: "<output>…</output><explanation>…</explanation>" }
        parse_llm_check_output   (unchanged)
        switch_check_rules_llm   retry → build_post_request | pass → set_output | bound → set_error_max_tries
      set_output                 { text, omImage }

## Risks

- **Prompt fixes stop being live on push.** A wording change now waits for an image build and a
  digest pin. Mitigation: the prompt path is part of the adapter's tests, and the publish workflow
  already pins `sympozium_pi_writer`.
- **The variety draw can change between attempts** when the session directory is gone (PVC sweep or
  a long human pause). The gate then sees a different shape than the rejected draft had. Accepted:
  the alternative is a `content_queue` column for four lines of text, and a post whose shape
  changed after a week is not the failure this lane is fixing.
- **A draft that answers without `<output>`** is parsed by `parse_llm_output` as the whole text,
  which includes any prose the model wrapped around the post. The adapter's instruction requires the
  block; the article lane answers in the same shape and is the precedent.
- **`ENABLE_CHECK=false` skips a turn that used to be skipped** — no new risk, but the live check
  must exercise both values because the pass edge now bypasses a different node set.
- **The session is shared with articles.** A malformed post request that names no `lane` would be
  served as an article turn and fail on `article.text`; the lane field is required for post tasks
  and the adapter refuses an unknown combination by name.
- **`ARTICLE_WRITER_URL` is already proven on this deployment.** `article_creator` reads it in
  four request builders, and `article_content_writer` calls that sub-workflow in production; the
  post lane is reached from a different parent, but it is the same n8n deployment variable and the
  same `pi-writer` Service. The first post run still confirms the service is up with the new image.

## Open questions

- Whether `Source here: SOME_URL` should be rendered by the adapter (it knows the URL) instead of by
  `parse_llm_output`. Deferred: the parser is the existing contract and moving it would touch the
  publish path's `text` for no benefit.
- Whether the directives should be persisted on the row (a `VARIETY` column) so a resumed approval
  and the image prompt read the same set. Deferred to a change that gives the image lane a reason to
  read them; today only the gate needs them.
- Whether the review turn should run with `--no-tools`. It does by construction because the session
  has no tools configured for the post lane; if the article lane's tool toggling later becomes
  per-turn, the post must stay on the no-tools side.

## Definition of Done

- `pi-writer` serves `lane: "post"` with `draft` and `review`, renders the six post prompts from its
  own directory, and leaves every article task and prompt byte-identical.
- The post creator's export has no `@n8n/n8n-nodes-langchain` node and no prompt `DownloadTemplate`
  call (the hook registry is the remaining one); `parse_llm_output` and `parse_llm_check_output` are
  unchanged in both copies.
- `LinkedIn Post Sharing` passes `ROW_NUMBER` on the creator call in both copies, so the session is
  `post-<row>` rather than a value derived from the URL.
- A draft is retried when the gate answers `false`, and the gate's explanation is in the next
  attempt's Reviewer Feedback block.
- `ENABLE_CHECK=false` publishes the first draft through `set_output`.
- The variety draw is covered by tests with a seeded `random`: weights, the length target inside the
  range, the hook opening line, and the same set returned for the review.
- The adapter's article tests and `openspec validate --all` pass.
- **[UNVERIFIED] until live:** one row drafted, gated and approved, and one row whose first draft is
  rejected with a reason the next attempt carries; both read from the live execution.
