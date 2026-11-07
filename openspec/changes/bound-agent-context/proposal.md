# Proposal

## Why

A session that runs for days reached a 346k-token prompt per step. Measured on
`ses_e61d7b831ffePwyJ7DgS3nv4aL`: 1.4 MB of effective context, 77% of it tool
results, with `n8n_get_workflow` dumps up to 55 KB each. The 73 MCP tool
definitions added about 32k to every prompt, and the default compaction threshold
is 425k of a 500k window. One compaction took the session from 424k to 82k, and
the rest of the day took it back to 381k.

## What Changes

- A session carries one issue, stated in the contract.
- An n8n workflow is read as `structure` or `filtered`, never `full`.
- The three MCP servers use Code Mode, the v2 default, so their schemas are
  discovered on demand instead of sent on every request.
- Compaction fires at 60% of the window and is summarized in the background.
- The reviewer returns one line per finding, at most five.

## Capabilities

`codeagent-instructions`.

## Out of scope

- The LiteLLM session-header pin and the upstream jitter. Both need a separate
  measurement before a change.
- Lowering the declared 500k window in LiteLLM.
