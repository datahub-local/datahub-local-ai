# Proposal

## Why

The article lane cannot produce a usable technical article from one prompt, and the drafts prove it
rather than suggest it. The last one (2026-10-30, after the structure fixes) is *well shaped*:
numbered sections, prerequisites first, four fenced blocks, a close that points somewhere. Its
commands are placeholders:

    kubectl apply -f <install-manifest-from-the-docs>
    <activate-command-from-the-docs> my-first-ensemble
    apiVersion: <group>/<version>

The previous one (execution 15259) had no commands at all and the shape's bullets as its headings.
Two drafts, two different defects, one cause: **the drafting pass writes from whatever text one HTTP
fetch put in its prompt.** Row gh-80's source material is a GitHub issue page — a brief, no install
docs, no chart, no version — so a model told to write a walk-through does the only thing it can: it
writes the shape of one and marks the holes. No prompt wording changes that, and a bigger prompt makes
it worse: the writer needs *capabilities* it does not have — fetch the project's own documentation,
read the chart, copy the exact command and the exact manifest.

This is the visual-studio finding in a second place, and it was accepted there: authoring moved out of
a node's prompt into a session with tools, a working directory and an artifact it can inspect, with
the critique as a separate call. The article lane is still on the other side of that line.

## What Changes

- **The drafting pass becomes a session turn, not an agent node.** `Article Creator` keeps its inputs
  and its output shape (`text`, `title`, `word_count`, `ERROR`) and its review loop; only the writer
  changes: one HTTP call to a `HarnessSession` running the existing Pi adapter image with an
  `article` profile, which has `read`, `bash`, `edit`, `write` and 443 egress.
- **The session fetches, it does not execute.** It reads the project's documentation, charts and
  repository files over HTTPS — from an allowlist of hosts, enforced by a loopback proxy the pod's
  tools go through — and quotes what it finds. It has no cluster and no Docker, so it never claims to
  have run anything; `helm template` and `kubectl --dry-run=client` do run, and a manifest that fails
  them may not be fenced at all.
- **Every fenced line carries a source.** The session returns `article.md` plus `sources.json`, a
  ledger of each fenced line with the URL it came from. The session **server**, not the model, fetches
  each URL after the turn and records its status and a hash, so a URL the model invented is dropped
  before the ledger reaches n8n.
- **The gate checks the ledger in code.** A fence is matched as a **block**, not a line: the ledger
  holds each fenced block verbatim and the check is "this block, whitespace-normalised, is a
  contiguous excerpt of the page it cites" plus a hash comparison against the excerpt the server
  recorded. That is the count that makes "real code" enforceable instead of a preference.
- **The ledger survives the run.** It is written to `article_queue.SOURCES` beside `ARTICLE_REF`, so
  the improvement pass — which runs in a later execution — re-checks an edit against the same ledger
  instead of trusting it.
- **A draft that could not find commands says so and writes no fence.** The ledger makes absence
  expressible, which is the `unavailable` rule the reporters already use: a section with no source is
  a legitimate section, an invented command is not.
- **The review gate is handed the ledger** (`{{ SOURCES }}`) so its fidelity judgement reads a list
  rather than recalling a page.

## Capabilities

### Modified Capabilities

- `content-writer`: an article is drafted by an agent session working from fetched sources, and every
  fenced command in it must appear in a server-verified source ledger.

## Impact

- `agents/adapters/pi-render/` — an `article` profile: a second instruction file, a profile on the
  request, `curl`/`ca-certificates` in the image, the ledger step after a turn. The `render` profile
  is unchanged.
- `agents/sympozium/templates/` — a second `HarnessSession` (`article-writer`) over the same image,
  with its own PVC, Service and the two NetworkPolicies the render session already needed.
- `agents/n8n/workflows/article_creator.workflow.json` — `create_article_ai`,
  `create_article_ai_plain`, `if_needs_research`, `research_sources`, `read_page` and their model
  nodes are replaced by one HTTP request to the session and a fetch of its two artifacts;
  `parse_article` gains the ledger check. Both graph copies.
- `agents/n8n/prompts/article_writer.md`, `article_review.md` — the body is the session's brief; the
  gate gets `{{ SOURCES }}`.
- `workflows/airflow`, `workflows/dbt`, the post lane, the publish path and the improvement pass —
  **untouched**.
- `datahub-local-core` — `ARTICLE_WRITER_URL` on the n8n deployment, and the image pipeline for the
  adapter tag. Cross-repo; the change is blocked on it.

## Non-goals

- **No cluster, no k3d, no Docker-in-Docker.** The session cannot run `helm install` against anything,
  and this change does not pretend otherwise by adding a cluster it would have to keep alive. If
  command *execution* is ever wanted, it is a separate change with a disposable cluster behind it.
- **No structure registry.** A template registry with counted sections was built and reverted on
  2026-10-30: the next draft satisfied every count it added and was still unpublishable. Shape is not
  the constraint.
- **No new publish path**, no change to the asset lane, and no change to the post lane's drafting.
