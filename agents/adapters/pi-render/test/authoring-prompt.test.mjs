// The composer's guide is sandbox facts only.
//
// It used to restate the HyperFrames composition contract, mandate a nine-point
// pre-render review with hard-coded pacing numbers, require a final hold and a page
// indicator. That harness competed with the framework's own guidance and its pacing
// rules mandated the frozen motion the framework names as a cheap-motion tell. The guide
// now names only what the brief cannot state: the working directory, the engine and the
// docs topics that carry its contract, the vendored GSAP, no network, and how to run the
// render. This test keeps the method from coming back.

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
  // The contract is the engine's own documentation, read from the binary at run time.
  assert.match(guide, /hyperframes docs compositions/);
  assert.match(guide, /hyperframes docs data-attributes/);
  assert.ok(
    !/\/opt\/hyperframes\/skills\//.test(guide),
    "the guide points at a skill tree again; the engine's docs carry the contract"
  );
  // The CLI is called as `hyperframes`; npx appears only as the prohibition, and a step that
  // told the composer to run through it could reach for a registry at render time.
  assert.match(guide, /never `npx hyperframes`/);
  assert.ok(
    !/^\s*\d+\.\s+[^\n]*npx /m.test(guide),
    "a numbered step invokes the CLI through npx"
  );
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
  // ...and the SVG exception is stated, because lint/check reject a standalone SVG and the
  // guide used to send every format through them (a real turn then wrote HTML into out.svg).
  assert.match(guide, /hyperframes lint`\s*\n?\s*and `check` validate HTML compositions|validate HTML compositions/);
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

test("the guide carries the SVG gate exception, not an SVG authoring mode", () => {
  assert.match(guide, /out\.svg/);
  // The engine's gates do not apply to a standalone SVG; how to author one is the brief's
  // job, so no SVG method may creep in here.
  for (const method of ["viewBox", "@keyframes", "SMIL", "<svg"]) {
    assert.ok(!guide.includes(method), `the guide carries an SVG method: ${method}`);
  }
});
