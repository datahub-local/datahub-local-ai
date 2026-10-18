# Tasks

## 1. Set the budget

- [ ] 1.1 Set `options.timeout: 120000` on every `@n8n/n8n-nodes-langchain.lmChatOpenAi` node in
  every export, both graph copies — twelve nodes across six workflows (`article_creator`,
  `content_feed_curator`, `image_content_generator`, `linked_in_image_creator`,
  `linked_in_post_creator`, `visual_studio`).
- [ ] 1.2 Leave `maxRetries` alone, and record in the design that it multiplies with the timeout.

## 2. Offline gate

- [ ] 2.1 Add `agents/n8n/scripts/test_model_timeouts.py`: sweep every `*.workflow.json`, both graph
  copies, and assert every `lmChatOpenAi` node carries `options.timeout >= 120000`, naming the file
  and node on failure. It must also assert it found the nodes at all, so an empty sweep cannot pass.
- [x] 2.2 Prove it fails without the change: revert the exports, run, record how many nodes it names,
  restore.
  **Landed.** With the exports at HEAD, `test_every_model_node_waits_for_the_gateway_failover` names
  **all 24 instances** (`timeout=None`), while `test_the_sweep_finds_the_model_nodes` still passes —
  which is what that second case is for. Restored: both pass.
- [x] 2.3 Run the gates and record the result: the new file, `test_workflow_invariants.py`,
  `test_code_nodes_parse.py`, then the whole `agents/n8n/scripts/` suite and `ruff`.
  **Landed.** Full suite **574 passed, 1 skipped** (the skip is the concurrent board-intake
  change's create body, not this one). Every export's two graph copies agree. `openspec validate
  --all` 15 passed. `ruff` reports one error, pre-existing and unrelated (`FURB167` in
  `test_visual_studio_registry.py`).

## 3. Apply to the live instance

- [ ] 3.1 Ask the owner before writing, presenting the sweep and the six workflow names.
- [x] 3.2 Apply all six with `--changes` and `--require-edge` on each model node's own edges, then
  re-read each and diff against its export.
  **Landed 2026-10-18.** All twelve guards held — the model nodes' outgoing edges across
  `ai_languageModel` to their consumers — and all twelve writes landed. Re-read: no parameter,
  connection or setting differs from any export, and each node's timeout reads back `120000`.
  `article_creator` and `content_feed_curator` differ only in node **positions**, which the editor
  owns.
- [x] 3.3 Confirm each workflow's `active` state is unchanged — the entry point is `active: False`
  by design, the rest are active.
  **Landed.** All six stayed `active: True` (`Article Creator`, `Content Feed Curator`,
  `Image Content Generator`, `LinkedIn Image Creator`, `LinkedIn Post Creator`, `Visual Studio`) and
  each PUT republished on its own, so the published versions carry the timeout. The entry point is
  not among the six — it has no model node of its own; it calls `Article Creator`.

## 4. Documentation

- [x] 4.1 Record in `AGENTS.md`: the model nodes' 120 s budget and why the client must exceed the
  gateway's per-attempt timeout, beside the existing note that the gateway's failover is what the
  budget is for.
  **Landed** as an eighth bullet in *structural things worth knowing before editing an export* (the
  count in that sentence was updated too), carrying the default, the failover reasoning, the sweep,
  the `maxRetries` multiplication and the gateway-side setting that is not this repository's.
- [ ] 4.2 Archive when the six graphs are live and 2.1–2.3 have run:
  `openspec archive raise-the-model-request-timeout`.
