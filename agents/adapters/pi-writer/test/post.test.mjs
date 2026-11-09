import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { chooseDirectives } from "../session-lib.mjs";

const variety = await readFile(fileURLToPath(new URL("../prompts/linkedin_variety.md", import.meta.url)), "utf8");

const draw = (random, extra = {}) =>
  chooseDirectives({ variety, minWords: 150, maxWords: 300, random, ...extra });

test("a zero draw takes the first weighted option and puts the length inside the range", () => {
  const chosen = draw(() => 0);
  assert.match(chosen.directives, /PURE PROSE: no bullet points at all/);
  assert.match(chosen.directives, /MEDIUM: aim for about 225 words, never fewer than 150 and never more than 300/);
  assert.match(chosen.directives, /DIRECT QUESTION/);
});

test("the draw reads the weights as duplication, not as a percentage", () => {
  // format carries 2 | PURE PROSE, 2 | PUNCHY, 1 | ONE BULLET BLOCK: a draw at 0.4 is the
  // second PUNCHY slot, and 0.8 is the bullet block. A plain average of three would put
  // 0.4 inside PURE PROSE and quietly change the distribution.
  assert.match(draw(() => 0.4).directives, /PUNCHY/);
  assert.match(draw(() => 0.8).directives, /ONE BULLET BLOCK/);
});

test("the hook opening is the row's decision, and a row without one leaves the shape to the writer", () => {
  const withHook = draw(() => 0, { hook: "trade_off", hookOpening: "open by framing the trade-off" });
  assert.match(withHook.directives, /- Hook — TRADE_OFF: open by framing the trade-off\./);

  const without = draw(() => 0, { hook: "", hookOpening: "" });
  assert.match(without.directives, /- Hook — the opening shape that best fits the content\./);
});

test("the length target never falls below the requested minimum", () => {
  // The old Code node's comment records the failure this prevents: a share of the maximum
  // can land under the minimum, and the directives are mandatory, so the model writes short.
  // The target is an offset from the minimum, so every band lands inside the range.
  const shortest = draw(() => 0, { minWords: 180, maxWords: 200 });
  assert.match(shortest.directives, /aim for about 190 words, never fewer than 180/);
  for (const random of [0, 0.35, 0.7]) {
    const chosen = draw(() => random, { minWords: 180, maxWords: 300 });
    const target = Number(/aim for about (\d+) words/.exec(chosen.directives)[1]);
    assert.ok(target >= 180 && target <= 300, `${target} is outside 180..300`);
  }
});

test("a missing option set fails by name rather than drawing an empty directive", () => {
  assert.throws(
    () => chooseDirectives({ variety: "## format\n\n2 | | PURE PROSE\n", minWords: 150, maxWords: 200 }),
    /carries no length options/
  );
});
