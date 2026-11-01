---
name: taskboard
description: Work a GitHub issue from the central taskboard and hand back a pull request. Use when a session names an issue, when a branch is cut, when a pull request is opened, or when a status would change.
---

# Taskboard

Every task is a GitHub issue in `datahub-local/datahub-local`. That repository is
the queue; the code and its pull requests live wherever the change is.

The Project board at `https://github.com/orgs/datahub-local/projects/1` is the
state of that queue, and **Hermes is its only writer**. The Pod has no `project`
token scope. Do not call the Projects API, do not add `status:*` labels, and do not
try to move a card. You signal with comments and a pull request; Hermes reads those
and moves the card.

## Starting a task

0. A session may start inside an existing checkout. Check before cloning:

   ```bash
   git rev-parse --show-toplevel 2>/dev/null && git remote -v
   ```

   If the working directory is already the repository you need, work there: fetch
   and cut the branch from `main`. Never clone a second copy inside a checkout,
   and never work in a checkout of a different repository than the issue names.

1. The prompt names the issue. Read it, and the comments, before anything else:

   ```bash
   gh issue view <n> --repo datahub-local/datahub-local --comments
   ```

   The newest human comment is part of the task. A previous comment may carry the
   session id; you are already in that session, so ignore it.

2. Comment once that work started:

   ```bash
   gh issue comment <n> --repo datahub-local/datahub-local \
     --body "Claimed. Branch \`<type>/<n>-<topic>\` in <repo>.

   <!-- taskboard:agent -->"
   ```

3. If the task arrived without an issue, create one first:

   ```bash
   gh issue create --repo datahub-local/datahub-local \
     --title "<repo>: <what changes>" \
     --label agent --label <area> \
     --body "<what, why, acceptance, the repository it touches>"
   ```

Labels that exist: `bug`, `enhancement`, `infra`, `data`, `monitoring`,
`security`, `automation`, `ai`, `CICD`, `documentation`, `question`, plus `agent`
for delegation. Use the ones that fit and never invent a new label.

## The branch

One issue, one branch, cut from an up-to-date `main`:

```
<type>/<issue>-<topic>        feat/116-org-profile-readme
```

`<type>` is the commit type of the main change. Never reuse a branch for a second
issue, and never branch from another feature branch.

## The pull request

You open it, in the repository that holds the change, never in the taskboard:

```bash
gh pr create --repo datahub-local/<repo> --base main --head <branch> \
  --title "<type>(<scope>): <subject>" --body-file /tmp/pr.md
```

The body is short and has four parts:

```
## Why
<the problem, one paragraph, in the issue's terms>

## What
- <change, one line per item>

## Checks
- `<command>` -> <result>

Refs datahub-local/datahub-local#<n>
```

`Closes` only works inside one repository. For a cross-repository pull request use
`Refs`, then comment the pull request URL on the issue:

```bash
gh pr view --repo datahub-local/<repo> --json url -q .url
gh issue comment <n> --repo datahub-local/datahub-local --body "<url>

<!-- taskboard:agent -->"
```

Do not mention the owner and do not post a review request. Hermes does both when
it sees the pull request.

## When you need a decision

Ask once, with the `question` tool, and stop the turn. Give two or three concrete
options and your recommendation. Hermes posts the question on the issue, pings the
owner and sets the card to `Blocked`; the answer arrives as the next prompt in this
same session.

Do not guess, do not pick a default, and do not stall inside a shell prompt. A
question you did not ask costs more than the turn it saves.

## The owner

The owner answers questions and reviews the pull request. Hermes handles the
notification; you never page the owner yourself.

## Closing

You do not close the issue and you do not move the card.

- A merged pull request in the same repository closes its own issue.
- A cross-repository pull request leaves the issue open. Comment what shipped and
  report `DONE`; Hermes sees the merge and sets `Done`.
- A task that cannot be finished: comment the blocker and what was tried, leave the
  issue open, and report `BLOCKED`. Never close an issue to signal failure.
