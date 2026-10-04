# Harness adapters

OCI images that let a Sympozium `AgentRun` be driven by an agent harness other than
the built-in `agent-runner`. One directory per adapter, each independently built,
scanned and published by digest.

Sympozium ships the seam, not the harnesses: *"BYO means a contract-compatible
adapter image, not an arbitrary upstream harness image."* An adapter is the image
that makes a particular harness fit — it reads the task the way Sympozium supplies
it, runs the harness, and returns the answer on the result contract.

## Why this repository has its own

The maintained Pi and Hermes adapters **disable tools and skills by design**, which
is right for a chat harness and useless for anything that has to *do* something —
author a file, run a command, read the result. Tool use is the adapter image's
business (*"the harness brings its own, or none"*), so an adapter that enables it is
the documented bring-your-own path, not a workaround.

Each adapter here therefore states, in its own README, which upstream adapter it
derives from, what it enables, and what it costs.

## The contract, in brief

Full detail: [Sympozium — Writing a Harness Adapter](https://deploy.sympozium.ai/docs/modes/harness-adapters/)
and [Harness Mode](https://deploy.sympozium.ai/docs/modes/harness/).
Authoritative upstream sources: [sympozium-ai/harness-adapters](https://github.com/sympozium-ai/harness-adapters).

**In** — environment and mounts:

| | |
| --- | --- |
| `TASK` | the task text (`task.parameters.prompt`), or `/ipc/input/task.json` |
| `SYSTEM_PROMPT` | `spec.systemPrompt`; honour only if you declare `persona` |
| `MODEL_NAME`, `MODEL_BASE_URL`, `MODEL_PROVIDER` | map these onto what the harness reads |
| provider credential | injected per-key by `SecretKeyRef`; never widen the allowlist to make an adapter work |
| `MCP_CONFIG_PATH` | the trusted loopback SkillPack registry, as JSON |
| `HOME` | `/home/agent`, an `emptyDir` — the only writable path besides `/workspace`, `/ipc/output`, `/tmp` |
| `SYMPOZIUM_RESULT_PATH` | where to write the result; read it from env, do not hardcode |
| `SYMPOZIUM_HARNESS_CONTRACT_VERSION` | check it and fail closed on an unknown version |
| `/ipc/control/skip` | a preRun hook found no work; the adapter must check this itself |

`/ipc` is **not** a shared surface: an adapter gets `input/` (read-only),
`control/` (read-only) and `output/`. The rest is absent from its mount namespace,
so a write there fails with "no such file or directory".

**Out** — both are required, because two different readers consume them:

```
__SYMPOZIUM_RESULT__
{"status":"success","response":"...the harness's answer..."}
__SYMPOZIUM_END__
```

plus the same payload at `$SYMPOZIUM_RESULT_PATH`. On failure,
`{"status":"error","error":"..."}` and a non-zero exit. Build the payload with a
JSON encoder (`jq --arg`), never string interpolation: the body is LLM output and
must not be able to forge a result structure.

**Image requirements** — the pod security context is not relaxed for harness mode:

- runs as **UID 1000**, non-root;
- **`readOnlyRootFilesystem: true`** — write only under `$HOME`, `/workspace`,
  `/ipc`, `/tmp`;
- `drop: [ALL]`, RuntimeDefault seccomp;
- its own `ENTRYPOINT`; Sympozium imposes no command;
- **digest-pinned** — a tag is rejected at admission *and* again in the controller.

**Declare capabilities honestly.** `capabilities` (`persona`, `toolFilter`) is the
entire basis on which a run is admitted, because Sympozium did not build the image
and cannot inspect it. Declaring more than the adapter translates means the field is
silently dropped at runtime; declaring less means working runs are rejected. Prefer
stingy — a rejection is a message an operator can act on.

## Adding an adapter

1. Make a directory here, named for the harness and what the adapter adds
   (`pi-render`, not `pi` when it enables more than upstream).
2. Start from the **upstream adapter's Dockerfile** for that harness, so the diff is
   small and reviewable, and record in the README which upstream revision you
   derived from.
3. Keep the pod constraints above. If the harness needs a browser or an encoder, bake
   it in — a run has no network to install it from.
4. Write `README.md` stating: upstream revision, what you enabled or added and why,
   what is **verified** and what is **not**, and the honest cost (who tracks the
   harness's release cadence).
5. Add a publish workflow, digest-pinned, multi-arch like the other images here.

## Deploying one

Three objects, in order, and the ordering matters:

1. **`SympoziumPolicy`** — `harnessPolicy.enabled: true`, plus the image's full
   digest in `imagePolicy.allowedRegistries`. That list is matched by **string
   prefix**: `ghcr.io/datahub-local` without a trailing slash would also admit
   `ghcr.io/datahub-local-evil/…`, so end entries at a `/` or a complete digest.
2. **`AgentRuntime`** — pins the image by digest, declares `contractVersion`, its
   `capabilities`, and a support owner. It must report `Ready` before a run may
   select it.
3. **`Agent`** — `policyRef` plus either `runtimeRef`, or a one-run override with
   `task.mode: harness`.

Nothing here is deployed by this repository's helmfile — these are images. Core
owns the policy objects; see `agents/sympozium/` for the personas that would use
one.
