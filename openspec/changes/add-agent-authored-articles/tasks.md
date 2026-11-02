# Tasks

## 1. The adapter's article profile

- [x] `agents/adapters/pi-render/session-lib.mjs`: parse `profile` (`render` default so an old
  caller keeps working), and refuse an unknown one by name.
- [x] `prompts/article.md`: the sandbox facts for this profile — working directory, 443 only, no
  cluster and no Docker, write `article.md` and `sources.json` here, quote rather than invent, say so
  when a source could not be read.
- [x] `session-lib.mjs`: the article artifact contract (`article.md`, `sources.json`), the
  ledger's schema, and the line a turn answers about where its files are.
- [x] `session-server.mjs`: choose the instruction and the artifact contract by profile; serve
  `article.md`/`sources.json` on the existing `/artifacts/<session>/<name>` route.
- [x] `session-server.mjs`: after an `article` turn, fetch every ledgered URL — https only,
  private/loopback/link-local refused, body capped, redirects capped, timeout per URL — and drop the
  entries that do not answer, recording status and a body hash.
- [x] `Dockerfile`: `curl`, `ca-certificates`, `helm` and `kubectl` (Pi's bash has no HTTP client,
  and a quoted manifest is dry-run before it is fenced); assert all four in
  `test/dockerfile.test.mjs` beside the existing toolchain assertions.
- [x] `session-server.mjs`: a loopback forward proxy honouring `ARTICLE_SOURCE_HOSTS`, with
  `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY` set in the container so `curl` in a bash tool goes through
  it; anything off the list answers `403` and the refusal is logged with the host.
- [x] `session-lib.mjs`: the ledger entry is the **fenced block** verbatim plus `url`, `found`,
  `sha256` of the normalised block, `validated` (`dry-run`/`none`) and `validation_error`; the match
  is a whitespace-normalised contiguous excerpt, and the server records the excerpt it matched.
- [x] `prompts/article.md`: render or dry-run a YAML block before fencing it; read only from the
  allowlisted hosts (the list is shown to the agent, the proxy enforces it).

## 2. The session

- [x] `agents/sympozium/templates/article-writer-session.yaml`: `SympoziumPolicy`, `AgentRuntime`
  (same image, its own resources), `Agent`, `PersistentVolumeClaim`, `HarnessSession`, `Service`, and
  the two additive NetworkPolicies (n8n ingress on 8080, egress to LiteLLM on 4000) — mirroring
  `pi-render-session.yaml`.
- [x] `values/default.yaml.gotmpl`: `sympozium_article_writer` with `enabled`, `image`, `digest`,
  `resources`, `model`, `storageClass`, `storage` and `sourceHosts`; no defaults for the model
  address, and the hosts are values because they are a property of what the fleet writes about.

## 3. The drafting swap

- [x] `article_creator.workflow.json`: replace `create_article_ai`, `create_article_ai_plain`,
  `if_needs_research`, `research_sources`, `read_page` and `ai_model`/`ai_model_fallback` with
  `request_article` (HTTP POST to the session, `profile=article`, `session_id` from the row) and two
  fetches (`fetch_article`, `fetch_sources`). Both graph copies.
- [x] Keep `parse_article`'s contract: the request node's output is reshaped into what it already
  reads, so the review loop, `merge_article_verdict` and the retry edge are untouched.
- [x] `parse_article`: match each fenced block against the ledger as a normalised contiguous
  excerpt, require the block to hash to what the server recorded, reject a block absent from the
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

- [x] `agents/adapters/pi-render/test/`: `profile` defaults to `render`, an unknown profile is
  refused, the article contract is served, and the ledger filter drops a URL that does not answer
  (a stub server, no network in the test).
- [x] The ledger fetch refuses `http://`, `169.254.169.254`, `10.0.0.0/8`, `localhost` and a
  redirect to any of them, and caps a large body.
- [x] `agents/adapters/pi-render/test/`: a blocked host is refused **through the proxy**, a
  ledgered URL that does not answer is dropped, a block whose whitespace differs still matches, and a
  block missing from the page is `found: false`.
- [x] `scripts/test_article_sources.py`: executing `parse_article`, a ledgered block passes, an
  absent one is rejected naming it, a block whose hash no longer matches the server's excerpt is
  rejected, a dropped entry is rejected, a failed dry-run is rejected naming the failure, and a draft
  with no ledger commands may not fence.
- [x] The twin check agrees on the same fixtures, including a missing `SOURCES` cell.
- [x] `scripts/test_article_prompts.py`: the gate declares `SOURCES` and the node supplies it; the
  writer prompt declares no placeholder the request does not pass.

## 6. Cross-repo

- [ ] `datahub-local-core`: `ARTICLE_WRITER_URL` on the n8n deployment, beside `PI_RENDER_URL`.
  **Blocked by** the session existing.
- [ ] Owner, by hand: add a `SOURCES` column to the `article_queue` sheet before the first run.
  The write node maps the column by header, so a missing header fails the run after the draft was
  uploaded.

## 7. Verification

- [x] `uv run --with pytest --with pyyaml pytest scripts/` in `agents/n8n`,
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

- **2.2 — the values block does not repeat the image pins.** `sympozium_article_writer` has
  `enabled`, `resources`, `model`, `storageClass` and `storage`; the template reads
  `sympozium_pi_render`'s image and digest through `required`, because one image is D1's decision.
  `sourceHosts` is omitted: `AgentRuntime.spec` has no env, so the list rides on the session request
  as `source_hosts` (n8n `SOURCE_HOSTS`), with `DEFAULT_ARTICLE_SOURCE_HOSTS` in the image.
- **2.1/6.1 — the model credential is cross-repo.** The controller refuses a Secret shared by two
  Agents, so the deployment expects `litellm-auth-credentials-article-writer`. Creating it belongs
  to `datahub-local-secrets` and the core fan-out; this change reports it instead of committing a
  secret.
- **3.1 — `ai_model` and `ai_model_fallback` stay.** They are removed from the drafting agent's
  `ai_languageModel` edges but not from the graph: `check_article_llm` still uses them, and a model
  node needs both inputs connected or the activation is refused.
- **3.3/3.4 — the hash check is an excerpt comparison.** An n8n Code node cannot
  `require('crypto')`. `parse_article` and `check_improved_draft` compare the normalised block to
  the `excerpt` the server recorded (whose normalised form is the hash input), and the server still
  writes `sha256` for the ledger's readers.
- **D11 — `kubectl` is not an offline validator in this version.** A client dry-run still needs API
  discovery, so the prompts name `helm template` for a manifest and no longer offer `kubectl` as a
  validator; `kubectl` remains in the image for the session's own attempts.
- **1.6 — `[UNVERIFIED]` the live image.** The adapter pin is rebuilt by the publish workflow; until
  it republishes, the article session runs the old `pi-render` image and `article` returns the
  profile refusal of an older server.
