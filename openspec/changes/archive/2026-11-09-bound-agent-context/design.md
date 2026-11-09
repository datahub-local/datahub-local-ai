# Design

## Decisions

- **Code Mode, not a trimmed server list.** `codemode` defaults to true in
  OpenCode v2.2.5 and the config was opting out. Code Mode keeps the definitions
  out of each request and lets a call filter a large result before it enters the
  context. Removing the n8n server would save the same tokens and lose the tools.
- **The default reserve, not a tighter cap.** A lower threshold compacts more
  often, rewrites the prompt prefix and summarizes the previous summary; each
  round loses detail. One issue per session is the real bound.
- **Background compaction.** The automatic summary is a 424k-token request that
  blocks a turn. Producing it as the threshold approaches keeps it off the
  critical path.
- **A terse reviewer.** Its report returns into the parent session, so its length
  is context the next turn pays for.

## Risks

- Code Mode changes how a tool is called: the agent calls it through `execute`.
  The generated catalogue states the call shape.
- `background_compaction` is experimental. It is one key to remove if it misbehaves.
