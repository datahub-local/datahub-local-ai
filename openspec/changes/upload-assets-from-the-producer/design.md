# Design

## Context

n8n saves an execution's node inputs and outputs as one unit, per workflow. There is no
per-node opt-out, so a workflow either records nothing about a successful run or records
everything that passed through it. The studio's payload *is* the artifact, which is why
`saveDataSuccessExecution` was set to `none` on the four workflows that carry one.

The archived `store-visual-studio-assets-in-s3` change moved the bytes to Garage but kept
them inside the workflow: `prepare_uploads` decoded `IMAGE`'s data URL back into binary
and the S3 node uploaded that. The base64 string in `agent_result` was never removed, and
it is the node output, so it is still what n8n persists.

The invariant this change is written against is therefore:

> An execution n8n saves may contain the asset's *coordinates*, and never its bytes.

Binary is not a loophole. n8n writes binary data to its own store when it saves an
execution, so a courier design adds ~60 MB per video run to `binary_data` instead of to
`execution_data`.

## Gate findings

All measured on 2026-10-14 against the live cluster.

| What | Result |
|---|---|
| `binary_data` | **249 MB, 903 rows** — binaries are persisted in Postgres |
| `execution_data` | **1060 MB, 1405 rows**; database 1335 MB |
| `N8N_DEFAULT_BINARY_DATA_MODE` | unset; the studio's own comment records `database:<id>` references |
| Code node `require('crypto')` | **`Module 'crypto' is disallowed`** (probe execution `13361`, workflow deleted) |
| Garage presigned PUT / GET | **200 / 200** on `datahub-local-temp` |
| session pod egress | DNS plus ports 443, 8080, 9473 with **no destination selector**; 3900 is not allowed |

The third and fourth rows together are what decide the shape: n8n cannot mint a presigned
URL, and a mounted key would be one. A key in a pod that runs model-authored code with a
shell — the composer calls `ffmpeg`, `ffprobe` and `hyperframes render` — is readable by
that code and postable out over the 443 egress the pod already has.

## Decisions

**The producer uploads.** The session server holds the bytes at the end of the turn, so
it writes them and reports the key. This is the only shape in which no n8n execution ever
holds the asset, and it needs no signer.

**The studio composes the key.** `build_author_brief` already derives
`visual-studio/<RUN_ID>-<ASSET_TYPE>.<ext>` for `prepare_uploads`, and the prune lists the
`visual-studio/` prefix. Keeping key composition in the workflow means the convention
stays in one place and the adapter is handed a destination rather than inventing one. The
adapter validates it and refuses to write outside the prefix.

**The credential is scoped, not detected.** A Garage key with write access to
`datahub-local-temp` and nothing else. The blast radius is then a temp bucket that is
pruned on a two-day window. This is an accepted risk rather than an eliminated one, and
`MEMORY.md` records that the alternative — a presigned URL — is unavailable only because
n8n cannot sign. If n8n ever gains a signer, that becomes the better design.

**The request is signed and sent by the AWS SDK, not by hand.** The first version of this
change hand-rolled SigV4 in `session-lib.mjs` and verified it two ways — its canonical
request and string-to-sign against botocore's `S3SigV4Auth`, and the headers it produced
against Garage live (`PUT 200`, `GET 200`, `DELETE 204`). It worked. It was still the
wrong call: `@aws-sdk/client-s3` does the signing, the streaming PUT, the retries and the
error classification for less code than the signer alone, and it was **measured working
against this Garage with its defaults** (path-style, region `homelab`, `PUT ok | GET ok`
with the exact body, `DELETE ok`, no checksum workaround needed) — so the hand-rolled
version and its vectors were removed rather than kept alongside it. The repository's
`renovate.json` already manages this `package.json`, the image is built in CI and consumed
by an auto-pinned digest, so the dependency costs a CI round trip and nothing manual.

**The SDK cannot live in `session-lib.mjs`.** That file's tests run in CI under
`node --test` with **no `npm ci`**, because it imports only node builtins — so anything
needing a dependency breaks that job, and it breaks as a module-not-found that reads like
a broken test rather than a misplaced dependency. The signing and the PUT therefore live
in `session-server.mjs`; what stays in the pure module is the policy, and a test asserts
the builtins-only property so a future dependency cannot be added there by accident.

**A failed upload fails the run.** The response reports the failure and no key, so no
caller can be handed a key for an object that was never written — the same rule
`upload_assets` follows by having no `onError`.

**The artifact stays on the volume.** `/tmp/aivideo/runs/<session>/` and the
`/artifacts/<session>/out.<ext>` route are unchanged, so `Visual Studio Test`, the
`fetch-artifact.mjs` script and a diagnosis after a failed upload all still work.

