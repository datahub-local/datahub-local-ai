// stats: the studio's original shape - a labelled figure list - now with an
// optional icon per row. This is the default layout, so it must render a spec
// that carries nothing but title/blocks/accent exactly as before.

export function build(ctx) {
  const { spec, esc, icon, u } = ctx;
  const rows = spec.blocks
    .map((b, i) => {
      const ico = icon(b.icon);
      return (
        `<div class="s-row" id="s-row-${i}">` +
        (ico ? ico.svg : "") +
        `<span class="s-label">${esc(b.label)}</span>` +
        `<span class="s-value">${esc(b.value)}</span>` +
        `</div>`
      );
    })
    .join("\n      ");

  const css = `
    .stats { display: flex; flex-direction: column; justify-content: center; height: 100%; gap: calc(30px * var(--u)); }
    .s-row { display: flex; align-items: center; gap: calc(24px * var(--u));
      padding-bottom: calc(20px * var(--u)); border-bottom: 2px solid var(--line); }
    .s-row .glyph { width: calc(56px * var(--u)); height: calc(56px * var(--u)); }
    .s-label { flex: 1; font-size: calc(36px * var(--u)); color: var(--muted); }
    .s-value { font-size: calc(58px * var(--u)); font-weight: 700; letter-spacing: -0.02em;
      color: var(--accent); text-align: right; }
  `;

  const anim = spec.blocks
    .map((_, i) => {
      const at = (0.9 + i * 0.22).toFixed(2);
      return (
        `tl.fromTo("#s-row-${i}", { opacity: 0, y: 34 }, ` +
        `{ opacity: 1, y: 0, duration: 0.55, ease: "power3.out" }, ${at});`
      );
    })
    .join("\n      ");

  return { css, body: `<div class="stats">\n      ${rows}\n    </div>`, anim };
}
