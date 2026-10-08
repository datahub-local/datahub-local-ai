# The Pi render adapter: a Sympozium harness adapter that lets an agent author a
# HyperFrames composition and render it inside a run.
#
# This image owns its own toolchain. It used to derive FROM the visual render
# service's image, but that service is retired, so the toolchain it carried — a
# browser, an encoder and a vendored HyperFrames — is built here directly from
# node:22-bookworm-slim. Deriving from the upstream Pi adapter's image was never
# an option: it is node:22-alpine + jq + git + pi-coding-agent with no browser and
# no encoder, which is exactly what authoring needs.
#
# Multi-arch like every published image here: agents are scheduled onto the arm64
# nodes, and an amd64-only image is unschedulable there.
#
# Platform constraints are satisfied below: UID 1000, a writable $HOME, and a
# read-only root filesystem with everything the contract requires on it.

FROM node:22-bookworm-slim

# Chromium is not optional and not amd64-only work. Google publishes no
# chrome-headless-shell build for linux/arm64 (HyperFrames' platform map has no
# entry for it and `browser ensure` refuses outright), so the browser comes from
# Debian here. On amd64 that also matches what HyperFrames downloads itself, so
# one path serves both architectures. FFmpeg is what produces a caller's GIF from
# the engine's MP4; the fonts are fallbacks for the brand faces.
#
# jq is not optional either: the adapter contract builds the result payload with
# it (`jq --arg`, so LLM output cannot forge a result structure).
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    ffmpeg \
    jq \
    ca-certificates \
    fonts-dejavu-core \
    fontconfig \
    libgbm1 \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libcups2 \
    libasound2 \
    libpangocairo-1.0-0 \
    libxshmfence1 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -fv

# The browser is already in the image via apt; point HyperFrames at it rather than
# letting it attempt a download. HYPERFRAMES_BROWSER_PATH is its first choice at
# render time (findFromEnv), and `/usr/bin/chromium` is present in the system
# layout both architectures ship.
ENV HYPERFRAMES_BROWSER_PATH=/usr/bin/chromium

WORKDIR /app

# The engine and its runtime are this image's own dependencies, so the build no
# longer depends on another image's layout.
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY vendor/gsap.min.js ./vendor/gsap.min.js

# Pi, installed exactly as the upstream adapter installs it: the pinned package,
# lifecycle scripts disabled. It is pure JS — verified to install and run on this
# image's Debian/glibc, not only on Alpine.
RUN npm install --global --ignore-scripts --no-audit --no-fund \
      @earendil-works/pi-coding-agent@0.84.4

# Move the engine to a stable, documented path so the prompt and the entrypoint
# do not depend on the build directory.
RUN mkdir -p /opt/hyperframes /opt/pi-render/prompts \
    && cp -r /app/node_modules /opt/hyperframes/node_modules \
    && ln -s /opt/hyperframes/node_modules/.bin/hyperframes /usr/local/bin/hyperframes \
    && mkdir -p /opt/hyperframes/vendor \
    && cp /app/vendor/gsap.min.js /opt/hyperframes/vendor/gsap.min.js \
    && mkdir -p /opt/hyperframes/skills \
    && cp -r /opt/hyperframes/node_modules/hyperframes/dist/skills/. /opt/hyperframes/skills/ \
    && test -f /opt/hyperframes/skills/hyperframes/SKILL.md

# The authoring instruction is a prompt file, never inlined in the entrypoint: the
# repository's rule is that prompts are files, read at run time, so the text is
# reviewable on its own and not buried in shell. Copied world-readable: the agent
# runs as UID 1000 and reads it.
COPY --chmod=0644 prompts/authoring.md /opt/pi-render/prompts/authoring.md

# $HOME must stay writable: a read-only root filesystem means Chrome fails with
# "Failed to create headless user data directory container" unless HOME points at
# a writable mount. The platform provides one at /home/agent.
RUN mkdir -p /home/agent /workspace \
    && chown -R 1000:1000 /home/agent /workspace /opt/hyperframes /opt/pi-render

COPY --chmod=0755 entrypoint.sh /usr/local/bin/sympozium-pi-render-adapter
# The v1alpha2 session endpoint. The entrypoint dispatches to it on the contract
# version, so one image serves both the one-shot Job and the long-lived session.
COPY --chmod=0755 session-server.mjs /usr/local/bin/sympozium-pi-render-session
# Pure helpers imported by the session server (artifact paths and output formats).
COPY --chmod=0644 session-lib.mjs /usr/local/bin/session-lib.mjs

USER 1000:1000
ENV HOME=/home/agent
# Cap V8's heap at the image level so a render collects rather than growing into
# whatever cgroup limit it is given. A Job's agent container is hardcoded to 1Gi by
# the controller and no CRD field reaches it, so a cap here is what keeps a
# Node-based render from being OOMKilled there; a session Deployment honours
# AgentRuntime.spec.resources, so it can be raised rather than capped. Setting it
# in the image means neither path depends on the caller remembering.
ENV NODE_OPTIONS=--max-old-space-size=2048
WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/sympozium-pi-render-adapter"]
