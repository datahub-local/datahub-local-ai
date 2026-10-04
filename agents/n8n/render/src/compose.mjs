// Deterministic spec -> HyperFrames composition.
//
// The composition contract is HyperFrames': a root with data-composition-id,
// data-start, data-duration, data-width and data-height; timeline elements
// carrying data-start/data-duration/data-track-index; and a GSAP timeline
// registered on window.__timelines["main"], which the engine seeks per frame.
//
// The animation runtime is a vendored local file, never a CDN: the service runs
// with no network, and a remote script would both fail in-cluster and make a
// render depend on a third party's uptime.

import { parseSpec, parseOptions } from "./spec.mjs";
import { esc, escAttr, icon, palette, shellCss } from "./scene.mjs";
import { build as buildLayout } from "./layouts/index.mjs";
import { buildBlock } from "./blocks/adapter.mjs";
import { blockFor, isBlock } from "./blocks/registry.mjs";

const ENTRANCE = {
  rise: { from: { opacity: 0, y: 40 }, to: { opacity: 1, y: 0 } },
  fade: { from: { opacity: 0 }, to: { opacity: 1 } },
  sweep: { from: { opacity: 0, x: -48 }, to: { opacity: 1, x: 0 } },
  pulse: { from: { opacity: 0, scale: 0.94 }, to: { opacity: 1, scale: 1 } },
  // Structural kinds fall back to a plain rise at the shell level; the layout
  // owns their actual motion (connectors, arrows, spins).
  draw: { from: { opacity: 0, y: 24 }, to: { opacity: 1, y: 0 } },
  travel: { from: { opacity: 0, y: 24 }, to: { opacity: 1, y: 0 } },
  spin: { from: { opacity: 0, scale: 0.94 }, to: { opacity: 1, scale: 1 } },
};

export function compose(specInput, optionInput) {
  const spec = parseSpec(specInput);
  const opt = { ...parseOptions(optionInput), durationMs: spec.motion.durationMs };
  const pal = palette(spec);
  const u = (opt.width / 1080).toFixed(4);
  const ctx = { spec, opt, pal, esc, escAttr, icon, u, dur: opt.durationMs / 1000 };
  // A layout name is either backed by a catalog block (the migration) or by a
  // hand-written builder still in src/layouts/. Both return the same
  // {css, body, anim} contract, so the shell below is unaware of which.
  const layout = isBlock(spec.layout) ? buildBlock(blockFor(spec.layout), ctx) : buildLayout(spec.layout, ctx);

  const durationSec = (opt.durationMs / 1000).toFixed(3);
  const entrance = ENTRANCE[spec.motion.kind] || ENTRANCE.rise;
  const foot = spec.alt ? `<div class="foot clip" data-start="0" data-duration="${durationSec}" data-track-index="0" id="foot">${esc(spec.alt)}</div>` : "";

  const shellAnim = [
    `tl.fromTo("#kicker", { opacity: 0, y: -16 }, { opacity: 1, y: 0, duration: 0.5 }, 0.0);`,
    `tl.fromTo("#title", ${JSON.stringify(entrance.from)}, { ...${JSON.stringify(entrance.to)}, duration: 0.9, ease: "power3.out" }, 0.12);`,
    `tl.fromTo("#rule", { scaleX: 0 }, { scaleX: 1, duration: 0.9, ease: "power2.inOut" }, 0.45);`,
    spec.alt ? `tl.fromTo("#foot", { opacity: 0 }, { opacity: 1, duration: 0.6 }, ${Math.max(0.8, opt.durationMs / 1000 - 1.1).toFixed(2)});` : "",
  ]
    .filter(Boolean)
    .join("\n      ");

  const html = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=${opt.width}, height=${opt.height}" />
    <title>${esc(spec.title)}</title>
    <style>
${shellCss(pal, opt)}
${layout.css}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="${durationSec}" data-fps="${opt.fps}" data-width="${opt.width}" data-height="${opt.height}">
      <header class="head">
        <div class="kicker" id="kicker">Data</div>
        <h1 id="title">${esc(spec.title)}</h1>
        <div class="rule" id="rule"></div>
      </header>
      <div class="canvas" id="canvas">${layout.body}</div>
      ${foot}
    </div>
    <script src="./vendor/gsap.min.js"></script>
    <script>
      const tl = gsap.timeline({ paused: true });
      ${shellAnim}
      ${layout.anim}
      window.__timelines = window.__timelines || {};
      window.__timelines["main"] = tl;
      tl.seek(0);
    </script>
  </body>
</html>
`;

  return { html, spec, opt };
}
