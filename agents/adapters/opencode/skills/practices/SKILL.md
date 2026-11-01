---
name: practices
description: How to shape, test, debug and land a change in these repositories. Load before the first edit of a task, and again before opening the pull request.
---

# Practices

The rules behind the contract. The contract states the four that never move; this
is the rest, in the order a change meets them.

## The shape of a change

- The smallest diff that makes the issue true. If a smaller version exists, it is
  the one to write.
- Delete before you add, and reuse the pattern the repository already has before
  inventing a second one.
- Never rewrite working code to improve it. No speculative abstraction, no new
  dependency or config knob where the standard library or the repository already
  does the job, no compatibility shim, deprecated alias or version guard. One
  version runs.
- Nothing outside the issue: no rename, reformat, dependency bump or "while I was
  here" fix. It is its own issue, named in the report.
- When two repositories must move together, change one here and report the other
  with the exact change it needs. A lockstep commit across repositories is not one
  change.

## Tests

- Write the failing test first, or at least watch it fail before the code exists.
  A test that has never been red proves nothing about the bug you are fixing.
- One behaviour per test, named after the behaviour. If the name needs "and", it is
  two tests.
- Assert what the code does, not what a stub did. A test that only proves a mock was
  called will pass while the behaviour is wrong.
- Tests cover behaviour, never configuration. No test over a YAML value, a chart
  option, a prompt's wording or a file's presence: it duplicates the file and fails
  the next legitimate edit. Where the change is configuration, the repository's
  render or build gate is the check.
- Run the project's whole suite before you call it done, not only the file you
  touched. A failure you saw and did not mention is a report falsified by omission.

## Debugging

- Read the error before anything else: the message, the stack, the line. The answer
  is often already there.
- Reproduce it first. A fix without a reproduction is a guess, and a guess you
  cannot check.
- Check what changed: `git log`, `git diff`, a new dependency, a value someone
  edited.
- One hypothesis, stated, tested with the smallest possible change. Not several
  fixes at once, because then nothing tells you which one worked.
- A fix gets a test that fails without it. The reproduction is that test.
- After two failed fixes, stop guessing and say so. After three, the design is
  wrong: report it instead of trying a fourth.

## Git

The commit format, the types, the scopes and the body rule are in the `change-shape`
skill. This adds only what it does not say:

- Branch from an up-to-date `main`, one branch per issue,
  `type/<issue>-<topic>`. Never branch from another feature branch.
- Stage the paths you touched. `git add -A` sweeps someone else's work into your
  commit.
- A generated file is not hand-edited: a lockfile, `site/`, a bundle zip, a pinned
  digest. Change the source, run the generator, commit its output.
- Never force-push, never rewrite published history, and never commit a secret: if
  one reaches a commit, say so instead of amending it away.

## Comments and docs

The per-repository rules are in the `change-shape` skill: YAML and helmfile carry
no prose, Python and shell keep a non-obvious why. In all of them:

- One line, the constraint, the trap or the incident. A comment restating the code
  is noise, and what the file used to be is the log's job.
- Documentation states the fact once. No page restating another page's table, no
  narration of how the fact was found, no changelog in prose.
- A stale comment or path is worse than none: when you move what a comment points
  at, grep the repository for the old path.

## Before you open the pull request

1. Read your own diff end to end, as if reviewing someone else's. Everything in it
   belongs to the issue, and nothing in it is a leftover.
2. Remove what does not ship: debug prints, scratch files, commented-out code, a
   widened log line. Leave nothing in the tree that you would flag in review.
3. Run the gate. Not the test file, the gate.
4. Write the body: why, what, the checks with their results, and `Refs` or `Closes`
   as the taskboard skill says.
5. Say what you did not verify. `[UNVERIFIED]` and a reason beats silence.

## When you are stuck

- Twelve tool calls without a concrete step forward: stop and report the blocker.
  A longer turn without progress spends tokens and buries the cause.
- A documented command that fails is a finding. Report the discrepancy; do not
  invent a private workaround the next session will not know about.
- Ask when the decision is the owner's, once, with options. Everything else is
  yours to decide and to report.
