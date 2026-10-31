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
| `gh` | `ARG GH_VERSION` | pull requests, workflow runs |
| `node`, `npm` | base image | OpenCode's plugin install |
| `python3`, `venv`, `pip` | base image (3.11) | system interpreter |
| `uv` + managed Python 3.13 | `ARG UV_VERSION` | `datahub-local-ai-mcp` requires 3.13 |

`ansible`, `dbt`, `dlt` and every other project dependency are **not** here: they
come from the checkout's lockfile via `uv sync`, which is the only version that
matches the repository being edited.

## The agent's own files

These are part of the image, not a ConfigMap. The state volume is mounted at
`/opt/data`, so anything baked under `$HOME` would be hidden; v2 reads a
machine-wide config from `/etc/opencode`, and git reads `/etc/gitconfig`.

| Path | What it is |
| --- | --- |
| `/etc/opencode/opencode.json` | model, plugin, MCP server, permissions, `update: disable` |
| `/opt/opencode/AGENTS.md` | agent operating rules, referenced by `instructions` |
| `/etc/gitconfig` | git identity and the credential helper |
| `/usr/local/bin/git-credential-opencode` | asks the minter on loopback for a token |
| `/usr/local/bin/opencode-minter.mjs` | GitHub App installation-token minter |

The one cluster-specific value is substituted at runtime: `{env:OPENCODE_FIRECRAWL_MCP_URL}`
is the Firecrawl MCP endpoint. `LITELLM_BASE_URL` and `LITELLM_API_KEY` are read by
the LiteLLM plugin; `OPENCODE_SERVER_PASSWORD` protects the API.

## Verified / not verified

Verified by the build: every tool above runs as uid 1000 with `HOME=/opt/data`,
`git config` resolves `/etc/gitconfig`, the plugin spec parses, and the minter
passes `node --check`.

Not verified here: that a checkout's `uv sync` succeeds against the cluster's PyPI
path, and that `helmfile template` resolves every chart through the egress proxy.
Both are checked in `datahub-local-core`'s change tasks, in the running Pod.

## Pins and rebuilds

Every version is a Dockerfile `ARG` with a `# renovate:` annotation;
`renovate.json`'s regex manager reads the annotation and the `ARG` that follows, so
adding a tool needs no new manager. The LiteLLM plugin is pinned in
`opencode.json` and tracked by a second npm manager. The base image
(`node:22-bookworm-slim`) is deliberately left to the weekly adapter rebuild in
`publish-images.yaml`, not to Renovate. Release assets are not sha256-pinned:
Renovate cannot bump a checksum, so a pin there would fail every bump until it was
edited by hand.

The cluster consumes the result by digest. This image's pin is
`ghcr.io/datahub-local/datahub-local-ai-opencode-adapter: main@sha256:…` in
`datahub-local-core/values/_version.yaml`; after a publish, this repository's pin
job does **not** touch core (it only rewrites `agents/sympozium/values` and
`agents/adapters/*/deploy`), so core's Renovate digest manager raises that PR.
