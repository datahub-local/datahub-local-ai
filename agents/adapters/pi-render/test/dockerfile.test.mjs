// The adapter must own its toolchain.
//
// It used to derive FROM the visual render service's image, which is retired: the
// base's layout changed to /app/render/node_modules and the adapter's copy of
// /app/node_modules broke every build. These assertions keep the image
// self-contained, so the same mistake cannot come back quietly.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { test } from "node:test";

const here = dirname(fileURLToPath(import.meta.url));
const dockerfile = readFileSync(join(here, "..", "Dockerfile"), "utf8");
const pkg = JSON.parse(readFileSync(join(here, "..", "package.json"), "utf8"));

test("the adapter does not derive from the retired render image", () => {
  assert.ok(
    !dockerfile.includes("datahub-local-ai-render"),
    "the Dockerfile still references the retired render image"
  );
  assert.ok(
    !/FROM\s+\$\{?RENDER_IMAGE/.test(dockerfile),
    "the Dockerfile still has a RENDER_IMAGE base"
  );
});

test("the adapter builds its own browser and encoder", () => {
  assert.match(dockerfile, /FROM node:22-bookworm-slim/);
  for (const pkgName of ["chromium", "ffmpeg", "curl", "jq"]) {
    assert.ok(dockerfile.includes(pkgName), `the base does not install ${pkgName}`);
  }
  assert.match(dockerfile, /ENV HYPERFRAMES_BROWSER_PATH=\/usr\/bin\/chromium/);
});

test("the adapter installs a pinned validator for a quoted manifest", () => {
  // The article profile reads the network with curl and renders a quoted YAML block with
  // helm before fencing it. Both are pinned per architecture with their published
  // checksums, because a build that follows "latest" is a different image next week.
  assert.match(dockerfile, /ARG HELM_VERSION=\d+\.\d+\.\d+/);
  assert.match(dockerfile, /ARG KUBECTL_VERSION=\d+\.\d+\.\d+/);
  assert.match(dockerfile, /dpkg --print-architecture/);
  for (const arch of ["amd64", "arm64"]) {
    assert.ok(dockerfile.includes(`${arch})`), `the build has no pin for ${arch}`);
  }
  assert.match(dockerfile, /sha256sum -c -/);
  assert.match(dockerfile, /helm version --short/);
});

test("the adapter installs HyperFrames from its own manifest", () => {
  assert.match(dockerfile, /COPY package\.json package-lock\.json/);
  assert.match(dockerfile, /npm ci --omit=dev/);
  assert.match(dockerfile, /COPY vendor\/gsap\.min\.js/);
  assert.ok(pkg.dependencies.hyperframes, "the toolchain manifest has no hyperframes dependency");
});

test("the contract comes from the engine binary, not a fetched skill tree", () => {
  // The npm package is the only upstream artifact this image trusts: its version is in the
  // lockfile, so it moves when a bump is accepted and not when upstream reorganises a
  // repository. What this replaces: the build fetched `skills/` from the release tag and
  // asserted eight directories, and v0.8.185 consolidated them, so every build failed on a
  // layout that had nothing to do with this adapter.
  assert.ok(pkg.dependencies.hyperframes, "the engine is not a dependency");
  assert.ok(
    !/codeload\.github\.com/.test(dockerfile),
    "the build fetches from a release tag again; that tree is upstream's to move"
  );
  assert.ok(
    !/dist\/skills/.test(dockerfile),
    "the build copies a skill tree again; the guide reads the binary's docs instead"
  );
  assert.match(dockerfile, /hyperframes docs "\$topic"/);
  assert.match(dockerfile, /missing docs topic in the engine/);
});

test("every docs topic the guide names is one the build asserts", () => {
  // The guide and the engine drifted the moment upstream consolidated its skill tree at
  // v0.8.185: the guide still sent the composer to hyperframes-core/-animation, and only the
  // image build noticed. The same pair is read here, so a removed topic fails offline.
  const guide = readFileSync(join(here, "..", "prompts", "authoring.md"), "utf8");
  const named = [...new Set(guide.match(/hyperframes docs ([a-z][a-z-]*)/g) ?? [])].map((m) =>
    m.replace("hyperframes docs ", "")
  );
  assert.ok(named.length > 0, "the guide names no docs topic, so this check would be vacuous");
  assert.ok(named.includes("compositions"), "the guide does not name the composition contract");
  for (const topic of named) {
    assert.match(dockerfile, new RegExp(`\\b${topic}\\b`), `the guide names "${topic}", which the build does not assert`);
  }
});

test("both profile instructions are baked into the image", () => {
  // The session picks the instruction by profile, so a missing copy is a turn that
  // reports a missing prompt rather than the method it was asked for.
  for (const name of ["authoring.md", "article.md"]) {
    assert.match(
      dockerfile,
      new RegExp(`COPY --chmod=0644 prompts/${name.replace(".", "\\.")} /opt/pi-render/prompts/`),
      `the image does not carry prompts/${name}`
    );
  }
});
