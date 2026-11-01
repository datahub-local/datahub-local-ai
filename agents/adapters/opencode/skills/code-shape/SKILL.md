---
name: code-shape
description: How much code a change should contain and what it must not touch. Use before writing or editing code in any datahub-local repository.
---

# Code shape

The smallest diff that makes the issue true. If a smaller version exists, that is
the one to write.

## Keep it small

- Delete before you add, and reuse the pattern the repository already has before
  inventing a second one.
- Implement the case the issue names. A general mechanism for one caller is
  speculative, and the second caller will not look like the one you imagined.
- Extend what exists before adding a module, a flag or a table. A new file is a
  decision; the issue has to ask for it.

## Do not re-engineer

- Never rewrite working code to improve it. No refactor the issue did not ask for,
  no rename, no move, no reformat, no dependency bump, no "while I was here" fix.
  Those are their own issues, and they are named in the report.
- No speculative abstraction: no interface with one implementation, no factory for
  one product, no config knob with one value.
- No compatibility shim, deprecated alias or version guard. One version runs.
- No new dependency for something the standard library or the repository already
  does.

## Do not widen the blast radius

- One repository per change. When two must move together, change one here and
  report the other with the exact change it needs. A lockstep commit across
  repositories is not one change.
- Do not make a test pass by changing what it tests, and do not make a build pass by
  relaxing what it checks.
- Leave the surrounding code as you found it, including its formatting. A diff
  nobody can read is a change nobody can review.

## When the issue is wrong

An issue can ask for something the code makes impossible or harmful. Say so with
the evidence, propose the alternative, and ask. Doing the harmful thing because it
was written down is not obedience, it is a second mistake.
