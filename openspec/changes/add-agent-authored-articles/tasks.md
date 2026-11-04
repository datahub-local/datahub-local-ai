# Tasks

## 1. The writer adapter

- [x] `agents/adapters/pi-writer/`: a new adapter, not a `profile` inside `pi-render` (D1).
  `session-lib.mjs` holds the artifact contract (`article.md`, `sources.json`), the ledger's schema,
  the source policy and Pi's retry settings; `session-server.mjs` serves
  `/v1/chat/completions` and `/artifacts/<session>/<name>`.
- [x] `prompts/writing.md`: the sandbox facts — working directory, 443 only through the proxy, no
  cluster and no Docker, write `article.md` and `sources.json` here, quote rather than invent, say so
  when a source could not be read.
- [x] `session-server.mjs`: after a turn, fetch every ledgered URL — https only,
  private/loopback/link-local refused, body capped, redirects capped, timeout per URL — and drop the
  entries that do not answer, recording status and a body hash.
- [x] `Dockerfile`: `curl`, `ca-certificates` and `helm` (Pi's bash has no HTTP client, and a quoted
  manifest is rendered with `helm template` before it is fenced); `kubectl` is deliberately absent.
  The toolchain assertions live in `test/dockerfile.test.mjs`.
- [x] `session-server.mjs`: a loopback forward proxy honouring the request's `source_hosts`, with
  `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY` set in the container so `curl` in a bash tool goes through
  it; anything off the list answers `403` and the refusal is logged with the host.
- [x] `session-lib.mjs`: the ledger entry is the **fenced block** verbatim plus `url`, `found`,
  `sha256` of the normalised block, `validated` (`dry-run`/`none`) and `validation_error`; the match
  is a whitespace-normalised contiguous excerpt, and the server records the excerpt it matched.
- [x] `entrypoint.sh`: dispatch to the session server on `v1alpha2`; a Job gets a named refusal with
  a `jq`-built error payload, because an article needs the session directory and the serialized turn.

## 2. The session

- [x] `agents/sympozium/templates/pi-writer-session.yaml`: `SympoziumPolicy`, `AgentRuntime` (its
  own image pin and resources), `Agent`, `PersistentVolumeClaim`, `HarnessSession`, `Service`, and
  the two additive NetworkPolicies (n8n ingress on 8080, egress to LiteLLM on 4000) — mirroring
  `pi-render-session.yaml`.
- [x] `values/default.yaml.gotmpl`: `sympozium_pi_writer` with `enabled`, `image`, `digest`,
  `resources`, `model`, `storageClass` and `storage`; the hosts ride on the session request, so there
  is no `sourceHosts` here.

## 3. The drafting swap

- [x] `article_creator.workflow.json`: replace `create_article_ai`, `create_article_ai_plain`,
  `if_needs_research`, `research_sources`, `read_page` and their model edges with `request_article`
  (HTTP POST to the session, `session_id` from the row) and two fetches (`fetch_article`,
  `fetch_sources`). Both graph copies.
- [x] Keep `parse_article`'s contract: the request node's output is reshaped into what it already
  reads, so the review loop, `merge_article_verdict` and the retry edge are untouched.
- [x] `parse_article`: match each fenced block against the ledger as a normalised contiguous
  excerpt, require the block to match what the server recorded, reject a block absent from the
  ledger, an entry whose `found` is false and an entry whose dry-run failed — naming the block's
  first line and the URL; report `SOURCES: <n> quoted` as data so grounding is readable from the
  execution.
- [x] `check_improved_draft`: the same ledger check, so an edit cannot introduce an unquoted
  command. Twin fixture, same verdicts.
- [x] A draft whose ledger carries no command lines is accepted as prose and rejected if it fences
  anything — the absence rule, expressed as a count.
- [x] `update_article_drafted`: write `SOURCES` (the ledger JSON) beside `ARTICLE_REF`, and add
  the column to the node's schema with `removed: false`; `select_article_to_queue` carries it, so a
  human retry and a resumed review read the same ledger.
- [x] `check_improved_draft`: the same block match against `row.SOURCES`; a missing ledger
  improves the draft with the fidelity check reported as not run, never silently passed.
- [x] The retry is a **correction turn** in the row's session (`article-<row_number>`): the request
  carries the reviewer's reason, the previous draft and `attempt`, and the instruction is to apply the
  change to the article in that directory, re-reading only what it names.

## 4. The prompts

- [x] `article_writer.md`: the brief the session receives — the entry, the audience, the rules, the
  sources to read first, and the ledger requirement; no template vocabulary.
- [x] `article_review.md`: `{{ SOURCES }}` and the fidelity check reading the list.
- [x] `article_improver.md`: an edit may not fence a line that is not in the ledger.

## 5. Tests

