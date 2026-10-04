# An extended Pi harness adapter with a toolchain, for agentic composition authoring.
#
# It is the upstream Pi adapter's base image plus what authoring needs: a browser
# and an encoder, and Pi's tools enabled. The upstream image is
# node:22.19.0-alpine3.21 + jq + git + @earendil-works/pi-coding-agent, invoked as
# `pi --print --no-tools`. Two things change here and nothing else:
#
#   1. chromium and ffmpeg are installed, and HyperFrames is vendored, so the
#      toolchain is present offline.
#   2. `--no-tools` is dropped, so Pi can write the composition and run the
#      engine's own validation and render commands.
#
# Why fork at all: the maintained Pi adapter disables tools and skills by design
# ("Both continue to disable tools and skills"), which is correct for a chat
# harness and useless for authoring a composition. Tool use is the *adapter
# image's* business — "the harness brings its own, or none" — so this is the
# documented BYO path, not a workaround.
#
# The cost, stated plainly: this tracks Pi's release cadence for the adapter
# itself. Upstream will not maintain this image. See README.md.
#
# It stays inside the contract the platform enforces: UID 1000, read-only root
# filesystem, writes only to $HOME, /workspace, /tmp and the result mount, its
# own ENTRYPOINT, the v1alpha1 result protocol, and a digest-pinned base.

FROM node:22.19.0-alpine3.21@sha256:d4760191131171132bb788c4fd0014ef07a5e4e79e5155e26068f3cc9fdffea4

# The toolchain. Chromium is not optional: HyperFrames renders by seeking a real
# browser, and `lint`/`render` are what Pi runs to check its own work. ffmpeg
# encodes the MP4. ca-certificates and the font packages are what a headless
# browser needs to lay out text that does not shift between runs.
RUN apk add --no-cache \
      jq git chromium ffmpeg \
      ca-certificates ttf-dejavu fontconfig \
      nss freetype harfbuzz ttf-freefont \
    && fc-cache -f

# Same package, same pin, same flags as upstream: lifecycle scripts disabled.
RUN npm install --global --ignore-scripts --no-audit --no-fund \
      @earendil-works/pi-coding-agent@0.84.4

# HyperFrames, vendored into the image so a render needs no network. The version
# is the same one the render service pins, so a composition authored here renders
# identically there.
WORKDIR /opt/hyperframes
COPY package.json package-lock.json ./
RUN npm ci --omit=dev \
    && ln -s /opt/hyperframes/node_modules/.bin/hyperframes /usr/local/bin/hyperframes

# GSAP is a local file, never a CDN — the composition must render offline.
COPY vendor/gsap.min.js /opt/hyperframes/vendor/gsap.min.js

# The authoring skills the agent reads. Three ship inside the pinned HyperFrames
# package — `hyperframes` (routing and the capability map), `hyperframes-cli`
# (the lint/render loop), `media-use`. They arrive with the engine version and
# cannot drift from it, so no vendored copy lives in this repository.
#
# `hyperframes-core` (the composition contract) is NOT in the package: the CLI's
# skills installer fetches it separately. The entrypoint therefore points the
# agent at the bundled set and states the contract inline instead of relying on a
# file that is not there. Verified against hyperframes@0.8.123.
RUN mkdir -p /opt/hyperframes/skills \
    && cp -r /opt/hyperframes/node_modules/hyperframes/dist/skills/. /opt/hyperframes/skills/ \
    && test -f /opt/hyperframes/skills/hyperframes/SKILL.md

RUN mkdir -p /home/agent /workspace && chown -R 1000:1000 /home/agent /workspace /opt/hyperframes

COPY --chmod=0755 entrypoint.sh /usr/local/bin/sympozium-pi-render-adapter

USER 1000:1000
ENV HOME=/home/agent
WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/sympozium-pi-render-adapter"]
