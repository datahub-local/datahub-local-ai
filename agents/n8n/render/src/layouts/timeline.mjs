// timeline: ordered points down an axis. The axis draws itself first, then each
// marker pops in reading order, so a sequence reads as time passing.

export function build(ctx) {
  const { spec, esc, icon, u } = ctx;
  const n = spec.blocks.length;
  const rows = spec.blocks
    .map((b, i) => {
      const ico = icon(b.icon);
      return (
        `<div class="t-row" id="t-row-${i}">` +
        `<span class="t-dot"></span>` +
        `<div class="t-card">` +
        (ico ? ico.svg : "") +
        `<div class="t-txt"><div class="t-label">${esc(b.label)}</div>` +
        `<div class="t-sub">${esc(b.value)}</div></div>` +
        `</div></div>`
      );
    })
    .join("\n      ");

  const css = `
    .timeline { position: relative; height: 100%; padding-left: calc(60px * var(--u));
      display: flex; flex-direction: column; justify-content: space-around; }
    .t-axis { position: absolute; left: calc(11px * var(--u)); top: calc(16px * var(--u));
      bottom: calc(16px * var(--u)); width: 3px; background: var(--accent);
      transform-origin: top center; }
    .t-row { display: flex; align-items: center; gap: calc(30px * var(--u)); }
    .t-dot { position: absolute; left: calc(3px * var(--u)); width: calc(19px * var(--u));
      height: calc(19px * var(--u)); border-radius: 50%; background: var(--accent);
      box-shadow: 0 0 0 calc(8px * var(--u)) color-mix(in srgb, var(--accent) 16%, transparent); }
    .t-card { display: flex; align-items: center; gap: calc(22px * var(--u)); width: 100%;
      padding: calc(24px * var(--u)) calc(30px * var(--u));
      border: 1px solid var(--line); border-radius: calc(18px * var(--u)); background: var(--card); }
    .t-label { font-size: calc(40px * var(--u)); font-weight: 650; }
    .t-sub { font-size: calc(26px * var(--u)); color: var(--muted); margin-top: calc(3px * var(--u)); }
  `;

  const anim = [
    `tl.fromTo(".t-axis", { scaleY: 0 }, { scaleY: 1, duration: 1.0, ease: "power2.inOut" }, 0.8);`,
  ];
  spec.blocks.forEach((_, i) => {
    const at = (1.3 + i * 0.5).toFixed(2);
    anim.push(`tl.fromTo("#t-row-${i}", { opacity: 0, x: -36 }, { opacity: 1, x: 0, duration: 0.5, ease: "power3.out" }, ${at});`);
  });

  return {
    css,
    body: `<div class="timeline"><div class="t-axis"></div>\n      ${rows}\n    </div>`,
    anim: anim.join("\n      "),
  };
}
