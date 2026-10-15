# Design

## Context

`parse_registry` maps each requested id through `visual_types.json`. An id the registry
does not declare becomes `{STATUS: 'UNKNOWN', ERROR: 'unknown asset type: <id>'}`, and one
marked `available: false` becomes `{STATUS: 'UNAVAILABLE', ERROR: <reason>}`; both carry
`AUTHOR: null`, deliberately, so the type does not take its author branch and "falls
through to the report path with a STATUS and reason" (`parse_registry`'s own comment).

The report path is `if_agent` false → `if_raster` false → `ready_pass` → `merge_branches`
→ `set_result`. `merge_branches` gathers the three ways an asset can be finished: an
authored one (`agent_result`), a raster one (`raster_result`), and a never-authored one
(`ready_pass`).

## Gate findings

- **The report path did not survive its last hop.** `connections.if_raster.main[1]` was
  `{"node": "ready_pass", "type": "main", "index": 2}`. `ready_pass` is a
  `n8n-nodes-base.noOp`, whose node type declares exactly one input.
- **n8n accepts an input index the node does not have.** `NoOp.execute()` is
  `return [this.getInputData()]` (read from the installed image, n8n 2.43.3), and the
  engine pads the inputs a node was not given with `[]` before running it, so the node
  runs reading input 0 and emits nothing. Verified in execution 13464: `if_raster`
  output 1 carried one item and `ready_pass` recorded `{"main": [[]]}`.
- **Nothing downstream could recover.** With input 2 empty, `merge_branches` never ran
  (absent from `runData`), `set_result` never ran, and the parent's
  `execute_visual_studio` emitted 0 items — a node that emits nothing takes its whole
  chain with it, the same failure AGENTS.md records for the studio's removed
  `prepare_uploads` chain.
- **The guard the caller already has was unreachable, not missing.**
  `check_animation_result` answers `ASSET_STATUS: 'MISSING'` with
  `ERROR: 'animated media unavailable: no asset returned'` for an absent asset, and
  `if_animation_ok` branches on that `ERROR`; a Code node cannot run on zero items, so
  none of it was reached.
- **No invariant covered it.** `test_workflow_invariants.py` checked that both copies
  agree, that names are unique, that no node is isolated, that references resolve and
  that called workflows exist — no check on where an edge lands.
- **Only one such edge exists in the repository**, in both copies of this export. Every
  other index above 0 is a `merge` target or an `ai_*` sub-node slot.

## Decisions

- **Fix the edge, not the caller.** The caller's contract — read the asset of the type
  requested, fall back when it says it failed — is already right, and the studio's answer
  is already built by `set_result` (`STATUS: FAILED` when every asset carries an error).
  Rewiring the caller around an empty result would be a second place that has to know
  what an empty answer means.
- **Assert the invariant, not this connection.** A test naming `ready_pass` would pass
  forever after the next graph edit re-introduces the same class somewhere else. The
  check is "a `main` edge onto input index > 0 must target a node type that takes more
  than one input", with the multi-input types named once.
- **Leave `ai_*` edges out of the invariant.** A sub-node slot is addressed above 0 by
  design (a chain node's model input is its second input), and enumerating LangChain
  types to say so is a list that drifts for nothing.
- **Keep the reported reason as it is.** `UNKNOWN` and `UNAVAILABLE` both answer with an
  asset carrying `ERROR`; the caller already treats a non-empty `ERROR` as the failure.

## Risks

- The added invariant's multi-input list is a small copy of n8n's node metadata. A type
  added later that takes two `main` inputs would fail the test until it is listed — a
  loud false positive, which is the direction to fail in.
- Live, the fix changes nothing for the two paths production uses (`agent_result` and
  `raster_result` both feed input 0); it restores a path only an unresolvable type takes.
  So the fix cannot be confirmed by ordinary traffic — the confirmation is the edge
  itself being read back, plus a probe that requests a type the registry does not declare.

## Open questions

- Whether `available: false` should be reached through the author branch with a
  short-circuit reason instead of through the never-authored path. Not decided here.

## Definition of done

- Both copies of the export route `if_raster` output 1 to `ready_pass` input 0.
- `test_no_edge_targets_an_input_the_node_does_not_have` fails against the pre-change
  export and passes after.
- `pytest agents/n8n/scripts/` and `ruff check` pass.
- Applied live with `--require-edge`, re-read and diffed against the export.
- `openspec validate fix-studio-unresolvable-type-result` passes.
