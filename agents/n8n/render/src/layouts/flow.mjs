// flow: connected nodes in a sequence. The structural motion is the point - each
// connector draws itself and an arrow travels along it before the next node
// lands - so the diagram reads as movement from A to B, not a list.

export function build(ctx) {
  const { spec, esc, icon, u } = ctx;
  const parts = [];

  spec.blocks.forEach((b, i) => {
    if (i > 0) {
      parts.push(
        `<div class="f-link">` +
          `<svg viewBox="0 0 120 100" preserveAspectRatio="none">` +
          `<path class="f-trace" id="f-trace-${i}" d="M60 2 C 60 60, 60 40, 60 96" pathLength="100" />` +
          `<path class="f-head" id="f-head-${i}" d="M60 98 l-11 -14 22 0 z" />` +
          `</svg></div>`
      );
    }
    const ico = icon(b.icon);
    parts.push(
      `<div class="f-node" id="f-node-${i}">` +
        (ico ? ico.svg : "") +
        `<div class="f-txt"><div class="f-label">${esc(b.label)}</div>` +
        `<div class="f-sub">${esc(b.value)}</div></div>` +
        `</div>`
    );
  });

  const css = `
    .flow { display: flex; flex-direction: column; height: 100%; justify-content: center; }
    .f-node { display: flex; align-items: center; gap: calc(26px * var(--u));
      padding: calc(28px * var(--u)) calc(32px * var(--u));
      border: 1px solid var(--line); border-radius: calc(20px * var(--u));
      background: linear-gradient(180deg, color-mix(in srgb, var(--ink) 6%, transparent), var(--card)); }
    .f-label { font-size: calc(42px * var(--u)); font-weight: 650; }
    .f-sub { font-size: calc(27px * var(--u)); color: var(--muted); margin-top: calc(4px * var(--u)); }
    .f-link { position: relative; flex: 1 1 0; min-height: calc(56px * var(--u)); }
    .f-link svg { position: absolute; left: calc(52px * var(--u)); top: 0;
      width: calc(90px * var(--u)); height: 100%; overflow: visible; }
    .f-trace { fill: none; stroke: var(--accent); stroke-width: 5; stroke-linecap: round;
      stroke-dasharray: 100; stroke-dashoffset: 100; }
    .f-head { fill: var(--accent); opacity: 0; }
  `;

  const anim = spec.blocks
    .map((_, i) => {
      const start = 0.85 + i * 0.75;
      const out = [`tl.fromTo("#f-node-${i}", { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.5, ease: "back.out(1.5)" }, ${start.toFixed(2)});`];
      if (i > 0) {
        out.push(`tl.fromTo("#f-trace-${i}", { strokeDashoffset: 100 }, { strokeDashoffset: 0, duration: 0.5, ease: "power2.inOut" }, ${(start - 0.55).toFixed(2)});`);
        out.push(`tl.to("#f-head-${i}", { opacity: 1, duration: 0.18 }, ${(start - 0.08).toFixed(2)});`);
      }
      return out.join("\n      ");
    })
    .join("\n      ");

  return { css, body: `<div class="flow">\n      ${parts.join("\n      ")}\n    </div>`, anim };
}
