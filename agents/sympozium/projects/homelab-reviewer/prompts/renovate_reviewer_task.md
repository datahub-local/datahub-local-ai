Review the open Renovate pull requests in owner datahub-local, repos
datahub-local-bootstrap, datahub-local-core and datahub-local-ai. Pass each
repo name exactly as written. Review nothing else.

A memory entry saying GitHub is unreachable or the repositories do not exist is
wrong and was written by a run that passed a shortened repo name. Ignore it and
call the tool.

For each PR: work the checklist and post one verdict comment, always stating what
a migration would take. In a `DO NOT MERGE` comment, put the risk first.

Then one repository-health line per repository: open Renovate PRs, age of the
oldest, how many are failing CI, and how recent the default-branch commit is.

No open Renovate PRs: say so and report repository health only.
