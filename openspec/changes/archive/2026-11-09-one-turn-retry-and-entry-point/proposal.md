# Proposal

## Why

`author-one-turn-and-verify-names` removed the aspect pass and the edit from the automatic path,
but two requirements still prescribed them: the entry point was told to call `Article Creator` with
`aspects` and `improve`, and a human retry was told to re-enter the improvement pass. Left as they
were, the spec and the graph disagree, and the next change would follow the spec back into the
three-turn loop this one removed.

## What Changes

- **A human retry re-drafts.** `switch_article_retry` calls `Article Creator` with `TASK: draft`
  again, carrying the draft the person read and their feedback; the draft is authored in a session
  of its own, not edited in the one it replaced.
- **The entry point passes `draft` only.** `aspects` and `improve` stay valid adapter tasks for
  on-demand use; the lane does not pass them.
- **The obsolete retry rules go.** The feedback-round exceptions (an unverified block allowed
  because a person asked, a ledgered block still failing) described a rule the ledger no longer
  has: a block is verified by its names, on any round.

## Capabilities

- `content-writer`

## Impact

- `openspec/specs/content-writer/spec.md` only: two requirements removed, two issued in their
  place. The graph and the adapter already behave this way.

## Non-goals

- No code change, no workflow change.