- [x] `agents/adapters/pi-writer/test/ledger.test.mjs`: the ledger's shape, the block match, and the
  fetch policy — a URL that does not answer is dropped, a block the page does not carry is
  `found: false` (a stub server, no network in the test).
- [x] The ledger fetch refuses `http://`, `169.254.169.254`, `10.0.0.0/8`, `localhost` and a
  redirect to any of them, and caps a large body.
- [x] `agents/adapters/pi-writer/test/session-server.test.mjs`: a blocked host is refused **through
  the proxy**, a declared private host is refused too, a retry is a correction turn, and the artifact
  route serves only the two names.
- [x] `scripts/test_article_sources.py`: executing `parse_article`, a ledgered block passes, an
  absent one is rejected naming it, a block that no longer matches the server's excerpt is
  rejected, a dropped entry is rejected, a failed dry-run is rejected naming the failure, and a draft
  with no ledger commands may not fence.
- [x] The twin check agrees on the same fixtures, including a missing `SOURCES` cell.
- [x] `scripts/test_article_prompts.py`: the gate declares `SOURCES` and the node supplies it; the
  writer prompt declares no placeholder the request does not pass; the request names the row and the
  allowlist and selects no profile.

## 6. Cross-repo

- [ ] `datahub-local-core`: `ARTICLE_WRITER_URL` on the n8n deployment, beside `PI_RENDER_URL`,
  pointing at `datahub-local-ai-pi-writer-api.automation.svc.cluster.local:8080`. **Blocked by** the
  session existing.
- [ ] The publish workflow's adapter discovery builds and pins
  `ghcr.io/datahub-local/datahub-local-ai-pi-writer-adapter` on the first merge to `main`, and the
  pin job rewrites the `digest:` line of the `sympozium_pi_writer` block. **Blocked by** that merge.
- [ ] Owner, by hand: add a `SOURCES` column to the `article_queue` sheet before the first run.
  The write node maps the column by header, so a missing header fails the run after the draft was
  uploaded.

## 7. Verification

- [x] `uv run --with pytest --with pyyaml pytest scripts/` in `agents/n8n`,
  `node --test 'agents/adapters/pi-writer/test/*.test.mjs'` in `agents/adapters/pi-writer`,
  `node --test 'agents/adapters/pi-render/test/*.test.mjs'` in `agents/adapters/pi-render`,
  `helmfile template` in `agents/sympozium`, and `openspec validate --all`.
- [x] Order: adapter image and session first, `ARTICLE_WRITER_URL` next, then the workflow — the
  graph calls a URL that does not exist until the session is running.
- [ ] Rollback is the committed export re-applied — no flag ships with this (D13). [UNVERIFIED]
  until one revert has been done with it.
- [ ] [UNVERIFIED] one live article on a row whose docs exist, read at the review notification:
  every fenced command traceable to a URL in `sources.json`, no placeholder, and a section that would
  have had one saying instead that the source could not be read.

## Deviations as landed

- **D1 — the shared image with a profile was built first and reverted.** The article lane landed as
  a `profile` inside `pi-render`; on the owner's direction it is its own adapter. `pi-render` is now
  byte-identical to `main` on this branch, so the studio cannot be affected by this change.
- **2.2 — the digest is seeded with the render image's.** `sympozium_pi_writer.digest` starts at
  `sha256:d799574b…`, the current `pi-render` digest, because no writer image exists until the first
  publish. The publish workflow's pin job rewrites the `digest:` line of the block named
  `sympozium_<adapter directory>`; renaming the block would leave the seed in place with no error.
- **2.1/6.1 — the model credential is cross-repo.** The controller refuses a Secret shared by two
  Agents, so the deployment expects `litellm-auth-credentials-pi-writer`. Creating it belongs
  to `datahub-local-secrets` and the core fan-out; this change reports it instead of committing a
  secret.
- **3.1 — `ai_model` and `ai_model_fallback` stay.** They are removed from the drafting agent's
  `ai_languageModel` edges but not from the graph: `check_article_llm` still uses them, and a model
  node needs both inputs connected or the activation is refused.
- **3.3/3.4 — the hash check is an excerpt comparison.** An n8n Code node cannot
  `require('crypto')`. `parse_article` and `check_improved_draft` compare the normalised block to
  the `excerpt` the server recorded (whose normalised form is the hash input), and the server still
  writes `sha256` for the ledger's readers.
- **D11 — `helm` is in the image for one rule.** An offline `helm template` is the only manifest
  check that works without a cluster. Drop the validation requirement and `helm` leaves the image
  with it. `kubectl` is absent because a client dry-run needs API discovery; no prompt offers it.
- **1.6 — `[UNVERIFIED]` the live image.** The writer image is built and pinned on the first merge
  to `main`. Until then the seeded digest points at `pi-render`, which refuses the writer's contract.
