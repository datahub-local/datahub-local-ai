# Proposal

## Why

Every model node in this repository runs on n8n's default request timeout. `lmChatOpenAi`'s
`options.timeout` defaults to **60000 ms** (read off the installed image:
`LmChatOpenAi.node.js` line 543), and none of the twelve model nodes in these exports sets it — they
set `maxRetries` and nothing else. The gateway they call is LiteLLM with a **fallback chain**, so a
primary that stalls is not a failed call: the gateway waits on it, then fails over, and the total can
run 60–120 s. At 60 s the client gives up first, which turns a recoverable failover into
`litellm.Timeout` on the node — exactly what ended execution 13975's reviewer turn (a 30 s timeout
that took the whole article run with it, and the reason `check_article_llm` now retries).

The HTTP nodes in these same exports already carry deliberate timeouts — 300000 ms for GitHub and S3,
600000 ms for an asset download, 1200000 ms for the composer's authoring call — so the model nodes
are the outlier, not the rule.

## What Changes

- Every `@n8n/n8n-nodes-langchain.lmChatOpenAi` node in every export sets
  `options.timeout: 120000`, the top of the failover budget, so a primary that stalls for the
  gateway's own timeout still leaves room for the fallback to answer.

Not changed: `maxRetries`, the models, the credentials, the gateway (its 30 s internal timeout is a
`datahub-local-core` LiteLLM setting), and the HTTP nodes' timeouts.

## Capabilities

### New Capabilities

- `model-request-budget`: how long a model call may take before the client abandons it, across every
  n8n workflow in this repository. It is a new capability rather than a delta on one lane because the
  rule is the same for all six workflows that call a model, and each of them would otherwise carry
  its own copy of it.

### Modified Capabilities

<!-- None. No lane's behaviour changes except how long it waits. -->

## Impact

- **Six exports, twelve model nodes, both graph copies**: `article_creator`,
  `content_feed_curator`, `image_content_generator`, `linked_in_image_creator`,
  `linked_in_post_creator`, `visual_studio`.
- Live apply needed for all six.
- **A cost note**: the node's own `maxRetries` (2 or 5) multiplies with this. A hung call with
  `maxRetries: 5` can now occupy the node for up to twelve minutes before it gives up, against six at
  the old default. That is the intended trade — the gateway's failover is what the budget is for —
  but it is the number to watch if runs start hanging instead of failing.
