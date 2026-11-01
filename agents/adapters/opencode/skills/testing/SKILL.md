---
name: testing
description: How to write a test that proves the change, and which tests not to write. Use when adding a test, fixing a bug, or deciding what the suite must cover.
---

# Testing

A test is proof, not decoration. If it cannot fail, it proves nothing.

## Red first

- Write the test before the code, or at least watch it fail before the code exists.
  A test that was never red has not shown you what it catches.
- Before writing it, name the production change that would make it fail. If you
  cannot name one, the test asserts something else: a mock, a fixture, a file.
- When fixing a bug, the reproduction is the test. It fails without the fix and
  passes with it, and it stays in the suite.

## One behaviour, one test

- The name states the behaviour, in the terms a reader of the issue would use. If
  the name needs "and", it is two tests.
- One assertion of consequence per test. Several assertions are fine when they
  describe the same outcome.
- Assert what the code does, never what a stub did. `assert mock.called` passes
  while the behaviour is wrong.
- Cover the edge the change is about, and the error path. The happy path alone
  proves the code ran, not that it is right.

## Never test configuration

No test over a YAML value, a chart option, a prompt's wording, a skill's text or a
file's presence. Such a test duplicates the file, fails every legitimate edit, and
proves nothing a reader cannot see. Where the change is configuration, the
repository's render or build gate is the check.

A rule file is reviewed, not asserted. No test and no build check should restate what
the file says.

## Before you call it done

- Run the whole suite the repository names, not only the file you touched. A scope
  statement bounds the deliverable, not the verification.
- Output pristine: no warnings your change introduced, no test left skipped.
- A failure you saw and did not mention turns the report into a false statement, even
  if your change did not cause it. Name it.