**Recording is verified by measurement, not by trust.** The acceptance test for enabling
`saveDataSuccessExecution` is the delta of `execution_data` and `binary_data` across a
known image run and a known composer run, recorded in the change. If a composer run moves
those numbers by megabytes, the invariant is not met and the change is not done.

## Considered: an MCP storage service

Raised as "MCP s3 server?". There is none: the catalog is `facts`, `semantic`,
`semantic-finance`, `argocd`, `github`, `grafana`, `k8s`, `postgres`, `slack`, `trino`.
The only storage credential is `mcp-s3-token`, on `homelab-facts` as `GARAGE_ADMIN_URL`
and `GARAGE_ADMIN_TOKEN` — Garage's admin API on 3903 for read-only reporting, not an S3
client. That server's posture is read-only by design: an enumerated read-only ClusterRole
and prompts that are report contracts.

So the idea is real but is not "reuse what exists" — it is a new tool, in another repo
(`datahub-local-ai-mcp`), and the better shape of it is **presign**, not upload: the
service signs a PUT for one key, the sandbox performs it, and then no credential exists in
the sandbox and the bytes are never copied a second time. It needs an S3 key of its own,
never the admin token, which is strictly more privileged than the bucket key this change
is trying to avoid.

Reachability is not the obstacle: the session pod's egress rule already allows port 8080
to *any* destination, so it can call an in-cluster service today with no policy change.
The obstacle is that a cross-repo write tool is a larger change than a scoped key, and the
credential it removes — a write-only key on a two-day temp bucket — is the smaller risk of
the two. Reopen this if the scope of that key ever needs to widen beyond
`datahub-local-temp`.

## Other security-sensitive code, reviewed

Because the trigger for using the SDK was "would this suffer an attack", the rest of the
repository's security-sensitive code was reviewed for the same pattern — hand-rolled
where a maintained library belongs:

| Surface | What it uses | Verdict |
|---|---|---|
| Enable Banking auth (`workflows/dlt/projects/finance/providers/enablebanking.py`) | **PyJWT** `RS256` and **httpx** | already a library; `mint_jwt` is 12 lines of claims |
| Slack delivery hook (`agents/sympozium/files/deliver-slack.py`) | stdlib `urllib.request` over HTTPS | stdlib, TLS verified by default, no `ssl`/`verify` override anywhere |
| Artifact serving (`session-server.mjs` + `resolveArtifact`) | session-id allowlist, artifact-name allowlist, `basename` equality, `normalize` + prefix check | the safe pattern; a framework's defaults would not be stricter |
| `fetch-artifact.mjs` | `md5` of the fetched bytes | an integrity check on a developer fetch, not a security boundary |

Nothing there needs replacing. The one genuine hand-rolled-crypto case in the repository
was this change's own signer, and it is gone.

## The still path cannot be byte-free

The Gemini response is created inside n8n, so its bytes pass through that workflow
whatever happens afterwards. What this change removes there is the *data URL* — the
`omImage` JSON `convert_image` decodes — so the bytes travel as binary and the record
carries ~0.9 MB of `binary_data` per still post instead of ~1.2 MB of payload.

Whether the model's own `b64_json` can also go depends on the gateway accepting
`response_format: url`, which would let the image be fetched as a file instead. That is
`[UNVERIFIED]`; if it is unsupported, the model's base64 stays in that one execution and
this document records it rather than claiming otherwise.

## Risks

- **Hand-rolled SigV4** is the most likely thing to be subtly wrong. Vectors plus a live
  PUT probe before any workflow depends on it.
- **The pod now writes to shared storage.** A wrong key is possible; the prefix check and
  the request-scoped destination bound it, and the prune bounds the residue.
- **Egress widening.** 3900 to `data` is added to a pod whose egress was already open on
  443 to any destination. The credential, not the reachability, is the sensitive part.
- **Two writers, one convention.** The studio names the object and the prune deletes it;
  a change to the key shape has to be made in both, and the prune's test asserts the
  prefix rather than a full key, which is what it already needs.

## Open questions

- Does the image gateway accept `response_format: url`? Gates task 6.2 only.
- Does a Garage key support prefix-level restriction, which would narrow the scope below
  a whole bucket? A bucket-level write-only key is the floor and is used either way.

## Definition of done

- A composer run's asset is written by the session server and fetchable from Garage using
  only the key in the response.
- A composer run adds **no** asset bytes to `execution_data` or `binary_data`, measured.
- `saveDataSuccessExecution` is `all` on the four workflows, and a successful run is
  visible in n8n with its nodes and their outputs.
- Publishing works from the key: the animated path and the still path both publish an
  approved asset without a data URL anywhere.
- The full test suites pass, the adapter's SigV4 has vectors, `openspec validate --all`
  passes, and `AGENTS.md` records the invariant and the credential's accepted risk.
