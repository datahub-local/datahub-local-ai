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
- [ ] 2.2 Prove it fails without the change: revert the exports, run, record how many nodes it names,
  restore.
- [ ] 2.3 Run the gates and record the result: the new file, `test_workflow_invariants.py`,
  `test_code_nodes_parse.py`, then the whole `agents/n8n/scripts/` suite and `ruff`.

## 3. Apply to the live instance

- [ ] 3.1 Ask the owner before writing, presenting the sweep and the six workflow names.
- [ ] 3.2 Apply all six with `--changes` and `--require-edge` on each model node's own edges, then
  re-read each and diff against its export.
- [ ] 3.3 Confirm each workflow's `active` state is unchanged — the entry point is `active: False`
  by design, the rest are active.

## 4. Documentation

- [ ] 4.1 Record in `AGENTS.md`: the model nodes' 120 s budget and why the client must exceed the
  gateway's per-attempt timeout, beside the existing note that the gateway's failover is what the
  budget is for.
- [ ] 4.2 Archive when the six graphs are live and 2.1–2.3 have run:
  `openspec archive raise-the-model-request-timeout`.
