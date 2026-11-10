# Proposal

## Why

`LinkedIn Post Creator` is the last lane where n8n holds the model. Its two turns are
`@n8n/n8n-nodes-langchain` nodes — `create_post_ai` drafts and `check_rules_llm` gates — and every
word they read is assembled by seven `DownloadTemplate` calls at run time
(`linkedin_post.md`, `linkedin_post_system.md`, `linkedin_post_rules.md`,
`linkedin_post_review.md`, `linkedin_variety.md`, `ai_speak.md` and `datasets/hook_types.json`).
The article lane already left that shape: `Article Creator` posts a `brief` to the `pi-writer`
`HarnessSession` and gets its prose back, and the adapter renders every prompt from its own image.

Two things follow from the split. First, the rule pair that the gate and the drafter must share —
the AI-speak list, the subject/attribution rules, the variety directives — lives in two files that
have to change together, and a wording fix is only as good as the next run that fetches both.
Second, the selection of the variety directives is code in a Code node (`set_variety_directives`)
while the options it reads are a prompt file fetched at run time, so the draw, the registry lookup
and the text the model reads are three owners. The AGENTS prompt policy already forbids the shape:
every instruction a model reads belongs in a prompt file the adapter renders, not in a model node,
an HTTP body or a Code node.

The post is short and the source text already arrives as `CONTENT`, so this is not the article
lane's research problem. It is an ownership problem: one adapter, one prompt directory, one place
where a draft and its gate cannot disagree.

## What Changes

- **Both model turns become writer-session turns.** `create_post_ai` and `check_rules_llm` are
  replaced by HTTP calls to the existing `pi-writer` session. A request names `lane: "post"` and
  `task: "draft"` or `"review"`; the source text, feedback, previous post, word range and resolved
  hook opening ride on the brief as values.
- **The post prompts move into the adapter image.** `linkedin_post.md`, `linkedin_post_system.md`,
  `linkedin_post_rules.md`, `linkedin_post_review.md`, `linkedin_variety.md` and `ai_speak.md` move
  to `agents/adapters/pi-writer/prompts/` and are deleted from `agents/n8n/prompts/`. n8n sends no
  prompt text.
- **The adapter owns the variety draw.** It selects the format, length band and closing from the
  weighted sets in its own `linkedin_variety.md`, formats the hook opening into the directive block,
  and keeps the chosen set for the session so the gate judges the shape the drafter was given.
- **The gate is a session turn with the same verdict.** It answers
  `<output>true|false</output>` plus `<explanation>`, so `parse_llm_check_output`, the
  `switch_check_rules_llm` routing and `MAX_TRIES` are untouched.
- **The draft keeps the `<output>` shape.** `parse_llm_output` still strips the block and rewrites
  `Source here: SOME_URL`, so the publish path sees the same `text`.
- **No research tools.** The post session receives the source text in the brief. It is not given
  Firecrawl, the source proxy or an allowlist; a post that needs a page re-read is a caller bug.
- **The n8n contract does not move.** Trigger inputs, `ENABLE_CHECK`, the retry loop, the error
  path and the `text` / `omImage` answer stay as they are. Only the prompt-download chain and the
  two model nodes change.
- **The hook registry stays in n8n.** `datasets/hook_types.json` has three readers (curator, post
  generator, image creator) and is data, not prompt text; n8n resolves the row's `HOOK` to its
  `opening` and sends that value. It is the only `DownloadTemplate` call left in the lane.

## Capabilities

### Modified Capabilities

- `linkedin-post-publishing`: the lane's drafting and review turns run in the writer session, the
  session owns the prompts and the variety directives, and the gate judges the draft against the
  directives the drafter was given.

## Impact

- `agents/adapters/pi-writer/` — `lane` routing, the post prompt set, the variety draw and the
  review turn; the article tasks and their prompts are unchanged.
- `agents/n8n/workflows/linked_in_post_creator.workflow.json` — both graph copies: the prompt
  chain and the two model nodes replaced by `build_post_request` → `request_post` →
  `read_post_answer` and `build_review_request` → `request_review` → `read_check_answer`.
- `agents/n8n/prompts/` — the six post-lane files deleted after their bodies move.
- `docs/agent/n8n.md` (the post lane section and the hook registry paragraph),
  `agents/adapters/pi-writer/README.md`, `AGENTS.md` (the prompt-policy example).
- `datahub-local-core` — **no change expected**: the post lane reuses the existing
  `ARTICLE_WRITER_URL` and the `pi-writer` Service. The variable is already read by `article_creator`
  (its `request_article` / review / aspect / improve nodes) and exercised in production by
  `article_content_writer`, which calls that sub-workflow.
- `linked_in_post_sharing.workflow.json` — both graph copies gain `ROW_NUMBER` on the
  `execute_post_creator` call so the session id is `post-<row>`; nothing else on the publish side
  changes.
- `LinkedIn Image Creator`, `Visual Studio`, `Content Feed Curator`, `workflows/airflow`,
  `workflows/dbt` — untouched.

## Non-Goals

- No panel or hook changes: `datasets/hook_types.json` and the curator's judge stay as they are.
- `linkedin_post_classify.md` is already retired (`classify_content` no longer runs); it is not
  resurrected here and is not part of the move.
- No research or fetch capability, no new HarnessSession, no new image, no new PVC.
- No change to the post's publish side (video/image upload, Slack approval).
