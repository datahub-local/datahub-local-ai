// The n8n side of the brand gate, exercised offline against the committed
// export. The workflow assembles the prompt blocks and the markup tokens in Code
// nodes, so this runs those nodes' JavaScript with a stubbed `$` and asserts what
// they produce: a surface cannot quietly stop reading brand.json without failing
// here.
//
// It runs in the render job because that job has Node; the n8n job has only
// Python and no browser, and this needs neither.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const N8N = join(HERE, "..", "..");
const brand = JSON.parse(readFileSync(join(N8N, "datasets", "brand.json"), "utf8"));
const workflow = JSON.parse(readFileSync(join(N8N, "workflows", "visual_studio.workflow.json"), "utf8"));

const node = (name) => {
  const found = workflow.nodes.find((n) => n.name === name);
  assert.ok(found, `workflow has no node '${name}'`);
  return found;
};

const runCode = (jsCode, scope) =>
  new Function("$", "return (function () {" + jsCode + "})()")(scope);

const outputs = (result) => result.map((r) => r.json);

test("brand.json is read once and shaped for prompts and markup", () => {
  const scope = (name) => {
    assert.equal(name, "download_brand");
    return { first: () => ({ json: { output: JSON.stringify(brand) } }) };
  };
  const [out] = outputs(runCode(node("brand_tokens").parameters.jsCode, scope));

  assert.ok(out.BRAND.includes(brand.schemes.dark.shell), "the block names the shell colour");
  assert.ok(out.BRAND.includes(brand.schemes.dark.accent), "the block names the accent");
  assert.ok(out.BRAND.includes(brand.typography.text), "the block names the brand typeface");
  assert.equal(out.ART_DIRECTION, brand.photographic.artDirection);
  assert.equal(out.TEMPLATE.SHELL, brand.schemes.dark.shell);
  assert.equal(out.TEMPLATE.FONT_CODE, brand.typography.code);
  assert.deepEqual(out.TEMPLATE.RAMP, [
    brand.schemes.dark.accent,
    brand.schemes.dark.accentStrong,
    brand.schemes.dark.accentDeep,
  ]);
});

test("the spec and raster prompts are handed the brand block", () => {
  const specVars = node("download_spec_prompt").parameters.workflowInputs.value.template_vars;
  const rasterVars = node("download_raster_prompt").parameters.workflowInputs.value.template_vars;
  assert.match(specVars, /"BRAND": \$\('brand_tokens'\)/);
  assert.match(rasterVars, /"BRAND": \$\('brand_tokens'\)/);
  // The art direction reaches the raster prompt only for a photographic kind; a
  // diagrammatic raster uses the palette instead (design D4).
  assert.match(rasterVars, /BRAND_KIND === 'photographic' \? \$\('brand_tokens'\).*ART_DIRECTION : ''/);
});

test("the prompt templates declare the placeholders the workflow fills", () => {
  const spec = readFileSync(join(N8N, "prompts", "visual_spec.md"), "utf8");
  const raster = readFileSync(join(N8N, "prompts", "visual_raster.md"), "utf8");
  assert.ok(spec.includes("{{ BRAND }}"));
  assert.ok(raster.includes("{{ BRAND }}"));
  assert.ok(raster.includes("{{ ART_DIRECTION }}"));
});

test("the agent brief carries the brand block", () => {
  const js = node("build_author_brief").parameters.jsCode;
  assert.match(js, /\$\('brand_tokens'\)\.first\(\)\.json\.BRAND/);
});

test("the registry carries a brandKind and rejects an unknown one", () => {
  const types = JSON.parse(readFileSync(join(N8N, "datasets", "visual_types.json"), "utf8")).types;
  assert.equal(types.find((t) => t.id === "hero_static").brandKind, "photographic");
  assert.ok(types.filter((t) => t.id !== "hero_static").every((t) => t.brandKind === "diagrammatic"));

  const registry = { types, budget: {}, max_types_per_request: 3, default_types: [types[0].id] };
  const scope = (name) => {
    if (name === "download_registry") return { first: () => ({ json: { output: JSON.stringify(registry) } }) };
    if (name === "normalize_input") return { first: () => ({ json: { ASSET_TYPES: "hero_static", FEEDBACK: "" } }) };
    throw new Error("unexpected node " + name);
  };
  const js = node("parse_registry").parameters.jsCode;
  const [hero] = outputs(runCode(js, scope));
  assert.equal(hero.BRAND_KIND, "photographic");

  const bad = { ...registry, types: [{ ...types[0], brandKind: "neon" }] };
  const badScope = (name) =>
    name === "download_registry"
      ? { first: () => ({ json: { output: JSON.stringify(bad) } }) }
      : { first: () => ({ json: { ASSET_TYPES: "hero_static", FEEDBACK: "" } }) };
  assert.throws(() => runCode(js, badScope), /unknown brandKind/);
});

test("the markup builder substitutes the brand tokens, not literals", () => {
  const js = node("merge_assets").parameters.jsCode;
  for (const token of ["%%BRAND_SHELL%%", "%%BRAND_INK%%", "%%BRAND_INK_MUTED%%", "%%BRAND_HAIRLINE%%", "%%FONT_TEXT%%", "%%FONT_CODE%%"]) {
    assert.ok(js.includes(token), `merge_assets does not substitute ${token}`);
  }
  // The caller's accent is mapped, not passed through.
  assert.ok(js.includes("mapAccent(spec.accent)"));
});

test("both copies of the graph are identical", () => {
  assert.deepEqual(workflow.nodes, workflow.activeVersion.nodes);
  assert.deepEqual(workflow.connections, workflow.activeVersion.connections);
});

test("the brand fetch sits on the single-item path before anything reads it", () => {
  const next = (name) => (workflow.connections[name].main[0] || []).map((c) => c.node);
  assert.deepEqual(next("normalize_input"), ["download_brand"]);
  assert.deepEqual(next("download_brand"), ["brand_tokens"]);
  assert.deepEqual(next("brand_tokens"), ["download_registry"]);
});
