# Tasks

## 1. The drafting turn can see its budget

- [x] 1.1 Pass `brief.max_words` to the draft and improve turns as `PI_WRITER_MAX_WORDS`, per turn
      (`session-server.mjs`): the run directory outlives a row edit, so a file would go stale.
- [x] 1.2 Extend `bin/check-article.mjs` to print
      `WORDS: <n> of <limit> (budget <max>) — cut at least <k> words` and exit 1 past the limit,
      using `articleWordCount`/`articleWordLimit` — the gate's own functions — and print nothing
      when the turn carries no budget.
- [x] 1.3 `prompts/writing.md`, `prompts/article_task.md` and `prompts/article_improver.md`: run the
      check before answering, cut until inside the limit, and treat `wc -w` as a rough guide only.
- [x] 1.4 Install `ripgrep` in the adapter image, because `prompts/article_audit.md` tells the
      auditor `rg` is installed.
- [x] 1.5 Tests: `test/check-article.test.mjs` covers over the limit, inside the limit and no
      budget; `test/dockerfile.test.mjs` asserts the `ripgrep` install.

## 2. An asset write is scoped to its own row

- [x] 2.1 Set `matchType: allConditions` on `store_assets`, `mark_asset_approved`,
      `mark_asset_cancelled` and `record_asset_paths` in
      `agents/n8n/workflows/article_content_writer.workflow.json`.
- [x] 2.2 Apply the same four fields to the live workflow (execution verified: the read-back shows
      `allConditions` on each node and the workflow stayed active).
- [x] 2.3 Record the failure and the trap in `docs/agent/n8n.md`.

## 3. Gates

- [x] 3.1 `node --test 'agents/adapters/pi-writer/test/*.test.mjs'` passes.
- [x] 3.2 `openspec validate --all` passes.
- [x] 3.3 Rebuild and publish the `pi-writer` adapter image, then pin its digest in
      `agents/sympozium/values/default.yaml.gotmpl` before the prompt and `check-article` change
      reaches the cluster. `blocked by` the image pipeline (CI publishes on merge; the pin is the
      follow-up commit). **Landed 2026-11-10:** `eeccf02` changed `agents/adapters/pi-writer`, the
      publish run rebuilt and re-pinned the adapter, and `07a154f` carries the new digest
      (`sha256:f3dbca38…`) three minutes later.
- [ ] 3.4 Live check after the image is pinned: one drafting turn where the model is forced past the
      limit runs `check-article`, cuts the body, and the gate accepts the answer in the same attempt.
      `[UNVERIFIED]` until the image is deployed.
