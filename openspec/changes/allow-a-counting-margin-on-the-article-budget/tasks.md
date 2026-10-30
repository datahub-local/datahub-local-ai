# Tasks

## 1. The gates

- [x] 1.1 `article_creator.workflow.json`, `parse_article`: compute `limit = Math.ceil(max * 11 / 10)`,
  reject past it with `OVER_BUDGET: <n> words against a limit of <limit> (MAX_WORDS=<max>)`, and
  emit `WORD_LIMIT`. Both graph copies.
- [x] 1.2 `article_content_writer.workflow.json`, `check_improved_draft`: the same margin and the
  same message. Both copies.
- [x] 1.3 `article_creator.workflow.json`, `download_article_review_prompt`: pass
  `WORD_LIMIT` from `parse_article`. Both copies.

## 2. The prompt

- [x] 2.1 `agents/n8n/prompts/article_review.md`: the length check and the draft's budget line read
  `{{ WORD_LIMIT }}`, with `{{ MAX_WORDS }}` kept as the row's budget so the two numbers cannot be
  confused. Pushed **after** 1.3 is applied live.

## 3. Tests

- [x] 3.1 `scripts/test_article_review_gate.py`: executing `parse_article`, a body at the limit is
  accepted and one word past it is rejected naming the limit.
- [x] 3.2 `scripts/test_article_entry_point.py`: the twin test's fixtures include the boundary, so
  the drafting gate and the improvement re-check cannot disagree on where it is.
- [x] 3.3 `scripts/test_article_review_gate.py`: the reviewer's length check names `WORD_LIMIT` and
  the node supplies it — a reviewer enforcing `MAX_WORDS` would reject what the code accepts.

## 4. Verification

- [x] 4.1 `uv run pytest` in `agents/n8n` (or the targeted files with `node` available),
  `python3 -m pytest scripts/test_article_prompts.py`, and `openspec validate --all`.
- [ ] 4.2 Live: apply the two graphs with `scripts/apply_workflow_changes.py`, then push the prompt.
  [UNVERIFIED] until done — nothing offline covers the running instance.
