# Design

## Context

- The installed node, read off the running image
  (`.../n8n-nodes-langchain/dist/nodes/llms/LMChatOpenAi/LmChatOpenAi.node.js`):
  ```js
  { displayName: 'Timeout', name: 'timeout', default: 60000,
    description: 'Maximum amount of time a request is allowed to take in milliseconds', type: 'number' },
  ```
  and it is applied twice — `configuration.fetchOptions.dispatcher = getProxyAgent(baseURL,
  { headersTimeout: timeout, bodyTimeout: timeout })` and the LangChain client's own `timeout`.
- The twelve model nodes in the committed exports, all `lmChatOpenAi`, none with a `timeout`:
  `article_creator` (`ai_model`, `ai_model_fallback`), `content_feed_curator` (both),
  `image_content_generator` (`OpenRouter Chat Model`, `… Fallback`), `linked_in_image_creator`
  (both), `linked_in_post_creator` (both), `visual_studio` (both). Their `options` carry
  `maxRetries` only — 5 in the article, curator and post lanes, 2 in the image and studio ones — and
  `{}` on the two OpenRouter nodes.
- The HTTP nodes in the same exports do carry timeouts, chosen per call: 15000–30000 ms for probes,
  120000 ms for a presign, 300000 ms for GitHub/S3, 600000 ms for an asset download, 1200000 ms for
  `execute_author`.
- Execution 13975 (2026-10-18): `check_article_llm` answered
  `litellm.Timeout: Timeout passed=30.0, time taken=30.347 seconds` and the fallback then answered
  `Model does not support this protocol`, so the run ended. The 30 s there is LiteLLM's own request
  timeout, not n8n's — a `datahub-local-core` setting — which is why the client budget has to be the
  larger of the two.

## Gate findings

- **The client budget must exceed the gateway's whole failover, not one attempt.** LiteLLM spends its
  own timeout on the primary and then tries the fallback. A client timeout equal to the gateway's
  per-attempt timeout aborts during the failover, so the client is always the one that decides the
  call failed — the opposite of what the fallback chain is for. 120 s is the top of the range the
  owner named and leaves room for a 30 s primary plus a 30 s fallback plus overhead.
- **The value is set per node, because nothing else carries it.** The `openAiApi` credential has no
  timeout field and there is no instance-wide default for it, so a policy has to be written into each
  node — which is why the offline case is a sweep over every export rather than a check of one.
- **A test that sweeps the exports is the only guard that scales.** Twelve nodes across six files,
  each in two copies: a per-file assertion would be six copies of the same rule, and a new workflow
  would silently be exempt.
- **`maxRetries` multiplies with it.** The node's own retries are the OpenAI client's, so a hung call
  now costs up to `timeout × (maxRetries + 1)`. Left as it is — the failover is the point — but
  recorded, because a run that hangs for twelve minutes looks like a different bug from one that
  fails fast.

## Decisions

- **D1 — `options.timeout: 120000`** on every `lmChatOpenAi` node, both copies.
- **D2 — a new `model-request-budget` capability** rather than a delta on one lane, because the rule
  is identical for all six workflows.
- **D3 — the offline case sweeps every `*.workflow.json`**, both copies, and asserts a floor rather
  than equality, so raising one node further is allowed and lowering one is not.

## Risks / Trade-offs

- **A hung gateway now occupies a node for longer.** Against a `runTimeout` of an hour on the article
  lane and `executionTimeout: 3600` on the entry point, twelve minutes is affordable; on a shorter
  budget it would not be. The trade is deliberate: the old behaviour was a run lost to a failover it
  never waited for.
- **The two OpenRouter nodes get the same value.** They are the same node type behind a different
  credential and a different base URL, and the rule is about the client, not the provider.
- **This does not change the gateway.** LiteLLM's own timeout stays a `datahub-local-core` setting;
  if it is what aborts a call, raising the client only makes the abort later and better reported.

## Open Questions

- **Whether `maxRetries` should come down as the timeout goes up.** Five retries at 120 s is twelve
  minutes for one node. Not measured; the next run that hangs will say.
- **Whether the gateway's 30 s timeout should be raised instead.** It is the tighter of the two, and
  it lives in another repository. Worth raising there if failovers keep being cut short.

## Definition of done

- `openspec validate --all` passes with this change present.
- `agents/n8n`'s offline suite passes, and the new case fails without the change (twelve nodes below
  the floor).
- Every export's two graph copies agree.
- All six graphs applied live with `--require-edge`, read back, and the exports diffed against live.
