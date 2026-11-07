# OpenCode adapter

The upstream OpenCode **v2** server **plus the toolchain the agent needs** to work
in this platform's repositories. Built on `node:22-bookworm-slim`, published as
`ghcr.io/datahub-local/datahub-local-ai-opencode-adapter` for `linux/amd64` and
`linux/arm64`, and consumed by `datahub-local-core` as the `opencode-server`
workload (`ENTRYPOINT ["opencode"]`, `args: ["serve", …]`).

**This is not a Sympozium harness adapter.** It implements no harness contract and
declares no capabilities. It lives under `agents/adapters/` only because
`publish-images.yaml` discovers every `agents/adapters/<dir>/Dockerfile`; the image
name and the build context follow from the directory.

See `datahub-local-core/openspec/changes/add-opencode-agent/` for the deployment.

## Upstream revision

- OpenCode `v2`, the glibc `opencode-linux-{x64,arm64}.tar.gz` release
  binary, copied in unpatched.
- The repository moved from `sst/opencode` to `anomalyco/opencode`; the tags did
  not change, and the release asset names are still `opencode-linux-*`.

## Why the upstream image is not deployable

`ghcr.io/anomalyco/opencode` is Alpine with `libgcc`, `libstdc++` and one Bun
binary. It has no `git`, no `helm`, no Python. An `apk --root` init container can
add one binary and still leaves the agent unable to render a release or run a test,
so the image is built here instead.

## What the image carries

