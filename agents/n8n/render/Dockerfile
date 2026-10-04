# Visual render service.
#
# Node 22 is HyperFrames' floor. FFmpeg/FFprobe are what the n8n image does not
# have (the reason a video type could not exist before); Chrome headless shell is
# baked in at build time so the running container needs no network. The animation
# runtime (GSAP) is a vendored local file, never a CDN, for the same reason.
#
# Multi-arch like every published image here: agents render on amd64, but a
# caller on an arm64 node must be able to pull it too.

FROM node:22-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
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
ENV HOME=/home/node

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY vendor ./vendor
COPY src ./src

# Bake the headless browser into the image so a render never downloads one.
RUN ./node_modules/.bin/hyperframes browser ensure \
    && chown -R node:node /home/node/.cache

USER node

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD node -e "fetch('http://127.0.0.1:8080/healthz').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", "src/server.mjs"]
