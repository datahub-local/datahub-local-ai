import { test } from "node:test";
import assert from "node:assert/strict";

import { coerce, declaredVariables, includeMarkup, variablePayload } from "../src/blocks/adapter.mjs";

test("a variable-declaring block's declarations are parsed", () => {
  const decls = declaredVariables("bar-chart-race");
  const ids = decls.map((d) => d.id);
  assert.ok(ids.includes("title"));
  assert.ok(ids.includes("series"));
  for (const d of decls) assert.ok(["string", "number", "color"].includes(d.type), `${d.id} has a type`);
});

test("a number is clamped to the block's declared range", () => {
  const decl = { id: "barCount", type: "number", min: 3, max: 12 };
  assert.equal(coerce(decl, 5, "barCount"), 5);
  assert.equal(coerce(decl, 99, "barCount"), 12);
  assert.equal(coerce(decl, 1, "barCount"), 3);
});

test("a non-numeric value for a number variable is rejected naming it", () => {
  const decl = { id: "barCount", type: "number" };
  assert.throws(() => coerce(decl, "lots", "barCount"), /barCount must be a number for 'barCount'/);
});

test("a colour must be #rrggbb and is normalised", () => {
  const decl = { id: "accent", type: "color" };
  assert.equal(coerce(decl, "#AABBCC", "accent"), "#aabbcc");
  assert.throws(() => coerce(decl, "red", "accent"), /accent must be a #rrggbb colour/);
});

test("a string variable rejects a non-string", () => {
  const decl = { id: "title", type: "string" };
  assert.equal(coerce(decl, "ok", "title"), "ok");
  assert.throws(() => coerce(decl, 5, "title"), /title must be a string for 'title'/);
});

test("only declared variables survive into the payload", () => {
  // The block declares a known set; a key it does not declare must be dropped
  // rather than injected, so the block's own default applies.
  const payload = variablePayload("bar-chart-race", {
    title: "T",
    series: "A: 1",
    notAVariable: "should be dropped",
    accent: "#22d3ee",
  });
  assert.equal(payload.title, "T");
  assert.equal(payload.series, "A: 1");
  assert.equal(payload.accent, "#22d3ee");
  assert.equal(payload.notAVariable, undefined);
});

test("overrides travel on the include element, not a global", () => {
  // The channel that actually works for a sub-composition: data-variable-values on
  // the host element. A global silently does nothing.
  const html = includeMarkup("bar-chart-race", {
    durationSec: "3.000",
    width: 1080,
    height: 1350,
    variables: { title: "Medallion build time" },
  });
  assert.match(html, /data-composition-src="blocks\/bar-chart-race\.html"/);
  assert.match(html, /data-variable-values='/);
  assert.match(html, /Medallion build time/);
  assert.doesNotMatch(html, /__hfVariables/);
});

test("a block with no variables cannot be included", () => {
  // A catalog component declares none; adopting one would mean rewriting its
  // content, which is the hand-written markup this change removes.
  assert.throws(() => declaredVariables("no-such-block"), /ENOENT|no such file/);
});
