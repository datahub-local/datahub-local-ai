# Design

## Gate findings

- Pi compacts inside a process before an assistant response when `estimate > window - reserve`.
  Its default reserve is 16,384, so the first resumed request of a long session is not compacted.
- The compaction's own request carries the same history, so compaction cannot rescue a session
  that is already over the window: the trigger has to fire while there is room for it. That is why
  the fix is a trigger, not a post-turn repair.
- `context_edit` entries invalidate Pi's cached token estimate and force a character-based
  re-estimate, which is why a session can pass the threshold check and still overflow the
  gateway's own tokenizer. A trigger at 150k leaves ~112k of headroom over that error.

## D1 — Pi's compaction, wired through settings.json

`agentSettings` already writes the file Pi reads for idle timeout and retries. Adding `compaction`
there needs no new process, no extra model call from us, and no caller change. Rejected: writing a
compaction entry ourselves (a hand-built summary and a `systemMessage` snapshot that Pi owns), and
rotating the session id per turn (loses the fetched corpus the review's fact check reads).

## D2 — The trigger is a token count, not a ratio

150,000 of 262,144 is 57%: enough room for a 16-page research turn (measured 217k before the fix,
which is why the trigger sits below it and Pi compacts mid-turn), and enough for the summariser's
own request. A ratio would move when the window changes; a token count is what the failure was
measured in.

## Risks

- Each compaction is one extra model call over up to 150k input. On a draft that scrapes heavily
  this can be a second call inside the 900 s turn.
- A single tool result larger than the trigger still lands in one request, because compaction runs
  between assistant responses. The 16-scrape budget keeps each result at page size, not corpus size.
- [UNVERIFIED] live: that Pi reads this block from settings.json and compacts at 150k. Verified
  here only that the file it is written into carries the values and that the schema accepts them.

## Definition of done

- `settings.json` from `agentSettings` carries `compaction.enabled: true` with the derived reserve.
- `node --test 'agents/adapters/pi-writer/test/*.test.mjs'` passes.
- The over-window transcript is out of the session path.
