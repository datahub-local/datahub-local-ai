---
name: ship-it
description: The last pass before a pull request: reading your own diff, leaving a clean tree, and what the body and the report must say. Use at the end of a task, before committing the last change and opening the pull request.
---

# Ship it

Everything below happens after the code works. It is the difference between a
branch and a reviewable pull request.

## Read your own diff

1. `git diff main...HEAD`, end to end, as if it were someone else's.
2. Everything in it belongs to the issue. Anything that does not is another issue
   or a revert.
3. Nothing in it is a leftover: no debug print, no commented-out code, no scratch
   file, no widened log line, no unrelated formatting.
4. The commit messages still describe what landed, after the last fix.

## Leave the tree the way you found it

- Stage the paths you touched. `git add -A` sweeps the owner's uncommitted work into
  your commit.
- A generated file is not hand-edited: a lockfile, `site/`, a bundle zip, a pinned
  digest. Change the source, run the generator, commit its output.
- No stray branch, stash or untracked file of yours is left behind.

## Run the gate, again

The last change may have broken what an earlier run proved. Run the repository's gate
as `verify` names it, not the single test file, and then write down each command and
its result. A gate that fails is not a pull request; it is a report.

## The pull request and the report

- Body: why, what, the checks with their results, and `Refs` or `Closes` as the
  `taskboard` skill says. Short, no narration.
- Say which part landed: merged, image rebuilt, digest re-pinned, synced. A merged
  pull request is not a deployed change.
- Mark anything you could not verify `[UNVERIFIED]` with the reason. It is always
  cheaper than a claim the owner later disproves.
