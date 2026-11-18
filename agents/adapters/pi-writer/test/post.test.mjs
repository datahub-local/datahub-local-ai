import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { chooseDirectives, parsePostHook, applyChosenHook, renderHookList } from "../session-lib.mjs";

const variety = await readFile(fileURLToPath(new URL("../prompts/linkedin_variety.md", import.meta.url)), "utf8");

const draw = (random, extra = {}) =>
  chooseDirectives({ variety, minWords: 150, maxWords: 300, random, ...extra });

test("a zero draw takes the first weighted option and puts the length inside the range", () => {
  const chosen = draw(() => 0);
  assert.match(chosen.directives, /LIST BODY: a two-sentence lead/);
  assert.match(chosen.directives, /MEDIUM: aim for about 225 words, never fewer than 150 and never more than 300/);
  assert.match(chosen.directives, /DIRECT QUESTION/);
});

test("the draw reads the weights as duplication, not as a percentage", () => {
  // format carries 2 | LIST BODY, 2 | PURE PROSE, 1 | NUMBERED LIST: a draw at 0.4 is the
  // first PURE PROSE slot, and 0.8 is the numbered list. A plain average of three would
  // put 0.4 inside the list slots and quietly change the distribution.
  assert.match(draw(() => 0.4).directives, /PURE PROSE/);
  assert.match(draw(() => 0.8).directives, /NUMBERED LIST/);
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

const hooks = [
  { id: "TRADE_OFF", when: "PROBE_WHEN_TRADE", opening: "PROBE_OPEN_TRADE" },
  { id: "CONTRARIAN", when: "PROBE_WHEN_CONTRA", opening: "PROBE_OPEN_CONTRA" },
];

test("the eligibility list carries each hook's when and opening, one line each", () => {
  assert.equal(
    renderHookList(hooks),
    "- TRADE_OFF — when: PROBE_WHEN_TRADE; open: PROBE_OPEN_TRADE\n" +
      "- CONTRARIAN — when: PROBE_WHEN_CONTRA; open: PROBE_OPEN_CONTRA"
  );
  assert.equal(renderHookList(undefined), "");
  assert.equal(renderHookList([{ when: "no id" }]), "");
});

test("a hook-less answer's tag is the choice, and an id off the list fails by name", () => {
  const chosen = parsePostHook("post body\n<hook> contrarian </hook>", { hooks });
  assert.deepEqual(chosen, { hook: "CONTRARIAN", opening: "PROBE_OPEN_CONTRA", error: "" });

  const missing = parsePostHook("post body", { hooks });
  assert.equal(missing.hook, "");
  assert.match(missing.error, /carries no <hook> tag although the brief offered 2/);

  const unknown = parsePostHook("<output>body</output><hook>WAR_STORY</hook>", { hooks });
  assert.match(unknown.error, /<hook>WAR_STORY<\/hook>, which the brief's hook list does not carry/);
});

test("an assigned hook needs no tag, and an empty list offers nothing to fail on", () => {
  assert.deepEqual(parsePostHook("post body", { hooks, assigned: "trade_off" }), {
    hook: "TRADE_OFF",
    opening: "",
    error: "",
  });
  assert.deepEqual(parsePostHook("post body", { hooks: [] }), { hook: "", opening: "", error: "" });
});

test("the chosen hook rewrites the stored directive and its id, so the gate judges that shape", () => {
  const drawn = draw(() => 0);
  assert.equal(drawn.hook_id, "");
  const chosen = applyChosenHook(drawn, { hook: "contrarian", hookOpening: "open with a blunt statement" });
  assert.equal(chosen.hook_id, "CONTRARIAN");
  assert.match(chosen.directives, /- Hook — CONTRARIAN: open with a blunt statement\./);
  // The other three directives are the drawn ones, untouched.
  assert.match(chosen.directives, /- Format — LIST BODY: a two-sentence lead/);
  assert.match(chosen.directives, /- Closing — DIRECT QUESTION/);
});
