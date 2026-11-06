# The Pi writer adapter: a Sympozium harness adapter that lets an agent draft an
# article from sources it actually read.
#
# It is a separate image from pi-render on purpose. The render adapter carries a
# browser, an encoder and a vendored engine because it renders; this one carries a
# text toolchain because it reads and writes. One shared image meant each lane
# carried the other's toolchain, and one prompt directory held two unrelated
# instructions.
#
# Multi-arch like every published image here: agents are scheduled onto the arm64
# nodes, and an amd64-only image is unschedulable there.
#
# Platform constraints are satisfied below: UID 1000, a writable $HOME, and a
# read-only root filesystem with everything the contract requires on it.

FROM node:22-bookworm-slim

# curl is the only way the session reads a page (Pi's bash has no HTTP client), and
# jq builds the contract's result payload with `--arg`, so LLM output cannot forge a
# result structure.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Pi, installed exactly as the upstream adapter installs it: the pinned package,
# lifecycle scripts disabled. It is pure JS — verified to install and run on this
# image's Debian/glibc, not only on Alpine.
ARG PI_VERSION=1.4.0
RUN npm install --global --ignore-scripts --no-audit --no-fund \
    "@earendil-works/pi-coding-agent@${PI_VERSION}"

# A quoted manifest is validated offline before the article fences it, and
# `helm template` is that validator: it renders a chart with no server. `kubectl` is
# deliberately absent — even `--dry-run=client` asks the API for discovery, so it
# cannot serve as an offline check and no instruction here offers it.
ARG HELM_VERSION=4.3.1
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
      amd64) helm_sha=0403a88ae20913d11b10a2467b50087721fea7581736da6b9d3992f5357fe54b ;; \
      arm64) helm_sha=8cf8f66ecbc252ac8f7f06cca68aba88508ddfde3a6a34feb1678ad1694b4f88 ;; \
      *) echo "unsupported architecture: $arch" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/helm.tgz "https://get.helm.sh/helm-v${HELM_VERSION}-linux-${arch}.tar.gz"; \
    echo "${helm_sha}  /tmp/helm.tgz" | sha256sum -c -; \
    tar -xzf /tmp/helm.tgz -C /tmp "linux-${arch}/helm"; \
    install -m 0755 "/tmp/linux-${arch}/helm" /usr/local/bin/helm; \
    rm -rf /tmp/helm.tgz "/tmp/linux-${arch}"; \
    helm version --short

# The drafting prompts live here, not in n8n: the caller sends the entry's fields and the
# session server renders the brief from these files at run time. Copied world-readable
# because the agent runs as UID 1000.
RUN mkdir -p /opt/pi-writer/prompts
COPY --chmod=0644 prompts/ /opt/pi-writer/prompts/

# $HOME must stay writable: Pi writes its provider config and transcripts there, and
# a read-only root filesystem means anything else fails at the first turn.
RUN mkdir -p /home/agent /workspace \
    && chown -R 1000:1000 /home/agent /workspace /opt/pi-writer

COPY --chmod=0755 entrypoint.sh /usr/local/bin/sympozium-pi-writer-adapter
# The v1alpha2 session endpoint. The entrypoint dispatches to it on the contract
# version; a Job is refused by name because an article needs the session directory.
COPY --chmod=0755 session-server.mjs /usr/local/bin/sympozium-pi-writer-session
# Pure helpers imported by the session server: paths, the ledger and Pi's settings.
COPY --chmod=0644 session-lib.mjs /usr/local/bin/session-lib.mjs

USER 1000:1000
ENV HOME=/home/agent
# A writer's heap is small next to a render's, and the cgroup limit here is the
# session's own. A cap keeps a runaway turn from growing into it.
ENV NODE_OPTIONS=--max-old-space-size=1024
WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/sympozium-pi-writer-adapter"]
