// The composer cannot see images, and the engine's checks do not catch a composition
// that fills only part of its frame or changes too fast to read. Live studio runs on
// 2026-10-08 passed `hyperframes check` yet shipped a top-40%-only layout and a clip
// that overran its requested duration; both were caught only by a human. A later run
// (12645) satisfied the review's proportion check by measuring a `flex: 1` wrapper
// while the visible content stayed in the top third, so the guide names the wrapper as
// an invalid measure. This test keeps the review, its numbers and its conventions from
// being dropped.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { test } from "node:test";

const here = dirname(fileURLToPath(import.meta.url));
const guide = readFileSync(join(here, "..", "prompts", "authoring.md"), "utf8");

test("the guide requires a review before rendering", () => {
  assert.match(guide, /## Review before you render/);
  for (const check of [
    "**Content.**",
    "**Proportion.**",
    "**Legibility.**",
    "**Pacing.**",
    "**Pages.**",
  ]) {
    assert.ok(guide.includes(check), `review is missing the ${check} check`);
  }
});

test("the proportion check measures the visible content, not a wrapper", () => {
  assert.match(guide, /visible content/);
  assert.match(guide, /stretches to fill the height/);
  assert.match(guide, /not the measure/);
});

test("multi-scene compositions carry a page indicator", () => {
  assert.match(guide, /more than one scene/);
  assert.match(guide, /bottom-right/);
  assert.match(guide, /2 \/ 3/);
});

test("the review names the legibility minimums", () => {
  for (const size of ["34px", "18px", "14px"]) {
    assert.ok(guide.includes(size), `review is missing the ${size} minimum`);
  }
});

test("the review bounds the total to the brief's duration", () => {
  assert.match(guide, /must not exceed the\s+duration the brief\s+asks for/);
});

test("the review requires a final hold so a reader can finish", () => {
  assert.match(guide, /End on a hold/);
  assert.match(guide, /last frame must stay still/);
  assert.match(guide, /State the total and the hold/);
});

test("the guide describes the SVG authoring mode", () => {
  assert.match(guide, /If the brief asks for SVG/);
  assert.match(guide, /out\.svg/);
  assert.match(guide, /no script, no network/);
});

test("the review is reported", () => {
  assert.match(guide, /State the review, with its\s+numbers/);
  assert.match(guide, /then the review you performed/);
});
