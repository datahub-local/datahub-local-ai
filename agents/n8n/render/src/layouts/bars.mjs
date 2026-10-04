// bars: values as proportional bars. When a value parses as a number the bar is
// proportional to it; otherwise the bars fall back to an even ramp so a
// non-numeric spec still renders sensibly rather than emptying the chart.

export function build(ctx) {
  const { spec, esc, icon, u } = ctx;

  const nums = spec.blocks.map((b) => {
    const m = String(b.value).replace(/[,\s]/g, "").match(/-?\d+(\.\d+)?/);
    return m ? Number(m[0]) : null;
  });
  const known = nums.filter((n) => n !== null);
  const max = known.length ? Math.max(...known, 1) : spec.blocks.length;

  const rows = spec.blocks
    .map((b, i) => {
      const ico = icon(b.icon);
      const pct = nums[i] === null ? Math.round(((i + 1) / spec.blocks.length) * 100) : Math.round((nums[i] / max) * 100);
      return (
        `<div class="b-row" id="b-row-${i}">` +
        `<div class="b-head">${ico ? ico.svg : ""}<span class="b-label">${esc(b.label)}</span>` +
        `<span class="b-value">${esc(b.value)}</span></div>` +
        `<div class="b-track"><i class="b-fill" id="b-fill-${i}" data-pct="${pct}"></i></div>` +
        `</div>`
      );
    })
    .join("\n      ");

  const css = `
    .bars { display: flex; flex-direction: column; justify-content: center; height: 100%; gap: calc(38px * var(--u)); }
    .b-head { display: flex; align-items: center; gap: calc(18px * var(--u)); margin-bottom: calc(14px * var(--u)); }
    .b-head .glyph { width: calc(40px * var(--u)); height: calc(40px * var(--u)); }
    .b-label { flex: 1; font-size: calc(34px * var(--u)); color: var(--muted); }
    .b-value { font-size: calc(40px * var(--u)); font-weight: 700; color: var(--accent); }
    .b-track { height: calc(18px * var(--u)); border-radius: calc(9px * var(--u)); background: var(--line); overflow: hidden; }
    .b-fill { display: block; height: 100%; width: 0; border-radius: calc(9px * var(--u));
      background: linear-gradient(90deg, var(--accent), var(--accent-2)); }
  `;

  const anim = spec.blocks
    .map((_, i) => {
      const at = (0.9 + i * 0.22).toFixed(2);
      return (
        `tl.fromTo("#b-row-${i}", { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.45, ease: "power3.out" }, ${at});\n      ` +
        `tl.to("#b-fill-${i}", { width: document.querySelector("#b-fill-${i}").dataset.pct + "%", duration: 0.8, ease: "power2.out" }, ${(Number(at) + 0.15).toFixed(2)});`
      );
    })
    .join("\n      ");

  return { css, body: `<div class="bars">\n      ${rows}\n    </div>`, anim };
}
