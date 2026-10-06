// Shared scene helpers: escaping, the brand tokens, offline icons and the
// page-level CSS the shell and every layout build on.
//
// Everything here is deterministic string work. No network, no randomness, no
// Date - the same spec must produce the same composition.
//
// The palette and the typefaces come from `datasets/brand.json`, the only copy of
// the brand in this repository (agents/n8n/scripts/test_brand.py fails a surface
// that spells its own). A layout asks for a role - ink, accent, surface - and
// never a hex value.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));

let ICONS = {};
try {
  ICONS = JSON.parse(readFileSync(join(HERE, "icons.json"), "utf8")).icons || {};
} catch {
  ICONS = {};
}

export const BRAND = JSON.parse(readFileSync(join(HERE, "..", "..", "datasets", "brand.json"), "utf8"));
export const SCHEMES = Object.keys(BRAND.schemes);

export const esc = (s) =>
  String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
export const escAttr = (s) => esc(s).replace(/"/g, "&quot;");

// Resolve an icon name to inline SVG. An unknown name returns null so the caller
// degrades to text-only rather than failing the render.
export function icon(name) {
  const def = name && ICONS[name];
  if (!def || !Array.isArray(def.paths) || !def.paths.length) return null;
  const paths = def.paths
    .map((d) => `<path d="${escAttr(d)}" />`)
    .join("");
  const svg =
    `<svg class="glyph${def.motion === "spin" ? " spin" : ""}" viewBox="0 0 24 24" ` +
    `fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" ` +
    `stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
  return { svg, motion: def.motion || null };
}

// The accent ramp is the only place a caller's colour may land. A brand value is
// kept as the brand spells it; anything else is mapped to the nearest role, so an
// out-of-brand accent - a legacy frozen spec, an old caller - still renders and
// never introduces a palette the brand does not define (design D3).
const RAMP = ["accent", "accentStrong", "accentDeep"];

function rgb(value) {
  const h = value.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
}

function distance(a, b) {
  const [ar, ag, ab] = rgb(a);
  const [br, bg, bb] = rgb(b);
  return (ar - br) ** 2 + (ag - bg) ** 2 + (ab - bb) ** 2;
}

export function mapAccent(value, scheme) {
  const wanted = String(value || "").toLowerCase();
  for (const role of RAMP) if (scheme[role].toLowerCase() === wanted) return scheme[role];
  return RAMP.map((role) => scheme[role]).reduce((best, candidate) =>
    distance(candidate, wanted) < distance(best, wanted) ? candidate : best
  );
}

export function palette(spec, schemeName = BRAND.defaultScheme) {
  const scheme = BRAND.schemes[schemeName] || BRAND.schemes[BRAND.defaultScheme];
  const accent = mapAccent(spec.accent, scheme);
  return {
    scheme: BRAND.schemes[schemeName] ? schemeName : BRAND.defaultScheme,
    accent,
    accent2: spec.accent2 ? mapAccent(spec.accent2, scheme) : accent,
    background: spec.background || scheme.shell,
    ink: scheme.ink,
    muted: scheme.inkMuted,
    surface: scheme.surface,
    surfaceRaised: scheme.surfaceRaised,
    codeBg: scheme.codeBg,
    codeInk: scheme.codeInk,
  };
}

// The vendored faces. Both are OFL and ship in the image under vendor/fonts/,
// so the render never reaches a CDN; a composition that names a brand face the
// image does not carry falls through to the generic at the end of the stack.
const FACE = `
    @font-face { font-family: "Space Grotesk"; font-style: normal; font-weight: 300 700;
      font-display: swap; src: url("./vendor/fonts/SpaceGrotesk.ttf") format("truetype"); }
    @font-face { font-family: "JetBrains Mono"; font-style: normal; font-weight: 100 800;
      font-display: swap; src: url("./vendor/fonts/JetBrainsMono.ttf") format("truetype"); }
`;

// The page shell CSS. `--u` scales type from the 1080-wide baseline so a
// differently-sized canvas keeps its proportions. Alpha surfaces are derived from
// `--ink` with color-mix, so no surface carries a colour literal of its own.
export function shellCss(pal, opt) {
  const u = (opt.width / 1080).toFixed(4);
  return `
    ${FACE}
    :root {
      --accent: ${pal.accent};
      --accent-2: ${pal.accent2};
      --bg: ${pal.background};
      --ink: ${pal.ink};
      --muted: ${pal.muted};
      --surface: ${pal.surface};
      --surface-raised: ${pal.surfaceRaised};
      --code-bg: ${pal.codeBg};
      --code-ink: ${pal.codeInk};
      --line: color-mix(in srgb, var(--ink) ${(BRAND.shape.hairlineAlpha * 100).toFixed(1)}%, transparent);
      --card: color-mix(in srgb, var(--ink) 4.5%, transparent);
      --radius-card: ${BRAND.shape.radiusCard};
      --radius-panel: ${BRAND.shape.radiusPanel};
      --radius-pill: ${BRAND.shape.radiusPill};
      --u: ${u};
      --duration: ${(opt.durationMs / 1000).toFixed(3)}s;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body { width: ${opt.width}px; height: ${opt.height}px; overflow: hidden;
      background: var(--bg); color: var(--ink);
      font-family: "Space Grotesk", "Roboto", ui-sans-serif, system-ui, sans-serif;
      -webkit-font-smoothing: antialiased; }
    #root { position: relative; width: 100%; height: 100%; padding: calc(72px * var(--u)) calc(72px * var(--u));
      display: flex; flex-direction: column;
      background:
        linear-gradient(color-mix(in srgb, var(--ink) 2.8%, transparent) 1px, transparent 1px) 0 0 / 100% calc(60px * var(--u)),
        linear-gradient(90deg, color-mix(in srgb, var(--ink) 2.8%, transparent) 1px, transparent 1px) 0 0 / calc(60px * var(--u)) 100%,
        radial-gradient(120% 80% at 82% -10%, color-mix(in srgb, var(--accent) 16%, transparent), transparent 60%); }
    /* The header is ordinary flow content, deliberately NOT a .clip: HyperFrames
       takes .clip elements out of normal flow, which made the canvas believe it
       had the whole height and overlap the title. As flow, the header's real
       height (one title line or three) decides where the canvas starts. */
    .head { flex: none; }
    .kicker { font-size: calc(26px * var(--u)); letter-spacing: 0.42em; text-transform: uppercase;
      color: var(--accent); font-weight: 600; }
    h1 { margin-top: calc(20px * var(--u)); font-size: calc(94px * var(--u)); line-height: 0.98;
      letter-spacing: -0.035em; font-weight: 700; max-width: calc(820px * var(--u)); }
    .rule { margin-top: calc(32px * var(--u)); height: calc(6px * var(--u)); width: 100%;
      border-radius: 3px; transform-origin: left center; flex: none;
      background: linear-gradient(90deg, var(--accent), color-mix(in srgb, var(--ink) 5%, transparent)); }
    .canvas { flex: 1 1 auto; min-height: 0; margin-top: calc(40px * var(--u));
      margin-bottom: calc(56px * var(--u)); position: relative; }
    .glyph { width: calc(72px * var(--u)); height: calc(72px * var(--u)); flex: none; color: var(--accent); }
    .mono, code { font-family: "JetBrains Mono", "DejaVu Sans Mono", ui-monospace, monospace; }
    .spin { transform-origin: 50% 50%; }
    .foot { position: absolute; left: calc(72px * var(--u)); bottom: calc(48px * var(--u));
      font-size: calc(26px * var(--u)); color: var(--muted); }
    .foot b { color: var(--ink); }
  `;
}
