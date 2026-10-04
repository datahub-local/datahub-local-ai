// Content-spec validation for the render service.
//
// The spec is the same shape the Visual Studio workflow already authors and
// validates (title, blocks, accent, motion, alt) plus the optional diagram
// vocabulary this service renders: layout, per-item icon, a second accent and a
// background. Keeping the service's view of the spec identical to the studio's
// is what lets one spec be rendered by either renderer without a translation
// layer.
//
// Validation is deliberately strict on the structural fields and lenient on
// decoration: an unknown layout fails (the whole composition depends on it), an
// unknown icon is dropped later (it is only a glyph).

export const LAYOUTS = ["stats", "flow", "timeline", "comparison", "bars", "bar-chart-race"];
export const MOTIONS = ["rise", "fade", "sweep", "pulse", "draw", "travel", "spin"];

export const CAPS = {
  durationMs: { min: 1000, max: 20000 },
  fps: { min: 12, max: 60 },
  // The long edge, in pixels. A wider canvas is rejected rather than downsampled,
  // so the caller learns its request was outside the service's contract.
  edge: 1920,
  items: { min: 1, max: 8 },
  text: { title: 120, label: 40, value: 40, alt: 240 },
};

const HEX = /^#[0-9a-fA-F]{6}$/;
const isStr = (v) => typeof v === "string" && v.trim() !== "";

class SpecError extends Error {}

const fail = (msg) => {
  throw new SpecError(msg);
};

function hex(value, field) {
  if (value === undefined || value === null || value === "") return undefined;
  if (typeof value !== "string" || !HEX.test(value)) fail(`${field} must be a #rrggbb colour`);
  return value.toLowerCase();
}

function bounded(value, field, min, max) {
  if (value === undefined || value === null || value === "") return undefined;
  const n = Number(value);
  if (!Number.isFinite(n)) fail(`${field} must be a number`);
  if (n < min || n > max) fail(`${field} must be between ${min} and ${max}`);
  return n;
}

// Returns a normalised spec, or throws SpecError naming the offending field.
export function parseSpec(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) fail("spec must be an object");

  const allowed = new Set(["title", "blocks", "accent", "accent2", "background", "layout", "motion", "alt"]);
  const unknown = Object.keys(input).filter((k) => !allowed.has(k));
  if (unknown.length) fail(`unsupported field: ${unknown.join(", ")} (send a content spec, not markup)`);

  if (!isStr(input.title)) fail("missing field: title");
  if (String(input.title).length > CAPS.text.title) fail("title is too long");

  if (!Array.isArray(input.blocks)) fail("missing field: blocks");
  const { min, max } = CAPS.items;
  if (input.blocks.length < min || input.blocks.length > max)
    fail(`blocks must have between ${min} and ${max} entries`);

  const blocks = input.blocks.map((b, i) => {
    if (!b || typeof b !== "object") fail(`blocks[${i}] must be an object`);
    if (!isStr(b.label)) fail(`missing field: blocks[${i}].label`);
    if (!isStr(String(b.value ?? ""))) fail(`missing field: blocks[${i}].value`);
    if (String(b.label).length > CAPS.text.label) fail(`blocks[${i}].label is too long`);
    if (String(b.value).length > CAPS.text.value) fail(`blocks[${i}].value is too long`);
    if (b.icon !== undefined && !isStr(b.icon)) fail(`blocks[${i}].icon must be a string`);
    return { label: String(b.label), value: String(b.value), icon: isStr(b.icon) ? String(b.icon) : undefined };
  });

  const accent = hex(input.accent, "accent");
  if (!accent) fail("missing field: accent");

  const layout = input.layout === undefined || input.layout === "" ? "stats" : String(input.layout);
  if (!LAYOUTS.includes(layout)) fail(`unknown layout: ${layout}`);

  const motionIn = input.motion || {};
  if (typeof motionIn !== "object") fail("missing field: motion");
  const kind = motionIn.kind === undefined ? "rise" : String(motionIn.kind);
  if (!MOTIONS.includes(kind)) fail(`unknown motion.kind: ${kind}`);
  const durationMs = bounded(motionIn.durationMs, "motion.durationMs", CAPS.durationMs.min, CAPS.durationMs.max) ?? 3000;

  const alt = isStr(input.alt) ? String(input.alt) : "";

  return {
    title: String(input.title),
    blocks,
    accent,
    accent2: hex(input.accent2, "accent2"),
    background: hex(input.background, "background"),
    layout,
    motion: { kind, durationMs },
    alt,
  };
}

// Render options are separate from the spec because they describe the file, not
// the idea. Dimensions are capped on the long edge.
export function parseOptions(input = {}) {
  const width = bounded(input.width, "width", 64, CAPS.edge) ?? 1080;
  const height = bounded(input.height, "height", 64, CAPS.edge) ?? 1350;
  if (width > CAPS.edge || height > CAPS.edge) fail(`resolution exceeds the ${CAPS.edge}px cap`);
  const fps = bounded(input.fps, "fps", CAPS.fps.min, CAPS.fps.max) ?? 30;
  return { width: Math.round(width), height: Math.round(height), fps: Math.round(fps) };
}

export { SpecError };
