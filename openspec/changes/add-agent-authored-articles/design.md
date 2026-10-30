# Design

## Context

Read off the exports, the adapter and the two drafts.

- `article_creator.workflow.json`: `create_article_ai` (tools `research_sources`, `read_page`,
  `maxIterations` 20) and `create_article_ai_plain` (no tools, 8) share one prompt and feed
  `parse_article`. The prompt's only material is `{{ CONTENT }}`, the entry's `LINK` fetched once by
  `download_content` (an `httpRequest`), plus at most three lookups by the tools.
- `article_content_writer.workflow.json`: `download_content` fetches `LINK` with no size limit and
  `set_link_flags` forwards it as `CONTENT`; gh-80's was a GitHub issue page.
- 2026-10-29 (15259): a *getting started* article, 730/1200 words, zero fences.
- 2026-10-30 (after the structure and margin fixes): numbered sections, four fences, every command a
  placeholder naming where the real one might be.
- `agents/adapters/pi-render/`: one image, Pi with tools, `/v1/chat/completions`, artifacts served
  from `runs/<session>/`, a PVC, 443/8080/9473 egress plus a policy for the gateway; instruction
  files under `/opt/pi-render/prompts/`, chosen at build time, currently `authoring.md` only.

## Decisions

### D1. One adapter image, two profiles

The Pi pin, the toolchain and the adapter contract are already maintained in one place, and a second
image would duplicate the pin and the Renovate grouping. The session server therefore takes a
`profile` on the request (`render`, `article`); the profile picks the instruction file and the
artifact contract. `render` keeps its current behaviour byte for byte — same instruction, same
`out.*`, same conformance — so the studio cannot be affected by this change.

Rejected: a sibling `pi-article` image (a second ~1 GB toolchain, a second Pi pin, a second set of
findings to keep), and a rename of the adapter (a repo-wide change for a naming itch, deferrable).

### D2. A separate session for articles

`article-writer` is its own `HarnessSession`, Deployment and PVC. A render and an article have
different memory profiles, different durations and different retention, and sharing one session would
mean one TTL for both — the render session is swept at seven days and is sized for a Chromium, which
an article does not need.

### D3. The n8n contract does not move

`Article Creator` keeps its trigger inputs and its answer (`text`, `title`, `word_count`, `ERROR`).
The entry point, the review loop, the improvement pass, the asset lane, the publish path and every
test around them are untouched, which is what keeps this change reviewable: the diff is inside one
sub-workflow plus the adapter. The prompt, the gate and the two counters stay where they are.

### D4. The ledger is the mechanism, and the server owns it

The session writes `article.md` and `sources.json`. The ledger lists each fenced line with the URL it
came from. After the turn, the **session server** fetches every distinct URL in the ledger, records
the HTTP status and a hash of the body, and drops entries whose URL does not answer — so a URL the
model invented cannot survive, and the agent is not the authority on whether a source exists.

`parse_article` then does what a count does: every fenced line must appear in the ledger, and a fence
whose ledger entry was dropped is a rejection naming the line and the URL. No model judgement is
involved in "is this command real".

What this does not prove is that the line is *correct for the reader's version* — a quoted command can
be stale. That is what the section's source URL is for, and it is visible to the reader.

### D5. Absence is expressible

A draft with no verifiable commands may not fence a placeholder. If the ledger carries no command
lines, the article is written without a command section and says in one sentence that the project's
documentation could not be read — the `unavailable` rule the reporters already follow, applied to
prose. A fence is therefore always a claim that a source exists, which is the property that separates
the 2026-10-30 draft from a usable one.

### D6. The session reads; it does not run

Egress is 443/8080/9473, there is no kubeconfig and no Docker socket, so the session cannot install
anything and cannot show a command's output. The adapter's instruction says so, the ledger records
`quoted` rather than `ran`, and no artifact may claim a result. Adding execution later means a
disposable cluster and a different change; pretending here would produce confident output the
operator has to disprove.

### D7. The gate reads the ledger, not a memory

`article_review.md` gains `{{ SOURCES }}` (the ledger, as a list of `line — url`) and one check: the
draft's commands, versions and manifest fields are the ones in the ledger. Its fidelity check
currently asks the reviewer to recall the Source Material; a list is cheaper to judge and does not
degrade with the size of the page.

### D8. A fence is matched as a block, not a line

The ledger stores each fenced block **verbatim** with its URL, and the check is "this block, with
whitespace collapsed and trailing spaces dropped, is a contiguous excerpt of the body the server
fetched". Line-level matching would pass `apiVersion: v1` because one line of a 12-line manifest is
common to every page, and would reject a YAML block whose indentation the docs render differently; a
block is the unit the writer actually copied.

Two checks, deliberately independent: the server records `found` and the `sha256` of the normalised
block it matched, and `parse_article` compares the article's block against that hash. An edit that
changes a block without touching the ledger then fails at n8n, not at the server.

### D9. The ledger is persisted on the row

`article_queue.SOURCES` carries the ledger JSON. The improvement pass runs in a later execution and
already reads the draft from `article_drafts`; the ledger rides on the row because that is where
review state already lives (`ARTICLE_STATUS`, `ARTICLE_FEEDBACK`), it is small (one entry per fence),
and a resumed review needs no session that may have been swept.

`update_article_drafted` writes it beside `ARTICLE_REF`, so a human retry, an approval resumed the
next morning and the fidelity re-check all read the same ledger. A missing cell is a report, not a
bypass: the draft is improved, and any fence it carries is unchecked — the pass says so in its note
rather than silently accepting.

### D10. The allowlist is enforced in the pod, not in a prompt

