# Tasks

## 1. `Article Creator`

- [x] 1.1 Add `TASK`, `DRAFT_TITLE`, `DRAFT_TEXT`, `FINDINGS` and `PROBLEM` to the trigger.
- [x] 1.2 `set_workflow_vars` normalises `TASK` and defaults it to `draft`.
- [x] 1.3 Add `switch_task` with `aspects`, `improve` and `draft` rules and an extra output.
- [x] 1.4 Move `build_aspects_request` and `request_aspects` in; return the answer through
  `pass_aspects_answer`.
- [x] 1.5 Move `build_improve_request` and `request_improve` in; return the answer through
  `pass_improve_answer` and carry `FINDINGS`/`PROBLEM` from the trigger.
- [x] 1.6 `bad_task` fails an unimplemented task instead of drafting.

## 2. `Article Content Writer`

- [x] 2.1 Replace `build_aspects_request` → `request_aspects` with `execute_article_aspects`.
- [x] 2.2 Replace `build_improve_request` → `request_improve` with `execute_article_improve`.
- [x] 2.3 Map the draft of record, the merged findings and the retry problem into the calls.
- [x] 2.4 Drop the writer URL and session id from `build_improvement_context`.
- [x] 2.5 Rewire `if_has_findings` and `switch_improved_ok` to the new nodes.

## 3. Documentation

- [x] 3.1 `docs/agent/n8n.md`: the `TASK` switch, the sub-workflow boundary and the moved
  request nodes.

## 4. Gate

- [x] 4.1 Workflow invariants on both exports: names, references, reachability, mirrored
  `activeVersion`, Code-node syntax.
- [x] 4.2 `openspec validate --all`.

## 5. Deployment (reported separately)

- [ ] 5.1 Apply both graphs live and compare each to the committed export.
- [ ] 5.2 Run one article row through the entry point. [UNVERIFIED] until then.
