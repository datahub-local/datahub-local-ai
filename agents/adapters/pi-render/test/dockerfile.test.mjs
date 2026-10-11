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
  for (const pkgName of ["chromium", "ffmpeg", "jq"]) {
    assert.ok(dockerfile.includes(pkgName), `the base does not install ${pkgName}`);
  }
  assert.match(dockerfile, /ENV HYPERFRAMES_BROWSER_PATH=\/usr\/bin\/chromium/);
});

test("the adapter installs HyperFrames from its own manifest", () => {
  assert.match(dockerfile, /COPY package\.json package-lock\.json/);
  assert.match(dockerfile, /npm ci --omit=dev/);
  assert.match(dockerfile, /COPY vendor\/gsap\.min\.js/);
  assert.ok(pkg.dependencies.hyperframes, "the toolchain manifest has no hyperframes dependency");
});

test("the image fetches the framework's full skill set at the pinned release", () => {
  // The npm dist ships three skills; the rest come from the repository's skills/ tree.
  assert.ok(
    pkg.dependencies["@hyperframes/shader-transitions"],
    "the transition primitives are not a vendored dependency"
  );
  assert.match(dockerfile, /codeload\.github\.com\/heygen-com\/hyperframes/);
  assert.match(dockerfile, /--wildcards[^\n]*skills\/\*/);
  const arg = dockerfile.match(/ARG HYPERFRAMES_VERSION=([\d.]+)/);
  assert.ok(arg, "the Dockerfile does not pin the skill-fetch release");
  // One release for the engine, the skills and the primitives.
  assert.equal(arg[1], pkg.dependencies.hyperframes);
  assert.equal(arg[1], pkg.dependencies["@hyperframes/shader-transitions"]);
  for (const skill of ["hyperframes-core", "hyperframes-animation", "hyperframes-keyframes"]) {
    assert.ok(dockerfile.includes(skill), `the build does not assert the ${skill} skill`);
  }
  // A missing skill must fail the build, not ship a subset quietly.
  assert.match(dockerfile, /missing skill in the image/);
});
