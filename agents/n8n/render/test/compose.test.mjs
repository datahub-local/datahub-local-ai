import { test } from "node:test";
import assert from "node:assert/strict";

import { compose } from "../src/compose.mjs";
import { parseSpec, SpecError } from "../src/spec.mjs";

const base = {
  title: "Homelab data flow",
  blocks: [
    { label: "Ingest", value: "bronze", icon: "download" },
    { label: "Build", value: "silver + gold", icon: "database" },
    { label: "Serve", value: "Trino", icon: "server" },
  ],
  accent: "#22d3ee",
  motion: { kind: "rise", durationMs: 3000 },
  alt: "Ingest, build, serve",
};

const composeSpec = (over = {}) => compose({ ...base, ...over }).html;

test("absent layout renders the stats list", () => {
  const html = composeSpec();
  assert.match(html, /class="stats"/);
  assert.match(html, />Ingest</);
  assert.match(html, /data-composition-id="main"/);
});

test("every layout renders its own structure", () => {
  assert.match(composeSpec({ layout: "flow" }), /class="flow"/);
  assert.match(composeSpec({ layout: "timeline" }), /class="timeline"/);
  assert.match(composeSpec({ layout: "comparison" }), /class="comparison"/);
  assert.match(composeSpec({ layout: "bars" }), /class="bars"/);
});

test("the flow layout draws connectors with an arrowhead", () => {
  const html = composeSpec({ layout: "flow" });
  assert.match(html, /class="f-trace"/);
  assert.match(html, /class="f-head"/);
  assert.match(html, /stroke-dashoffset: 100/);
});

test("the bars layout carries proportional fills", () => {
  const html = compose({ ...base, layout: "bars" }).html;
  assert.match(html, /data-pct="/);
});

test("an unknown icon degrades instead of failing", () => {
  const html = composeSpec({ blocks: [{ label: "A", value: "1", icon: "no-such-icon" }] });
  assert.doesNotMatch(html, /no-such-icon/);
  assert.match(html, />A</);
});

test("a spinning icon is given the spin class", () => {
  const html = composeSpec({ blocks: [{ label: "A", value: "1", icon: "gear" }] });
  assert.match(html, /class="glyph spin"/);
});

test("no template token is left in the composition", () => {
  const html = composeSpec({ layout: "flow" });
  assert.doesNotMatch(html, /%%[A-Z_]+%%/);
  assert.doesNotMatch(html, /\$\{/);
});

test("the composition duration comes from the spec", () => {
  const html = composeSpec({ motion: { kind: "rise", durationMs: 4000 } });
  assert.match(html, /data-duration="4\.000"/);
  assert.doesNotMatch(html, /NaN/);
});

test("an unknown layout fails loudly", () => {
  assert.throws(() => parseSpec({ ...base, layout: "pie" }), /unknown layout: pie/);
});

test("an invalid colour fails loudly", () => {
  assert.throws(() => parseSpec({ ...base, accent: "teal" }), /accent must be/);
  assert.throws(() => parseSpec({ ...base, accent2: "#12" }), /accent2 must be/);
});

test("markup is not accepted as a spec", () => {
  assert.throws(() => parseSpec("<div>x</div>"), SpecError);
});

test("the service refuses caller markup before composing", () => {
  // The guard lives in the server; assert its key list is honoured by compose's
  // input contract: an html key is not a valid spec field, so a spec carrying it
  // is rejected by validation rather than rendered.
  assert.throws(() => parseSpec({ ...base, html: "<b>x</b>" }), SpecError);
});
