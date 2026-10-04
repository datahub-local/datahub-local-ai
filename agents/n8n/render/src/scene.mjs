// Shared scene helpers: escaping, the palette, offline icons and the page-level
// CSS the shell and every layout build on.
//
// Everything here is deterministic string work. No network, no randomness, no
// Date - the same spec must produce the same composition.

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

export function palette(spec) {
  return {
    accent: spec.accent,
    accent2: spec.accent2 || spec.accent,
    background: spec.background || "#0a0d12",
    ink: "#f5f7fa",
    muted: "rgba(245,247,250,0.62)",
    line: "rgba(245,247,250,0.12)",
    card: "rgba(255,255,255,0.045)",
  };
}

// The page shell CSS. `--u` scales type from the 1080-wide baseline so a
// differently-sized canvas keeps its proportions.
export function shellCss(pal, opt) {
  const u = (opt.width / 1080).toFixed(4);
  return `
    :root {
      --accent: ${pal.accent};
      --accent-2: ${pal.accent2};
      --bg: ${pal.background};
      --ink: ${pal.ink};
      --muted: ${pal.muted};
      --line: ${pal.line};
      --card: ${pal.card};
      --u: ${u};
      --duration: ${(opt.durationMs / 1000).toFixed(3)}s;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body { width: ${opt.width}px; height: ${opt.height}px; overflow: hidden;
      background: var(--bg); color: var(--ink);
      font-family: Inter, "DejaVu Sans", ui-sans-serif, system-ui, sans-serif;
      -webkit-font-smoothing: antialiased; }
    #root { position: relative; width: 100%; height: 100%; padding: calc(72px * var(--u)) calc(72px * var(--u));
      background:
        linear-gradient(rgba(255,255,255,0.028) 1px, transparent 1px) 0 0 / 100% calc(60px * var(--u)),
        linear-gradient(90deg, rgba(255,255,255,0.028) 1px, transparent 1px) 0 0 / calc(60px * var(--u)) 100%,
        radial-gradient(120% 80% at 82% -10%, color-mix(in srgb, var(--accent) 16%, transparent), transparent 60%); }
    .kicker { font-size: calc(26px * var(--u)); letter-spacing: 0.42em; text-transform: uppercase;
      color: var(--accent); font-weight: 600; }
    h1 { margin-top: calc(20px * var(--u)); font-size: calc(94px * var(--u)); line-height: 0.98;
      letter-spacing: -0.035em; font-weight: 700; max-width: calc(820px * var(--u)); }
    .rule { margin-top: calc(32px * var(--u)); height: calc(6px * var(--u)); width: 100%;
      border-radius: 3px; transform-origin: left center;
      background: linear-gradient(90deg, var(--accent), rgba(245,247,250,0.05)); }
    .canvas { position: absolute; left: calc(72px * var(--u)); right: calc(72px * var(--u));
      top: calc(336px * var(--u)); bottom: calc(104px * var(--u)); }
    .glyph { width: calc(72px * var(--u)); height: calc(72px * var(--u)); flex: none; color: var(--accent); }
    .spin { transform-origin: 50% 50%; }
    .foot { position: absolute; left: calc(72px * var(--u)); bottom: calc(58px * var(--u));
      font-size: calc(26px * var(--u)); color: var(--muted); }
    .foot b { color: var(--ink); }
  `;
}
