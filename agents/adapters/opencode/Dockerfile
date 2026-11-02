# The OpenCode adapter: the upstream OpenCode server plus the toolchain the agent
# needs to work in this platform's repositories.
#
# This is NOT a Sympozium harness adapter. It implements no harness contract and
# declares no capabilities; it lives under agents/adapters/ only because
# publish-images.yaml discovers every agents/adapters/<dir>/Dockerfile. The image
# in this directory is named datahub-local-ai-opencode-adapter and is consumed by
# datahub-local-core as `opencode serve`.
#
# Debian bookworm, not Alpine: the Python projects need glibc wheels, and helm,
# helmfile, kubectl, kustomize, gh, yq and uv publish glibc builds. The upstream
# ghcr.io/anomalyco/opencode image is Alpine with one Bun binary and no toolchain
# at all, so it cannot render a release or run a test.
#
# Every version below is an ARG with a `# renovate:` line. core/renovate.json reads
# the annotation and the ARG that follows it, so a bump is a one-line PR here and a
# digest PR in core. Do not pin a release-asset sha256: Renovate cannot update it,
# and every bump would break the build until someone edited it by hand.

FROM node:22-bookworm-slim

# The upstream release binary. The glibc build, not the musl one, because the base
# is Debian. `sst/opencode` moved to `anomalyco/opencode`; the tags are unchanged.
# v2 is the current release line; `opencode` is still the executable and
# `opencode serve` is still the server, but the config and API are v2.
#
# Not Renovate-managed: GitHub keeps v1 as the repository's "latest" release, so
# github-releases cannot see the v2 line. publish-images.yaml resolves the newest
# v2 tag and passes it as this build argument; the default is for local builds.
ARG OPENCODE_VERSION=2.2.5
# renovate: datasource=github-releases depName=helm/helm
ARG HELM_VERSION=v4.3.1
# renovate: datasource=github-releases depName=helmfile/helmfile
ARG HELMFILE_VERSION=1.8.2
# renovate: datasource=github-releases depName=kubernetes/kubernetes
ARG KUBECTL_VERSION=v1.37.2
# renovate: datasource=github-releases depName=kubernetes-sigs/kustomize
ARG KUSTOMIZE_VERSION=5.8.3
# renovate: datasource=github-releases depName=mikefarah/yq
ARG YQ_VERSION=v4.54.1
# renovate: datasource=github-releases depName=cli/cli
ARG GH_VERSION=2.103.3
# renovate: datasource=github-releases depName=astral-sh/uv
ARG UV_VERSION=0.13.6
# renovate: datasource=npm depName=@fission-ai/openspec
ARG OPENSPEC_VERSION=1.16.0

# node:22-bookworm-slim carries node and npm for the platform's own scripts. The
# rest are Debian's own builds; they are not version-pinned here because the base
# image is, and the weekly adapter rebuild carries their security fixes.
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    git \
    jq \
    openssh-client \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# One ARG per tool is not enough: the release asset names use three different
# architecture spellings (x64/x86_64/amd64), so map buildx's TARGETARCH once.
ARG TARGETARCH
RUN case "$TARGETARCH" in \
      amd64) opencode_arch=x64; helm_arch=amd64; helmfile_arch=amd64; kubectl_arch=amd64; \
             kustomize_arch=amd64; gh_arch=amd64; uv_arch=x86_64; yq_arch=amd64 ;; \
      arm64) opencode_arch=arm64; helm_arch=arm64; helmfile_arch=arm64; kubectl_arch=arm64; \
             kustomize_arch=arm64; gh_arch=arm64; uv_arch=aarch64; yq_arch=arm64 ;; \
      *) echo "unsupported architecture: $TARGETARCH" >&2; exit 1 ;; \
    esac \
    && tmp=$(mktemp -d) \
    && curl -fsSL "https://github.com/anomalyco/opencode/releases/download/v${OPENCODE_VERSION}/opencode-linux-${opencode_arch}.tar.gz" \
       | tar -xz -C "$tmp" opencode \
    && install -m 0755 "$tmp/opencode" /usr/local/bin/opencode \
    # helm and kubectl publish their binaries from non-GitHub hosts; the version
    # ARGs above are still what Renovate tracks.
    && curl -fsSL "https://get.helm.sh/helm-${HELM_VERSION}-linux-${helm_arch}.tar.gz" \
       | tar -xz -C "$tmp" --strip-components=1 "linux-${helm_arch}/helm" \
    && install -m 0755 "$tmp/helm" /usr/local/bin/helm \
    && curl -fsSL "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${kubectl_arch}/kubectl" \
       -o "$tmp/kubectl" \
    && install -m 0755 "$tmp/kubectl" /usr/local/bin/kubectl \
    && curl -fsSL "https://github.com/helmfile/helmfile/releases/download/v${HELMFILE_VERSION}/helmfile_${HELMFILE_VERSION}_linux_${helmfile_arch}.tar.gz" \
       | tar -xz -C "$tmp" helmfile \
    && install -m 0755 "$tmp/helmfile" /usr/local/bin/helmfile \
    && curl -fsSL "https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv${KUSTOMIZE_VERSION}/kustomize_v${KUSTOMIZE_VERSION}_linux_${kustomize_arch}.tar.gz" \
       | tar -xz -C "$tmp" kustomize \
    && install -m 0755 "$tmp/kustomize" /usr/local/bin/kustomize \
    && curl -fsSL "https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_linux_${yq_arch}" \
       -o "$tmp/yq" \
    && install -m 0755 "$tmp/yq" /usr/local/bin/yq \
    && curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${gh_arch}.tar.gz" \
       | tar -xz -C "$tmp" --strip-components=2 "gh_${GH_VERSION}_linux_${gh_arch}/bin/gh" \
    && install -m 0755 "$tmp/gh" /usr/local/bin/gh-real \
    && curl -fsSL "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-${uv_arch}-unknown-linux-gnu.tar.gz" \
       | tar -xz -C "$tmp" --strip-components=1 \
    && install -m 0755 "$tmp/uv" "$tmp/uvx" /usr/local/bin/ \
    && rm -rf "$tmp"

