# Visual render service.
#
# Node 22 is HyperFrames' floor. FFmpeg/FFprobe are what the n8n image does not
# have (the reason a video type could not exist before); the browser is baked in
# at build time so the running container needs no network. The animation runtime
# (GSAP) is a vendored local file, never a CDN, for the same reason.
#
# Multi-arch like every published image here: agents render on amd64, but a
# caller on an arm64 node must be able to pull it too.

FROM node:22-bookworm-slim

# chromium is not optional and not amd64-only work. Google publishes no
# chrome-headless-shell build for linux/arm64 (HyperFrames' platform map has no
# entry for it and `browser ensure` refuses outright), so the browser comes from
# Debian here. On amd64 that also matches what HyperFrames downloads itself —
# it ships the same Chrome for Testing build — so one path serves both
# architectures and what CI builds is what runs. Chromium is set as the default
# browser at the end of this file.
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    ffmpeg \
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

ENV NODE_ENV=production

# HOME must be writable. The deployment runs with readOnlyRootFilesystem, and
# Chrome puts its user data directory under $HOME while HyperFrames caches under
# ~/.cache/hyperframes; with HOME=/home/node on a read-only root Chrome fails
# with "Failed to create headless user data directory container". /tmp is the
# emptyDir the deployment mounts, so a writable HOME is one env change and no
# cluster-side exception.
ENV HOME=/tmp

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY vendor ./vendor
COPY src ./src

# The browser is already in the image via apt; point HyperFrames at it rather
# than letting it attempt a download. HYPERFRAMES_BROWSER_PATH is its first
# choice at render time (findFromEnv), so this is the documented override, and
# `/usr/bin/chromium` is present in the system layout both architectures ship.
ENV HYPERFRAMES_BROWSER_PATH=/usr/bin/chromium

USER node

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD node -e "fetch('http://127.0.0.1:8080/healthz').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", "src/server.mjs"]
