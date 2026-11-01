---
name: taskboard
description: Create, claim and close GitHub issues in the central taskboard, and link the pull request to them. Use whenever a task starts, a branch is cut, a pull request is opened, or an issue's state changes.
---

# Taskboard

Every task is a GitHub issue in `datahub-local/datahub-local`. That repository is
the queue; the code and its pull requests live wherever the change is.

The org's Project board at `https://github.com/orgs/datahub-local/projects/1`
mirrors the queue. Membership is automatic: the project adds any issue carrying
the `agent` label, server-side. Never call the Projects API from this Pod. The Pod
has no `project` token scope, and it does not need one, because the issue is the
record and the board is a view of it. If an issue must be added by hand, say so in
the report and let the owner add it.

## Claiming a task

1. `gh issue view <n> --repo datahub-local/datahub-local` and read the body and
   the comments. The latest human comment is part of the task.
2. If the task arrived without an issue, create one first:

   ```bash
   gh issue create --repo datahub-local/datahub-local \
     --title "<repo>: <what changes>" \
     --label agent --label <area> \
     --body "<what, why, acceptance, the repository it touches>"
   ```

3. Comment once that work started, so the issue shows a live claim:

   ```bash
   gh issue comment <n> --repo datahub-local/datahub-local \
     --body "Claimed. Branch \`<type>/<n>-<topic>\` in <repo>."
   ```

Labels that exist: `bug`, `enhancement`, `infra`, `data`, `monitoring`,
`security`, `automation`, `ai`, `CICD`, `documentation`, `question`, plus the
queue marker `agent`. Use the ones that fit and never invent a new label; if
`agent` is missing, create it once with `gh label create agent --repo
datahub-local/datahub-local --description "Delegated to the code agent"`.

## The branch

One issue, one branch, cut from an up-to-date `main`:

```
<type>/<issue>-<topic>        feat/106-opencode-mcp-shim
```

`<type>` is the commit type of the main change. Never reuse a branch for a second
issue, and never branch from another feature branch.

## The pull request

Open it in the repository that holds the change, never in the taskboard:

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

`Closes` only works inside one repository. For a cross-repository pull request
use `Refs`, then comment the pull request URL on the issue:

```bash
gh pr view --repo datahub-local/<repo> --json url -q .url
gh issue comment <n> --repo datahub-local/datahub-local --body "<url>"
```

## The owner

Mention `@alvsanand` once, on the pull request, when it is ready for review. Not
in the issue, not per commit, not in a status comment. Hermes posts the Slack
message; the pull request is the record.

## Closing

- A merged pull request in the same repository closes its own issue.
- A cross-repository pull request leaves the issue open until the merge is
  reported. Then comment what shipped and close it:

  ```bash
  gh issue close <n> --repo datahub-local/datahub-local --reason completed
  ```

- A task that cannot be finished: comment the blocker and what was tried, leave
  the issue open, and report `BLOCKED`. Never close an issue to signal failure.
