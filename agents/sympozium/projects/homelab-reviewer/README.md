# homelab-reviewer

One agent, in its own ensemble, because it is the only agent in this repo that
can write anything anywhere.

| Persona | Type | Schedule (UTC) | Skills | MCP |
| --- | --- | --- | --- | --- |
| `renovate-reviewer` | scheduled | `0 6 * * 1-5` (Mon–Fri 08:00 Madrid) | `code-review`, `memory` | `github`, `argocd` |

## Why a separate ensemble

Ensemble-level settings — the policy binding, shared memory, the model endpoint
— apply to every persona inside. Keeping the one agent that holds a write tool
apart from the five read-only ones means its blast radius is visible in the
directory listing, and that loosening something for it cannot silently loosen it
for them.

Its single write tool is `github_add_issue_comment`. `merge_pull_request`,
`create_pull_request_review` (which could approve), `push_files`,
`create_or_update_file`, branch and repository creation, and issue mutation are
all listed in `toolsDeny`, so they are filtered at the MCP server rather than
just omitted from the allowlist. `sharedMemory` is off.

## What it does

This is change management for `datahub-local-bootstrap`, `datahub-local-core` and
`datahub-local-ai`. Each weekday morning the agent reads the open Renovate PRs
and comments a verdict — `SAFE TO MERGE`, `REVIEW NEEDED` or `DO NOT MERGE` —
and always says what a migration would cost.

What makes the verdict more than a rubber stamp is that it checks the bump
against how these repositories actually work:

- Helm chart versions live in `values/_version.yaml` in datahub-local-core, so a
  chart bump is a `version` change there and the affected release is knowable by
  name.
- `renovate.json` disables **all** major updates. A PR that crosses a major
  anyway is a misconfiguration worth shouting about, not a routine bump.
- Every release is deployed by ArgoCD, so it checks the affected application is
  Healthy *right now* — merging onto an already-degraded app is a bad idea
  whatever the diff says.
- For anything beyond a patch it fetches the upstream notes looking for four
  specific things, because these are what actually break this homelab: removed or
  renamed values keys (the release still renders, the config silently vanishes),
  CRD schema changes (the dangerous class — ArgoCD may not be able to apply them
  unattended), required manual migration commands, and changed defaults.

The **Migration** section is never left blank: either the exact steps, or "none
required" because it checked. And it may not claim "no breaking changes" without
having fetched and read the notes — if it could not, the verdict is
`REVIEW NEEDED` and it says why. One comment per PR per run, silent when the
verdict has not changed.

`fetch_url` is allowlisted here and nowhere else — changelogs live outside the
cluster. The Sympozium NetworkPolicy already permits agent egress on 443.

## Notification

The `DO NOT MERGE` comment on the PR **is** the alert, so the prompt requires the
risk to be the first thing a reader sees rather than something buried under a
summary of the diff.

This agent is **not** bound to Slack, though the credential now exists and
[homelab-ops](../homelab-ops/README.md#notification) uses it. A channel binding
is bidirectional: it would put an inbound trigger — anyone in the workspace, via
an @-mention — on the one agent in this repo that can write anything anywhere.
The whole reason this ensemble is separate is that its blast radius stays
visible in the directory listing, and quietly adding a remote-trigger path to it
would undo that. Bind it only alongside `channelAccessControl.allowedSenders`,
and treat that as a deliberate change rather than a convenience.

## Repository health

A short second job, run after the PRs. GitHub Actions history is not reachable —
the MCP server ships no workflow tools — so health is measured from what is
visible: how many Renovate PRs are open, how old the oldest is, how many are
failing CI, and how recently the default branch was committed to. The finding
being hunted is a *growing backlog*, since that is how a homelab ends up a year
behind without anyone ever deciding to fall behind.
