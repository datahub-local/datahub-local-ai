// comparison: two opposed sides. Blocks alternate left/right, so an idea that is
// a before/after or an A-vs-B reads as two columns meeting at a divider rather
// than as another list.

export function build(ctx) {
  const { spec, esc, icon, u } = ctx;
  const left = [];
  const right = [];
  spec.blocks.forEach((b, i) => {
    const ico = icon(b.icon);
    const cell =
      `<div class="c-card" id="c-card-${i}">` +
      (ico ? ico.svg : "") +
      `<div class="c-value">${esc(b.value)}</div>` +
      `<div class="c-label">${esc(b.label)}</div>` +
      `</div>`;
    (i % 2 === 0 ? left : right).push(cell);
  });

  const css = `
    .comparison { display: grid; grid-template-columns: 1fr 3px 1fr; gap: calc(34px * var(--u));
      height: 100%; align-items: center; }
    .c-col { display: flex; flex-direction: column; gap: calc(30px * var(--u)); }
    .c-divider { align-self: stretch; background: linear-gradient(180deg, transparent, var(--accent), transparent);
      transform-origin: center; }
    .c-card { padding: calc(30px * var(--u)); border: 1px solid var(--line);
      border-radius: calc(18px * var(--u)); background: var(--card); text-align: center; }
    .c-card .glyph { margin: 0 auto calc(14px * var(--u)); width: calc(52px * var(--u)); height: calc(52px * var(--u)); }
    .c-value { font-size: calc(52px * var(--u)); font-weight: 700; color: var(--accent); letter-spacing: -0.02em; }
    .c-label { font-size: calc(26px * var(--u)); color: var(--muted); margin-top: calc(6px * var(--u)); }
  `;

  const anim = [`tl.fromTo(".c-divider", { scaleY: 0 }, { scaleY: 1, duration: 0.7, ease: "power2.out" }, 0.8);`];
  spec.blocks.forEach((_, i) => {
    const dir = i % 2 === 0 ? -40 : 40;
    const at = (1.0 + i * 0.28).toFixed(2);
    anim.push(`tl.fromTo("#c-card-${i}", { opacity: 0, x: ${dir} }, { opacity: 1, x: 0, duration: 0.5, ease: "power3.out" }, ${at});`);
  });

  return {
    css,
    body:
      `<div class="comparison">` +
      `<div class="c-col">${left.join("")}</div>` +
      `<div class="c-divider"></div>` +
      `<div class="c-col">${right.join("")}</div>` +
      `</div>`,
    anim: anim.join("\n      "),
  };
}
