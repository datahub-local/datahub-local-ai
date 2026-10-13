// The composer's guide is sandbox facts only.
//
// It used to restate the HyperFrames composition contract, mandate a nine-point
// pre-render review with hard-coded pacing numbers, require a final hold and a page
// indicator. That harness competed with the framework's own skills — which the image
// now ships in full — and its pacing rules mandated the frozen motion the framework
// names as a cheap-motion tell. The guide now names only what the brief cannot state:
// the working directory, the engine and its skills, the vendored GSAP, no network, and
// how to run the render. This test keeps the method from coming back.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { test } from "node:test";

const here = dirname(fileURLToPath(import.meta.url));
const guide = readFileSync(join(here, "..", "prompts", "authoring.md"), "utf8");

test("the guide states the sandbox facts", () => {
  assert.match(guide, /working directory/i);
  assert.match(guide, /`hyperframes` is on `PATH`|hyperframes.*on .PATH/);
  assert.match(guide, /\/opt\/hyperframes\/skills\//);
  assert.match(guide, /gsap\.min\.js/);
  assert.match(guide, /no network/i);
  assert.match(guide, /foreground/);
  assert.match(guide, /cannot see images|You cannot see images/);
});

test("the guide keeps the render command, its flags and the foreground rule", () => {
  assert.match(guide, /hyperframes render/);
  assert.match(guide, /--low-memory-mode/);
  assert.match(guide, /render_cancelled_parent_exited|aborts? the moment/);
});

test("a turn that never renders is a stated failure", () => {
  assert.match(guide, /must end in a render/);
});

test("the guide requires check and names the sidecar it reads", () => {
  // check verifies motion only when the composition ships a *.motion.json sidecar, so
  // the guide has to ask for one and to require check rather than call it optional.
  assert.match(guide, /motion\.json/);
  assert.match(guide, /hyperframes check/);
  assert.match(guide, /declaration, not a probe/);
  // check launches its own Chrome; the memory caution survives.
  assert.match(guide, /--samples/);
  assert.ok(!/is optional/.test(guide), "check is optional again");
});

test("the vendored GSAP is served, never referenced by absolute path or a CDN", () => {
  assert.match(guide, /gsap\.min\.js/);
  assert.match(guide, /CDN/);
  // The absolute /opt path is what 404'd at render time; it must not come back.
  assert.ok(
    !/\/opt\/hyperframes\/vendor\/gsap\.min\.js/.test(guide),
    "the guide references the vendored GSAP by absolute path again"
  );
});

test("no composition-contract restatement survives", () => {
  for (const forbidden of [
    "data-composition-id",
    "data-start",
    "data-duration",
    "__timelines",
    "paused: true",
  ]) {
    assert.ok(!guide.includes(forbidden), `the guide restates the contract: ${forbidden}`);
  }
});

test("no review section and no pacing numbers survive", () => {
  assert.ok(!/##\s*Review before you render/.test(guide), "the review section is back");
  for (const number of ["2.5-3.5", "0.6-0.9", "1.5 second"]) {
    assert.ok(!guide.includes(number), `the guide carries the pacing number ${number}`);
  }
  assert.ok(!/End on a hold/.test(guide), "the frozen final hold is back");
  assert.ok(!/page indicator/i.test(guide), "the page-indicator rule is back");
});

test("the SVG authoring mode is gone (the brief carries it)", () => {
  assert.ok(!/out\.svg/.test(guide), "the SVG instructions are back in the guide");
});
