// The `gh` on PATH is a wrapper around `gh-real`: it borrows the git credential
// helper's token so commits and pull requests carry one identity.
//
// Two ways to break that silently, both asserted here. Asking `git credential
// fill` instead of the helper binary makes git re-read its config, and a
// `gh auth setup-git` line left in a persisted home points that config back at
// this wrapper, so the two recurse until the caller times out. And git calls
// this wrapper directly for such a line, which a wrapper that ignores
// `auth git-credential` answers with nothing, so the clone fails unauthenticated.

import { execFileSync } from "node:child_process";
import { chmodSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { test } from "node:test";

const here = dirname(fileURLToPath(import.meta.url));
const wrapper = join(here, "..", "gh-app");

function sandbox() {
  const dir = mkdtempSync(join(tmpdir(), "gh-app-"));
  const write = (name, body) => {
    writeFileSync(join(dir, name), body);
    chmodSync(join(dir, name), 0o755);
  };
  // Stands in for the minter-backed helper.
  write("git-credential-opencode", '#!/bin/sh\nprintf "username=x-access-token\\npassword=ghs_test\\n"\n');
  // Prints the token it was handed, which is what the wrapper must supply.
  write("gh-real", '#!/bin/sh\nprintf "GH_TOKEN=%s\\n" "${GH_TOKEN:-}"\n');
  // If the wrapper ever shells out to git, the test fails here instead of hanging.
  write("git", '#!/bin/sh\necho "the wrapper must not call git" >&2\nexit 9\n');
  return dir;
}

const run = (dir, args) =>
  execFileSync("sh", [wrapper, ...args], {
    env: { PATH: `${dir}:${process.env.PATH}`, HOME: dir },
    encoding: "utf8",
    timeout: 10_000,
  });

test("a plain gh call runs with the helper's token", () => {
  const out = run(sandbox(), ["api", "/installation/repositories"]);
  assert.equal(out.trim(), "GH_TOKEN=ghs_test");
});

test("git's own credential call is answered, not looped back", () => {
  const out = run(sandbox(), ["auth", "git-credential", "get"]);
  assert.match(out, /^password=ghs_test$/m);
  assert.doesNotMatch(out, /GH_TOKEN=/, "the credential call reached gh-real instead of being answered");
});
