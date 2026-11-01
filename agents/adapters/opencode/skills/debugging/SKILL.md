---
name: debugging
description: How to find a cause before changing code, and when to stop guessing. Use on any failing test, build, render, request or unexpected behaviour.
---

# Debugging

A fix without a reproduction is a guess, and a guess you cannot check.

## Find the cause first

1. Read the error completely: message, stack, file and line, exit code. The answer
   is often already in the line you skipped.
2. Reproduce it. Reliably, with the exact command, before touching anything. What
   you cannot reproduce, you cannot fix.
3. Check what changed: `git log`, `git diff`, a new dependency, an edited value, a
   different environment. Most failures are recent.
4. In a multi-part system, find which part fails before proposing a fix. Add one
   reading at each boundary, run once, and let the evidence pick the layer.

## Then change one thing

- State one hypothesis and test it with the smallest possible change. Several fixes
  at once tell you nothing about which one worked.
- If it did not work, form a new hypothesis. Do not stack a second fix on the first,
  and do not leave the first one in.
- The fix gets a test that fails without it. A bug fixed without a reproduction comes
  back.
- Fix the cause, not the symptom. A guard around a wrong value hides the code that
  produces it.

## When to stop

- Two failed fixes: stop and re-read the evidence. You are probably fixing the wrong
  layer.
- Three failed fixes: the design is wrong, not the code. Report it with what you
  tried and what each attempt showed; do not try a fourth.
- Twelve tool calls without a concrete step forward: report the blocker instead of
  exploring further.
- A documented command that fails is a finding. Report the discrepancy rather than
  inventing a private workaround the next session will not know about.

## What not to do

- Do not widen a log line, add a `sleep`, retry more, or catch the error, to make the
  symptom go away.
- Do not skip the failing test, loosen the assertion or disable the check.
- Do not report a cause you inferred from a name or a comment. A cause is a reading
  you saw.
