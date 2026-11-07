# Design

## D1 — `TASK` on the existing trigger

`Article Creator` already receives the entry's fields through `executeWorkflowTrigger`. The turn
is one more field, not a second sub-workflow: `TASK` selects `draft`, `aspects` or `improve`, and
the default keeps every existing caller drafting.

Rejected: a separate `Article Writer Turns` sub-workflow called twice by the entry point. It
duplicates the session id, the endpoint and the brief mapping that the creator already holds, and
leaves the lane with two sub-workflows to deploy and keep in step.

## D2 — The branch returns the adapter's answer unchanged

`request_aspects` and `request_improve` are HTTP nodes with `neverError`, `fullResponse` and
`continueErrorOutput`; both outputs meet a `noOp`, which returns the item as the sub-workflow's
answer. `merge_aspect_findings` and `check_improved_draft` therefore see the same
`statusCode`/`body` on a sub-workflow call as they saw on a direct HTTP call, and a transport
failure still arrives as an `error` item rather than a missing answer.

Rejected: parsing the answer inside the sub-workflow and returning `findings`/`article`. The code
gates are the entry point's half of the contract; moving them would make `Article Creator` decide
what the lane accepts.

## D3 — An unknown task fails

`switch_task` has three rules and an extra output wired to `bad_task`, which throws the task's
name. A typo must not fall through to a draft: a silent draft spends a model call and hides the
caller bug behind a plausible article.

## D4 — The draft of record crosses the boundary as fields

For `aspects` and `improve`, the entry point passes `DRAFT_TITLE` and `DRAFT_TEXT`; for `improve`
it also passes `FINDINGS` and, on a retry, `PROBLEM`. The sub-workflow never reads the entry
point's nodes, and the entry point never reads the writer's session directory.

## D5 — The entry point owns the gates, the creator owns the requests

Word budget, asset markers and ledger fidelity stay in `merge_aspect_findings`,
`check_improved_draft` and `select_final_draft`. The sub-workflow builds and posts the request and
returns what the adapter answered. The split is the one the draft path already uses:
`execute_article_creator` posts, `parse_article` and `merge_article_verdict` judge.
