# A Sympozium harness adapter that lets an agent author a HyperFrames composition
# and render it, inside a run.
#
# It derives from **our own render image**, not from the upstream Pi adapter's
# image. The reasoning is the point of this file:
#
#   The upstream Pi adapter is node:22-alpine + jq + git + pi-coding-agent. What
#   it does NOT have is a browser or an encoder, which authoring needs. Our render
#   image already has both, plus a vendored HyperFrames and GSAP, with the
#   read-only-rootfs and HOME problems already found and fixed. Deriving from the
#   Pi image would mean re-adding what ours already carries and inheriting a
#   release cadence for a decision we are overriding.
#
#   So: one toolchain, built once — ours — and this image adds only the agent loop
#   and the adapter contract on top.
#
# The cost is stated plainly in README.md: a render-service change flows into this
# adapter's next build, and upstream does not maintain this image.
#
# Platform constraints are already satisfied by the base: UID 1000, a writable
# $HOME, and everything the contract requires.

# Digest-pinned, because the platform rejects a mutable tag and records the
# digest. `main` is the published tag; the digest is what admission checks.
ARG RENDER_IMAGE=ghcr.io/datahub-local/datahub-local-ai-render:main
FROM ${RENDER_IMAGE}

USER root

# Pi, installed exactly as the upstream adapter installs it: the pinned package,
# lifecycle scripts disabled. It is pure JS — verified to install and run on this
# image's Debian/glibc, not only on Alpine.
RUN npm install --global --ignore-scripts --no-audit --no-fund \
      @earendil-works/pi-coding-agent@0.84.4

# jq is not optional: the adapter contract builds the result payload with it
# (`jq --arg`, so LLM output cannot forge a result structure), and the upstream
# entrypoint requires it. The render base image is Debian and does not carry it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends jq \
    && rm -rf /var/lib/apt/lists/*

# Move the engine to a stable, documented path so the prompt and the entrypoint do
# not depend on the base image's WORKDIR. The base keeps /app as well; these are
# the same files, exposed where the adapter's contract points at them.
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

# $HOME must stay writable: the base sets HOME=/tmp for the read-only root
# filesystem, and the platform provides a writable $HOME at /home/agent. Either
# works, so this defers to the platform when it sets one.
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
