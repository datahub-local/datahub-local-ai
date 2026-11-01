---
name: router
description: Load this first in a session. It says which skill to load for what you are about to do, and which rules apply before any skill is loaded.
---

# Router

You have eight skills. You do not need all of them, and loading one early costs
context you will want later. This maps the moment to the skill.

| About to | Load | What it decides |
| --- | --- | --- |
| choose a repository, or answer where something lives | `repo-map` | which of the five repositories owns the work |
| start, claim, block or close a task | `taskboard` | the issue, the branch, the pull request, the marker |
| write or edit the change | `code-shape` | how big the diff is, and what it must not touch |
| write or fix a test | `testing` | red first, one behaviour, never configuration |
| investigate a failure | `debugging` | cause before fix, one hypothesis, when to stop |
| commit | `change-shape` | Conventional Commits, scopes, comments, OpenSpec |
| open the pull request | `ship-it` | your own diff, clean tree, the gate, the body |
| report `DONE` or `BLOCKED` | `verify` | the gate command per repository |

## How to use the table

- Load a skill when its moment arrives, not before. A session that reads one file
  and answers loads none of them.
- Load the next one when the moment changes. Reading the diff is `code-shape`;
  committing what you read is `change-shape`.
- Two or three skills is a normal session. Eight means the task is too broad for
  one branch, and it should go back to the owner as several issues.

## When skills disagree with something

The order is the contract's: the repository's own `AGENTS.md` or `CLAUDE.md`, then
the code and its tests, then the issue, then these skills. If a skill contradicts a
repository's `AGENTS.md`, the repository wins and you say so in the report. Do not
reconcile the two by guessing.

## Before any skill is loaded

These two hold from the first tool call, so they are in the contract too:

- Evidence before claims. A claim about a command is one you ran in this turn and
  read the output of.
- Never make a gate pass by weakening it.

## Adding a skill

A skill owns one moment. If a rule fits two skills, one owns it and the other points
at it. If a skill grows past a screen, the moment is two moments.
