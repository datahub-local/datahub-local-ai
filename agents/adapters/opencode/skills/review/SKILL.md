---
name: review
description: Get the change reviewed by the second model before reporting it done, post that review on the pull request, and act on every finding. Use after the gate passes and the pull request exists, before the DONE report.
---

# Review

The agent that wrote the change is the worst judge of it. A second agent, on a
different model, reads the diff with fresh eyes, and its review is written where a
person will find it: on the pull request.

## Order

1. The gate is green and the pull request exists.
2. Run the reviewer (below).
3. Post the review on the pull request.
4. Act on every finding, then push.
5. Report. At most two review rounds.

Never run this before the gate: a reviewer reading a failing diff wastes its turn
on what the gate already said.

## Running the reviewer

Invoke the `reviewer` subagent with the Task tool. It is the `reviewer` agent in the
image config: a different model (`OPENCODE_REVIEW_MODEL`), read-only by permission,
no `question`, no nested subagents. Give it:

- the issue number and the repository;
- the base the diff is against (`origin/main`);
- the gate commands you ran and their results;
- the files you changed, one line each.

Do not paste the diff or your reasoning: it reads them. Do not ask it to fix
anything; it cannot edit.

## Posting it

Write the review verbatim on the pull request, with a quoted heredoc so nothing in
the body is interpreted:

```
cat <<'EOF' | gh pr comment <n> --repo datahub-local/<repo> --body-file -
## Review by glm-5.3-flash

<the reviewer's findings, verbatim>

<!-- taskboard:review -->
EOF
```

The marker matters: it is what tells the tick this comment is not the owner
writing.

## Acting on it

- **BLOCKING**: fix it. If you believe the finding is wrong, say why in one line in
  the report and in a reply on the pull request; do not stay silent and do not
  silently comply with something wrong.
- **SHOULD**: fix it, or state in the report why it is out of scope.
- **NIT**: fix it if it is free, otherwise leave it.
- Re-run the gate after the fixes and push to the same branch.
- Run the reviewer once more when a blocking finding was fixed. Two rounds is the
  ceiling; a third means the task is bigger than one branch, and that is a report.

## In the report

One line per round: the verdict, the count of findings by severity, and what you
did with each. Unresolved findings are named with the reason. A review you did not
run is `[UNVERIFIED]`, not omitted.
