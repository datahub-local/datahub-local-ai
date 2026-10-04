// The catalog-block adapter.
//
// Turns a content spec into a composition built from a vendored HyperFrames
// catalog block. It replaces the per-layout string builders in src/layouts/: the
// markup comes from a block that upstream designed, and this module's only job is
// to bind our spec to it.
//
// Only **variable-declaring** blocks are adopted (design D3). Such a block declares
// its variables in `data-composition-variables` and reads them back through
// `window.__hyperframes.getVariables()`; we include it by `data-composition-src`
// and pass the mapped values on the include element, never rewriting its markup.
// A catalog *component* (markup + CSS with hardcoded content and no declared
// variables) is deliberately not supported: binding a spec to it would mean
// substituting its content, which is the hand-written markup this change removes.
//
// The trust boundary is unchanged: a block is ours (vendored in the image), a
// caller names a layout from a closed set, never a file, and never supplies markup.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { escAttr } from "../scene.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const BLOCKS_DIR = join(HERE, "..", "..", "vendor", "blocks");

const read = (name) => readFileSync(join(BLOCKS_DIR, `${name}.html`), "utf8");

// Parse a block's declared variables. Throws for a block that declares none, so a
// component can never be reached by accident.
export function declaredVariables(name) {
  const body = read(name);
  const m = body.match(/data-composition-variables='([\s\S]*?)'/);
  if (!m) throw new Error(`block '${name}' declares no variables; only variable-declaring blocks are adopted`);
  try {
    const decls = JSON.parse(m[1]);
    if (!Array.isArray(decls)) throw new Error("not an array");
    return decls;
  } catch (e) {
    throw new Error(`block '${name}' has an unreadable data-composition-variables declaration: ${e.message}`);
  }
}

// Coerce and bounds-check one value against its declaration. A value of the wrong
// type is rejected naming the field rather than passed through, because a silently
// wrong type renders a wrong figure.
export function coerce(decl, value, field) {
  if (value === undefined || value === null) return undefined;
  switch (decl.type) {
    case "number": {
      const n = Number(value);
      if (!Number.isFinite(n)) throw new Error(`${field} must be a number for '${decl.id}'`);
      const lo = decl.min ?? -Infinity;
      const hi = decl.max ?? Infinity;
      return Math.min(hi, Math.max(lo, n));
    }
    case "color": {
      const s = String(value);
      if (!/^#[0-9a-fA-F]{6}$/.test(s)) throw new Error(`${field} must be a #rrggbb colour for '${decl.id}'`);
      return s.toLowerCase();
    }
    default: {
      if (typeof value !== "string") throw new Error(`${field} must be a string for '${decl.id}'`);
      return value;
    }
  }
}

// Build the variable payload for a block. `wanted` is the per-block mapping's
// output; anything the block does not declare is dropped here, and anything the
// mapping omits keeps the block's own default.
export function variablePayload(name, wanted) {
  const payload = {};
  for (const d of declaredVariables(name)) {
    const v = coerce(d, wanted[d.id], d.id);
    if (v !== undefined) payload[d.id] = v;
  }
  return payload;
}

// The include markup for a sub-composition block: referenced, never pasted.
//
// Per-instance variable overrides go in `data-variable-values` on this element,
// not on a global. HyperFrames layers them over the sub-composition's declared
// defaults for this one mount (docs: `compositions`), and the runtime's
// getVariables() returns the merged result. Setting window.__hfVariables instead
// looks right and does nothing for a sub-composition - found by rendering the
// block and watching its sample data survive; only the attribute form changed it.
export function includeMarkup(name, { durationSec, width, height, variables }) {
  const values =
    variables && Object.keys(variables).length
      ? ` data-variable-values='${escAttr(JSON.stringify(variables))}'`
      : "";
  return (
    `<div data-composition-id="${escAttr(name)}" data-composition-src="blocks/${escAttr(name)}.html"` +
    ` data-start="0" data-duration="${durationSec}" data-width="${width}" data-height="${height}"${values}></div>`
  );
}

// Per-block spec -> declared-variable mappings (the design's per-block table).
// Each maps only variables the block declares; the adapter drops the rest.
const VARIABLE_MAPPINGS = {
  // A race wants a time series. Our spec is a flat list of labelled figures, so
  // this reads them as one period: a single-period race, the honest rendering of a
  // spec that carries no history.
  "bar-chart-race": (spec) => ({
    title: spec.title,
    subtitle: spec.alt || "",
    periods: "now",
    series: spec.blocks.map((b) => `${b.label}: ${numeric(b.value)}`).join("\n"),
    accent: spec.accent,
    valueSuffix: suffix(spec.blocks.map((b) => b.value)),
  }),
};

// A value like "34s" is a figure plus a unit; a race takes the figure and the unit
// separately. A value with no number is passed as 0 rather than inventing one.
function numeric(value) {
  const m = String(value).replace(/[,\s]/g, "").match(/-?\d+(\.\d+)?/);
  return m ? Number(m[0]) : 0;
}

// The unit shared by every block value, if there is one, so "12s" reads as 12 with
// an "s" suffix rather than four different units in one chart.
function suffix(values) {
  const units = values.map((v) => String(v).replace(/[\d,.\s-]/g, "")).filter(Boolean);
  return units.length === values.length && new Set(units).size === 1 ? units[0] : "";
}

// Compose a block into the shell. Returns the same {css, body, anim} contract the
// layout builders returned, so compose.mjs needs no special case.
export function buildBlock(name, ctx) {
  const { spec, opt } = ctx;
  const durationSec = (opt.durationMs / 1000).toFixed(3);
  const mapping = VARIABLE_MAPPINGS[name];
  if (!mapping) throw new Error(`no spec mapping for block '${name}'`);

  const payload = variablePayload(name, mapping(spec, ctx));
  return {
    css: "",
    body: includeMarkup(name, { durationSec, width: opt.width, height: opt.height, variables: payload }),
    anim: "",
    variables: {},
  };
}

export { BLOCKS_DIR };