# `openspec validate --all` is part of the gate in datahub-local, datahub-local-core
# and datahub-local-ai, so the CLI ships here rather than in a session's first
# command. It is npm-only. Installed globally because the agent runs it as uid 1000
# from any checkout, and the npm cache is dropped so the layer stays small.
RUN npm install -g "@fission-ai/openspec@${OPENSPEC_VERSION}" \
    && rm -rf /root/.npm

# The base image ships Python 3.11; datahub-local-ai-mcp requires 3.13. uv owns one
# managed interpreter under /opt so both projects resolve from the same place and
# nothing is downloaded at container start.
ENV UV_PYTHON_INSTALL_DIR=/opt/uv/python
RUN uv python install 3.13 && chmod -R a+rX /opt/uv

# The agent's own files belong to the image, not to a ConfigMap: OpenCode v2 loads
# the machine-wide config from /etc/opencode, git reads /etc/gitconfig, and the
# minter is code. None of it may live under $HOME — the state volume is mounted
# over /opt/data and would hide it. The Firecrawl endpoint is the one
# cluster-specific value and is substituted from OPENCODE_FIRECRAWL_MCP_URL.
# COPY --chmod also applies to a parent directory it creates, which would leave
# /etc/opencode untraversable; create them 0755 first.
RUN mkdir -p /etc/opencode /opt/opencode \
    && chmod 0755 /etc/opencode /opt/opencode

COPY --chmod=0644 opencode.json /etc/opencode/opencode.json
COPY --chmod=0644 AGENTS.md /opt/opencode/AGENTS.md
# No --chmod here: COPY applies it to the directory too, which leaves every skill
# directory mode 0644 and untraversable. Source modes are already 0755/0644.
COPY skills/ /opt/opencode/skills/
RUN chmod -R a+rX /opt/opencode/skills
COPY --chmod=0644 gitconfig /etc/gitconfig
COPY --chmod=0755 git-credential-opencode /usr/local/bin/git-credential-opencode
COPY --chmod=0755 gh-app /usr/local/bin/gh
COPY --chmod=0644 minter.mjs /usr/local/bin/opencode-minter.mjs
COPY --chmod=0644 github-proxy.mjs /usr/local/bin/github-proxy.mjs

# node:22-bookworm-slim already ships uid/gid 1000 as `node`; reuse it rather than
# creating a second account with the same id. The server's HOME is the state volume,
# so OpenCode's own state survives a restart. Created here so the image runs as uid
# 1000 without a root process ever needing to mkdir it.
RUN mkdir -p /workspace /opt/data \
    && chown -R 1000:1000 /workspace /opt/data \
    && usermod --home /opt/data node

# Fail the build, not a session, when a tool is missing or the release asset
# changed shape. `uv python find` proves the managed 3.13 resolves for uid 1000.
USER 1000:1000
ENV HOME=/opt/data
WORKDIR /workspace
RUN set -eux; \
    opencode --version; \
    jq -e '.providers.litellm' /etc/opencode/opencode.json; \
    jq -e '.skills.paths | index("/opt/opencode/skills")' /etc/opencode/opencode.json; \
    jq -e '.mcp.servers.k8s' /etc/opencode/opencode.json; \
    jq -e '.model == "{env:OPENCODE_MODEL}"' /etc/opencode/opencode.json; \
    jq -e '.agents.reviewer.model == "{env:OPENCODE_REVIEW_MODEL}"' /etc/opencode/opencode.json; \
    jq -e '.agents.reviewer.mode == "subagent"' /etc/opencode/opencode.json; \
    test "$(git config --get credential.helper)" = /usr/local/bin/git-credential-opencode; \
    test "$(GITHUB_TOKEN=build-token git-credential-opencode get | sed -n 's/^password=//p')" = build-token; \
    node --check /usr/local/bin/opencode-minter.mjs; \
    node --check /usr/local/bin/github-proxy.mjs; \
    git --version; \
    helm version; \
    helmfile version; \
    kubectl version --client; \
    kustomize version; \
    yq --version; \
    gh --version; \
    test -x /usr/local/bin/gh-real; \
    openspec --version; \
    node --version; \
    npm --version; \
    uv --version; \
    python3 --version; \
    uv python find 3.13

# Upstream's entrypoint shape: core supplies `serve`.
ENTRYPOINT ["opencode"]