| Tool | Pinned by | Why |
| --- | --- | --- |
| `opencode` | `ARG OPENCODE_VERSION` | the server itself |
| `git`, `bash`, `curl`, `openssh-client`, `ca-certificates` | base image | clone, push, fetch |
| `jq`, `yq` | `ARG YQ_VERSION` (`jq` is Debian's) | inspect and edit workflow JSON/YAML |
| `kubectl`, `helm`, `helmfile`, `kustomize` | `ARG …_VERSION` | render and inspect the helmfile releases |
| `gh` | `ARG GH_VERSION` | pull requests, workflow runs. The `gh` on PATH is a wrapper: it asks the git credential helper for the App token and execs `gh-real` |
| `node`, `npm` | base image | the platform's own scripts |
| `python3`, `venv`, `pip` | base image (3.11) | system interpreter |
| `uv` + managed Python 3.13 | `ARG UV_VERSION` | `datahub-local-ai-mcp` requires 3.13 |
| `openspec` | `ARG OPENSPEC_VERSION` | `openspec validate --all`, part of the gate in three repositories |

The agent authenticates as the coder GitHub App, never as a person: `gitconfig`
carries the App's bot identity and noreply address, the credential helper mints an
installation token through the minter sidecar on loopback, and `github-proxy.mjs`
is the same minting shape for the manager side. No token or key is written to disk.

`ansible`, `dbt`, `dlt` and every other project dependency are **not** here: they
come from the checkout's lockfile via `uv sync`, which is the only version that
matches the repository being edited.

## The agent's own files

These are part of the image, not a ConfigMap. The state volume is mounted at
`/opt/data`, so anything baked under `$HOME` would be hidden; v2 reads a
machine-wide config from `/etc/opencode`, and git reads `/etc/gitconfig`.

| Path | What it is |
| --- | --- |
| `/etc/opencode/opencode.json` | model, LiteLLM plugin, the `reviewer` subagent, MCP servers, skills path, permissions, `update: disable` |
| `/opt/opencode/AGENTS.md` | the contract, referenced by `instructions` |
| `/opt/opencode/skills/<name>/SKILL.md` | the detail, loaded on demand: `router` first, then `repo-map`, `taskboard`, `code-shape`, `testing`, `debugging`, `change-shape`, `ship-it`, `review`, `verify` |
| `/etc/gitconfig` | git identity and the credential helper |
| `/usr/local/bin/git-credential-opencode` | answers git from `GITHUB_TOKEN`, else the minter |
| `/usr/local/bin/opencode-minter.mjs` | GitHub App installation-token minter |

The contract is what every turn pays for: who decides what, what is authoritative,
where the work lives, the taskboard flow, the hard boundaries, MCP-before-shell,
the verification rule and the report shape. A rule that must always apply lives
there, not in a skill; everything else is a skill, so a session that does not need
n8n operations does not carry them.

`openspec/changes/rework-codeagent-instructions/` is the record, including why the
split exists and what was rejected.

`opencode-plugin-litellm` registers the provider itself from
`{env:LITELLM_BASE_URL}` and `LITELLM_API_KEY`, so there is no `providers.litellm`
block. The plugin reads the proxy's `/v1/models` response and copies
`max_input_tokens` and `max_output_tokens` into each model's `limit`; OpenCode's
`openai-compatible` provider never reads `/model/info`, so a model declared by hand
would keep its 200000/32000 default instead. Models are discovered, not listed. The
built-in `opencode` provider is disabled. Four values are substituted at runtime:
`{env:LITELLM_BASE_URL}`, `{env:OPENCODE_FIRECRAWL_MCP_URL}`,
`{env:OPENCODE_K8S_MCP_URL}` and `{env:OPENCODE_N8N_MCP_URL}` with its
`{env:OPENCODE_N8N_MCP_TOKEN}` header.
`LITELLM_API_KEY` comes from the environment. `OPENCODE_SERVER_PASSWORD` protects
the API, and `GITHUB_TOKEN` is what the git helper and `gh` authenticate with.

The three MCP servers are the agent's only route to the web, to the cluster and to
n8n. The
Pod's egress policy admits DNS, LiteLLM, the `mcpserver` pods on 8080 and the proxy,
and nothing else, so no direct public rule exists and the Kubernetes API is
unreachable; `kubectl` in the image has neither a credential nor a route. That is
why the k8s server is registered and `kubectl` is not the answer to anything.

## Verified / not verified

Verified by the build: every tool above runs as uid 1000 with `HOME=/opt/data`,
`git config` resolves `/etc/gitconfig`, the plugin pin parses, the skills path
and the k8s entry are present in the config, the n8n entry carries its header,
both model placeholders and the
reviewer agent parse, and the minter passes `node --check`. The build asserts no
individual skill file: the directory is copied whole, and the PR diff is the review.

Not verified here: that a checkout's `uv sync` succeeds against the cluster's PyPI
path, that `helmfile template` resolves every chart through the egress proxy, and
that the plugin's first install from npm completes inside the server's startup
probe. The first two are checked in `datahub-local-core`'s change tasks, in the
running Pod; the plugin was checked the same way, in a throwaway `HOME`.

## Pins and rebuilds

Every toolchain version is a Dockerfile `ARG` with a `# renovate:` annotation;
`renovate.json`'s regex manager reads the annotation and the `ARG` that follows, so
adding a tool needs no new manager. OpenCode is the exception: GitHub keeps **v1**
as the repository's "latest" release, so `github-releases` cannot see the v2 line
and Renovate would never propose a bump. `publish-images.yaml` resolves the newest
v2 tag on every build and passes it as `OPENCODE_VERSION`; the `ARG` default is for
local builds. The base image (`node:22-bookworm-slim`) is deliberately left to the
weekly adapter rebuild, not to Renovate. Release assets are not sha256-pinned:
Renovate cannot bump a checksum, so a pin there would fail every bump until it was
edited by hand.

The plugin is the one dependency not covered by that loop: its version is pinned in
`opencode.json` and bumped by hand, because Renovate would have to know the
`plugins` array and the adapter is rebuilt weekly anyway.

The cluster consumes the result by digest. This image's pin is
`ghcr.io/datahub-local/datahub-local-ai-opencode-adapter: main@sha256:…` in
`datahub-local-core/values/_version.yaml`; after a publish, this repository's pin
job does **not** touch core (it only rewrites `agents/sympozium/values` and
`agents/adapters/*/deploy`), so core's Renovate digest manager raises that PR.