A host allowlist cannot be expressed as a `NetworkPolicy` here (the CNI is not FQDN-aware), and an
instruction is not enforcement. The session server therefore runs a small forward proxy on loopback
and the container sets `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY` to it, so `curl`, `wget` and any tool
built on them honour it; anything off the list answers `403`. The same list gates the server's own
ledger re-fetch.

Hosts come from `ARTICLE_SOURCE_HOSTS` in values — `github.com`, `raw.githubusercontent.com`, the
project's docs host — because the set is a property of what the fleet writes about, not of the code.
**The proxy is the one piece of this change with no precedent in the repo**, and a proxy that misses
a client (a tool not honouring `HTTPS_PROXY`) is a hole rather than a limit; it is called out in the
risks.

### D11. A quoted manifest is validated offline before it is fenced

`helm` and `kubectl` go into the image. The instruction requires a YAML block to be rendered
(`helm template`) or applied with `--dry-run=client` before it is written into the article, and the
ledger records `validated: "dry-run"` or `"none"` plus the failure when one occurred. `parse_article`
rejects a fence whose ledger entry says the validation failed — the article may not carry YAML the
session knows is broken.

This is the middle option on purpose: it catches malformed YAML without a cluster, and it does not
pretend to prove a command runs. `kubectl apply --dry-run=client` validates locally; `helm template`
needs no server. Roughly 100 MB of binaries for that.

### D12. A retry is a correction turn

`MAX_TRIES=3` allows four drafts, and a retry that re-fetched every source would pay the whole first
turn again. `SESSION_ID` is the row (`article-<row_number>`), so a retry continues the session: the
request carries the reviewer's reason and the previous draft, the instruction is "apply this to the
article in this directory, re-reading only what it names", and the fetched corpus stays on disk. A
first attempt is the only authoring turn.

### D13. No feature flag

The drafting half is replaced outright. Rollback is `apply_workflow_changes.py` with the committed
export, which is how every graph change in this repo is reverted; a per-row or values switch would be
a second path to keep correct for a lane with one writer.

## Flow

    n8n Article Creator
      POST /v1/chat/completions  (profile=article, session_id=<row>, brief)
        └─ session: curl the sources, read them, write article.md + sources.json
        └─ server: fetch each ledgered URL, keep what answers
      GET /artifacts/<session>/article.md
      GET /artifacts/<session>/sources.json
      parse_article: H1/body split, budget, markers, ledger check
      → the existing review loop

## Risks

- **The allowlist proxy is new machinery on the request path.** A client that ignores `HTTPS_PROXY`
  bypasses it, and a proxy bug fails every fetch. It is the one part of this change with no
  precedent here, so it ships with a test that a blocked host is refused *through* the proxy and not
  merely by the instruction.

- **Latency and cost.** A turn that fetches five pages is minutes, not seconds, and the drafting loop
  may retry it. Mitigation: the ledger makes a retry cheaper for the *same* sources (the session keeps
  its directory), and `SESSION_ID` is the row, so a retry continues rather than re-fetches.
- **A docs site that needs JavaScript** yields nothing to `curl`. The session falls back to the
  repository's own files (`raw.githubusercontent.com`), and if neither answers, D5 applies.
- **The server's fetch is an SSRF surface.** It only fetches URLs the model wrote, which is
  attacker-controlled if the entry's link is. Restrict to https, refuse private ranges and the
  cluster's own addresses, cap body size and redirects — in the server, not in the prompt.
- **A quoted command can be wrong for the reader's version.** Accepted and made visible: the section
  cites its URL, and the article does not claim a version it did not read. A dry-run proves the YAML
  parses, never that the version is the reader's.
- **The ledger hash can be satisfied by a block the session edited.** The check is "the article's
  block is the block the server found"; a session that fetches a page, edits it and ledgeres its own
  edit passes. That is why the ledger stores the fetched excerpt and the URL, and why the gate reads
  both: the server proves the page exists, the gate reads whether the quote is of that page.
- **[UNVERIFIED] the model can write a good article from a fetched corpus at all.** This is the same
  open question the render adapter's first live run answered; here it is answered by one run on a row
  whose docs exist, read at the review notification.

## Open questions

- Whether the ledger should also carry non-fenced claims (a number, a version) with their source.
  Deferred: the fence is where the harm is, and a ledger for every sentence is a second article.
- Whether the correction turn should be capped by wall clock (`runTimeout`) rather than by attempts.
  Deferred to the first measurements: four turns against a session that keeps its corpus should be
  cheaper than one cold turn, and the numbers will say whether that is true.

## Definition of done

- The adapter serves `profile=article` and returns `article.md` + `sources.json`; `profile=render`
  is unchanged, proven by the studio's own tests and one render.
- The session server fetches every ledgered URL, drops the ones that do not answer, refuses
  non-https and private addresses, and caps size.
- `parse_article` rejects a fenced line absent from the ledger, and a fence whose ledger entry was
  dropped, naming the line and the URL; the twin check in the improvement pass agrees.
- A draft with no ledger commands carries no fence, and says why.
- A fenced block passes only when the server found it in the page it cites **and** the article's
  block still hashes to the excerpt the server recorded.
- A fetch outside the allowlist answers 403 through the proxy, with the proxy doing the refusing.
- A YAML block whose dry-run failed is rejected naming the failure.
- The `agents/n8n` suite and `openspec validate --all` pass.
- [UNVERIFIED] live: one article reading its own sources, reviewed by a human, with every fenced
  command traceable to a URL. The adapter must be applied and the session running before the
  workflow is, or every run fails on an unreachable URL.
