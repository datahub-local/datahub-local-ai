// The composer cannot see images, and the engine's checks do not catch a composition
// that fills only part of its frame or changes too fast to read. Two live studio runs
// on 2026-10-08 passed `hyperframes check` yet shipped a top-40%-only layout and a
// clip that overran its requested duration; both were caught only by a human. The
// authoring guide therefore carries a mandatory review before rendering. This test
// keeps that review, and the numbers it commits to, from being dropped.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { test } from "node:test";

const here = dirname(fileURLToPath(import.meta.url));
const guide = readFileSync(join(here, "..", "prompts", "authoring.md"), "utf8");

test("the guide requires a review before rendering", () => {
  assert.match(guide, /## Review before you render/);
  for (const check of ["**Content.**", "**Proportion.**", "**Legibility.**", "**Pacing.**"]) {
    assert.ok(guide.includes(check), `review is missing the ${check} check`);
  }
});

test("the review names the legibility minimums", () => {
  for (const size of ["34px", "18px", "14px"]) {
    assert.ok(guide.includes(size), `review is missing the ${size} minimum`);
  }
});

test("the review bounds the total to the brief's duration", () => {
  assert.match(guide, /must not exceed the\s+duration the brief\s+asks for/);
});

test("the review is reported", () => {
  assert.match(guide, /State the review, with its\s+numbers/);
  assert.match(guide, /then the review you performed/);
});
