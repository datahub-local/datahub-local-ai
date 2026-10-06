// The brand gate on the render service: the composition is built from
// datasets/brand.json, a caller's accent lands inside the brand's ramp, and the
// scheme an asset declares is the scheme it uses.
//
// These fail if a surface swaps a role for a literal: the assertions name the
// exact hex the brand document carries, so `#0a0d12` or an unchanged `#22d3ee`
// showing up in the markup is a failure rather than a rename.

import { test } from "node:test";
import assert from "node:assert/strict";

import { compose } from "../src/compose.mjs";
import { BRAND, SCHEMES, mapAccent } from "../src/scene.mjs";

const base = {
  title: "Homelab data flow",
  blocks: [
    { label: "Ingest", value: "bronze" },
    { label: "Build", value: "silver" },
  ],
  accent: BRAND.schemes.dark.accent,
  motion: { kind: "rise", durationMs: 3000 },
  alt: "Ingest and build",
};

const html = (over = {}, options = {}) => compose({ ...base, ...over }, options).html;

test("the brand document carries both schemes and the two typefaces", () => {
  assert.deepEqual(SCHEMES.sort(), ["dark", "light"]);
  assert.equal(BRAND.defaultScheme, "dark");
  assert.equal(BRAND.typography.text, "Space Grotesk");
  assert.equal(BRAND.typography.code, "JetBrains Mono");
});

test("a diagram uses the dark scheme's surface, ink and accent", () => {
  const out = html();
  const dark = BRAND.schemes.dark;
  assert.ok(out.includes(dark.shell), "shell background is the brand dark");
  assert.ok(out.includes(dark.ink), "ink is the brand cream");
  assert.ok(out.includes(dark.accent), "accent is the brand moss");
  assert.ok(!out.includes("#0a0d12") && !out.includes("#f5f7fa"), "no pre-brand literal survives");
});

test("a light-scheme asset uses the light scheme throughout", () => {
  const out = html({}, { scheme: "light" });
  const light = BRAND.schemes.light;
  assert.ok(out.includes(`--bg: ${light.shell}`), "shell background is the brand cream");
  assert.ok(out.includes(`--ink: ${light.ink}`), "ink is the brand dark");
  assert.ok(out.includes(`--accent: ${light.accent}`), "accent is the brand moss");
});

test("an unknown scheme fails loudly", () => {
  assert.throws(() => html({}, { scheme: "neon" }), /unknown scheme/);
});

test("a brand accent is kept exactly as the brand spells it", () => {
  for (const role of ["accent", "accentStrong", "accentDeep"]) {
    const value = BRAND.schemes.dark[role];
    assert.equal(mapAccent(value, BRAND.schemes.dark), value);
    assert.ok(html({ accent: value }).includes(value));
  }
});

test("an out-of-brand accent is mapped onto the ramp, never rendered as given", () => {
  const out = html({ accent: "#22d3ee" });
  assert.ok(!out.includes("#22d3ee"), "the caller's colour must not reach the composition");
  assert.ok(mapAccent("#22d3ee", BRAND.schemes.dark).startsWith("#"));
  const ramp = ["accent", "accentStrong", "accentDeep"].map((r) => BRAND.schemes.dark[r]);
  assert.ok(ramp.some((hex) => out.includes(hex)), "an in-ramp accent is used instead");
});

test("the second accent maps into the ramp too", () => {
  const out = html({ accent2: "#ff00ff" });
  assert.ok(!out.includes("#ff00ff"));
});
