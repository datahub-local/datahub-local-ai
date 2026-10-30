# Tasks

## 1. The adapter's article profile

- [ ] 1.1 `agents/adapters/pi-render/session-lib.mjs`: parse `profile` (`render` default so an old
  caller keeps working), and refuse an unknown one by name.
- [ ] 1.2 `prompts/article.md`: the sandbox facts for this profile — working directory, 443 only, no
  cluster and no Docker, write `article.md` and `sources.json` here, quote rather than invent, say so
  when a source could not be read.
- [ ] 1.3 `session-lib.mjs`: the article artifact contract (`article.md`, `sources.json`), the
  ledger's schema, and the line a turn answers about where its files are.
- [ ] 1.4 `session-server.mjs`: choose the instruction and the artifact contract by profile; serve
  `article.md`/`sources.json` on the existing `/artifacts/<session>/<name>` route.
- [ ] 1.5 `session-server.mjs`: after an `article` turn, fetch every ledgered URL — https only,
  private/loopback/link-local refused, body capped, redirects capped, timeout per URL — and drop the
  entries that do not answer, recording status and a body hash.
- [ ] 1.6 `Dockerfile`: `curl`, `ca-certificates`, `helm` and `kubectl` (Pi's bash has no HTTP client,
  and a quoted manifest is dry-run before it is fenced); assert all four in
  `test/dockerfile.test.mjs` beside the existing toolchain assertions.
- [ ] 1.7 `session-server.mjs`: a loopback forward proxy honouring `ARTICLE_SOURCE_HOSTS`, with
  `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY` set in the container so `curl` in a bash tool goes through
  it; anything off the list answers `403` and the refusal is logged with the host.
- [ ] 1.8 `session-lib.mjs`: the ledger entry is the **fenced block** verbatim plus `url`, `found`,
  `sha256` of the normalised block, `validated` (`dry-run`/`none`) and `validation_error`; the match
  is a whitespace-normalised contiguous excerpt, and the server records the excerpt it matched.
- [ ] 1.9 `prompts/article.md`: render or dry-run a YAML block before fencing it; read only from the
  allowlisted hosts (the list is shown to the agent, the proxy enforces it).

## 2. The session

- [ ] 2.1 `agents/sympozium/templates/article-writer-session.yaml`: `SympoziumPolicy`, `AgentRuntime`
  (same image, its own resources), `Agent`, `PersistentVolumeClaim`, `HarnessSession`, `Service`, and
  the two additive NetworkPolicies (n8n ingress on 8080, egress to LiteLLM on 4000) — mirroring
  `pi-render-session.yaml`.
- [ ] 2.2 `values/default.yaml.gotmpl`: `sympozium_article_writer` with `enabled`, `image`, `digest`,
  `resources`, `model`, `storageClass`, `storage` and `sourceHosts`; no defaults for the model
  address, and the hosts are values because they are a property of what the fleet writes about.

## 3. The drafting swap

- [ ] 3.1 `article_creator.workflow.json`: replace `create_article_ai`, `create_article_ai_plain`,
  `if_needs_research`, `research_sources`, `read_page` and `ai_model`/`ai_model_fallback` with
  `request_article` (HTTP POST to the session, `profile=article`, `session_id` from the row) and two
  fetches (`fetch_article`, `fetch_sources`). Both graph copies.
- [ ] 3.2 Keep `parse_article`'s contract: the request node's output is reshaped into what it already
  reads, so the review loop, `merge_article_verdict` and the retry edge are untouched.
- [ ] 3.3 `parse_article`: match each fenced block against the ledger as a normalised contiguous
  excerpt, require the block to hash to what the server recorded, reject a block absent from the
  ledger, an entry whose `found` is false and an entry whose dry-run failed — naming the block's
  first line and the URL; report `SOURCES: <n> quoted` as data so grounding is readable from the
  execution.
- [ ] 3.4 `check_improved_draft`: the same ledger check, so an edit cannot introduce an unquoted
  command. Twin fixture, same verdicts.
- [ ] 3.5 A draft whose ledger carries no command lines is accepted as prose and rejected if it fences
  anything — the absence rule, expressed as a count.
- [ ] 3.6 `update_article_drafted`: write `SOURCES` (the ledger JSON) beside `ARTICLE_REF`, and add
  the column to the node's schema with `removed: false`; `select_article_to_queue` carries it, so a
  human retry and a resumed review read the same ledger.
- [ ] 3.7 `check_improved_draft`: the same block match against `row.SOURCES`; a missing ledger
  improves the draft with the fidelity check reported as not run, never silently passed.
- [ ] 3.8 The retry is a **correction turn** in the row's session (`article-<row_number>`): the request
  carries the reviewer's reason, the previous draft and `attempt`, and the instruction is to apply the
  change to the article in that directory, re-reading only what it names.

## 4. The prompts

- [ ] 4.1 `article_writer.md`: the brief the session receives — the entry, the audience, the rules, the
  sources to read first, and the ledger requirement; no template vocabulary.
- [ ] 4.2 `article_review.md`: `{{ SOURCES }}` and the fidelity check reading the list.
- [ ] 4.3 `article_improver.md`: an edit may not fence a line that is not in the ledger.

## 5. Tests

- [ ] 5.1 `agents/adapters/pi-render/test/`: `profile` defaults to `render`, an unknown profile is
  refused, the article contract is served, and the ledger filter drops a URL that does not answer
  (a stub server, no network in the test).
- [ ] 5.2 The ledger fetch refuses `http://`, `169.254.169.254`, `10.0.0.0/8`, `localhost` and a
  redirect to any of them, and caps a large body.
- [ ] 5.3 `agents/adapters/pi-render/test/`: a blocked host is refused **through the proxy**, a
  ledgered URL that does not answer is dropped, a block whose whitespace differs still matches, and a
  block missing from the page is `found: false`.
- [ ] 5.4 `scripts/test_article_sources.py`: executing `parse_article`, a ledgered block passes, an
  absent one is rejected naming it, a block whose hash no longer matches the server's excerpt is
  rejected, a dropped entry is rejected, a failed dry-run is rejected naming the failure, and a draft
  with no ledger commands may not fence.
- [ ] 5.5 The twin check agrees on the same fixtures, including a missing `SOURCES` cell.
- [ ] 5.6 `scripts/test_article_prompts.py`: the gate declares `SOURCES` and the node supplies it; the
  writer prompt declares no placeholder the request does not pass.

## 6. Cross-repo

- [ ] 6.1 `datahub-local-core`: `ARTICLE_WRITER_URL` on the n8n deployment, beside `PI_RENDER_URL`.
  **Blocked by** the session existing.

## 7. Verification

- [ ] 7.1 `uv run --with pytest --with pyyaml pytest scripts/` in `agents/n8n`,
  `npm test` in `agents/adapters/pi-render`, `openspec validate --all`.
- [ ] 7.2 Order: adapter image and session first, `ARTICLE_WRITER_URL` next, then the workflow — the
  graph calls a URL that does not exist until the session is running.
- [ ] 7.3 Rollback is the committed export re-applied — no flag ships with this (D13). [UNVERIFIED]
  until one revert has been done with it.
- [ ] 7.4 [UNVERIFIED] one live article on a row whose docs exist, read at the review notification:
  every fenced command traceable to a URL in `sources.json`, no placeholder, and a section that would
  have had one saying instead that the source could not be read.
