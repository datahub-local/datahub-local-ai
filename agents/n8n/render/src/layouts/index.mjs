import { build as stats } from "./stats.mjs";
import { build as flow } from "./flow.mjs";
import { build as timeline } from "./timeline.mjs";
import { build as comparison } from "./comparison.mjs";
import { build as bars } from "./bars.mjs";

const LAYOUTS = { stats, flow, timeline, comparison, bars };

export function build(layout, ctx) {
  const fn = LAYOUTS[layout];
  if (!fn) throw new Error(`unknown layout: ${layout}`);
  return fn(ctx);
}
