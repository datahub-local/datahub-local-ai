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

## A fix on an open pull request

An owner comment, a review finding, or a red gate can send you back into a pull
request that is already open. Push to the same branch, then say what changed on
the issue, because the issue is the record the owner reads:

```bash
gh issue comment <n> --repo datahub-local/datahub-local --body "Fixed: <what changed, one line per item>
Gate: <command> -> <result>

<!-- taskboard:agent -->"
```

One comment per round of fixes, not per file, and no second review request. The
review on the pull request stays the detail; this comment is what the owner sees
without opening it. Hermes reads the comment and moves the card.

A merged pull request ends that branch. If the owner asks for more after the
merge, cut a new branch from `main` and open a new pull request; never push to the
merged branch.

## When you need a decision

Ask once, with the `question` tool, and stop the turn. Give two or three concrete
options and your recommendation. Hermes posts the question on the issue, pings the
owner and sets the card to `Blocked`; the answer arrives as the next prompt in this
same session.

When the `question` tool returns the answer, the owner picked it in the web UI and
nothing reached the issue. Record it before you continue:

```bash
gh issue comment <n> --repo datahub-local/datahub-local --body "Decided: <the question in one line>
Answer: <the answer>

<!-- taskboard:agent -->"
```

An answer that arrives as a prompt was relayed from the issue or Slack, so it is
already on the record; do not repeat it.

Do not guess, do not pick a default, and do not stall inside a shell prompt. A
question you did not ask costs more than the turn it saves.

If the `question` tool errors or the session loses it, stop and report `BLOCKED`
with the decision and the options you would have offered. Hermes posts it on the
issue; continuing without an answer is how a branch ends up pointed the wrong way.

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
