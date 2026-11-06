// The writer image owns its own toolchain, and it is not the render lane's.
//
// pi-render carries a browser, an encoder and a vendored engine because it renders.
// This image carries curl and helm because it reads and quotes. These assertions keep
// the two from drifting back into one another by copy-paste.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { test } from "node:test";

const here = dirname(fileURLToPath(import.meta.url));
const dockerfile = readFileSync(join(here, "..", "Dockerfile"), "utf8");
const guide = readFileSync(join(here, "..", "prompts", "writing.md"), "utf8");

test("the image installs what the guide tells the model to use", () => {
  assert.match(dockerfile, /FROM node:22-bookworm-slim/);
  // The guide names `curl` for reading and `helm template` for validating. A named
  // command that is not in the image is a turn that fails at the first section. The
  // checks read the install lines, not the word anywhere in the file: `curl` also
  // appears in the helm download, and a comment is not an installation.
  for (const command of ["curl", "jq"]) {
    assert.match(
      dockerfile,
      new RegExp(`apt-get install[\\s\\S]*?\\n\\s+${command}\\b`),
      `the apt block does not install ${command}`
    );
  }
  assert.match(dockerfile, /install -m 0755 "\/tmp\/linux-\$\{arch\}\/helm" \/usr\/local\/bin\/helm/);
  assert.match(guide, /curl -fsSL/);
  assert.match(guide, /helm template/);
});

test("the image is the writer's, not the render lane's", () => {
  for (const absent of ["chromium", "ffmpeg", "hyperframes", "/opt/hyperframes"]) {
    assert.ok(!dockerfile.includes(absent), `the writer image carries ${absent}, which it does not use`);
  }
  // kubectl is named in the guide only to say it proves nothing; it is deliberately
  // not installed, because a client dry-run needs the API's discovery.
  assert.ok(!/dl\.k8s\.io|install -m 0755 .*kubectl/.test(dockerfile), "the image installs kubectl");
});

test("helm is pinned per architecture with its published checksum", () => {
  assert.match(dockerfile, /ARG HELM_VERSION=\d+\.\d+\.\d+/);
  assert.match(dockerfile, /dpkg --print-architecture/);
  for (const arch of ["amd64", "arm64"]) {
    assert.ok(dockerfile.includes(`${arch})`), `the build has no pin for ${arch}`);
  }
  assert.match(dockerfile, /sha256sum -c -/);
  assert.match(dockerfile, /helm version --short/);
});

test("Pi is installed at a pinned version", () => {
  assert.match(dockerfile, /ARG PI_VERSION=\d+\.\d+\.\d+/);
  assert.match(dockerfile, /@earendil-works\/pi-coding-agent@\$\{PI_VERSION\}/);
  assert.match(dockerfile, /--ignore-scripts/);
});

test("the prompts are files in the image and the server is the entrypoint's dispatch", () => {
  assert.match(dockerfile, /COPY --chmod=0644 prompts\/ \/opt\/pi-writer\/prompts\//);
  assert.match(dockerfile, /COPY --chmod=0755 session-server\.mjs \/usr\/local\/bin\/sympozium-pi-writer-session/);
  assert.match(dockerfile, /COPY --chmod=0644 session-lib\.mjs \/usr\/local\/bin\/session-lib\.mjs/);
  assert.match(dockerfile, /ENTRYPOINT \["\/usr\/local\/bin\/sympozium-pi-writer-adapter"\]/);
});

test("the image runs unprivileged with a writable home", () => {
  assert.match(dockerfile, /USER 1000:1000/);
  assert.match(dockerfile, /ENV HOME=\/home\/agent/);
  assert.match(dockerfile, /chown -R 1000:1000/);
});

test("the entrypoint refuses a contract it cannot serve", () => {
  const entrypoint = readFileSync(join(here, "..", "entrypoint.sh"), "utf8");
  assert.match(entrypoint, /v1alpha2/);
  assert.match(entrypoint, /sympozium-pi-writer-session/);
  assert.match(entrypoint, /serves v1alpha2 sessions only/);
});
