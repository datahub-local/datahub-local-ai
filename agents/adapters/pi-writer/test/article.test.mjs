import { test } from "node:test";
import assert from "node:assert/strict";

import { splitArticle, articleWordCount, articleWordLimit } from "../session-lib.mjs";

test("the H1 becomes the title and the rest is the body", () => {
  const { title, text } = splitArticle("# Probe\n\n## Install\n\nUse it.\n");
  assert.equal(title, "Probe");
  assert.equal(text, "## Install\n\nUse it.");
});

test("an article block is unwrapped before the title is read", () => {
  const { title, text } = splitArticle("<article># Probe\n\nBody</article>");
  assert.equal(title, "Probe");
  assert.equal(text, "Body");
});

test("a body with no H1 keeps an empty title", () => {
  const { title, text } = splitArticle("## Install\n\nUse it.");
  assert.equal(title, "");
  assert.equal(text, "## Install\n\nUse it.");
});

test("asset markers do not count as words", () => {
  assert.equal(articleWordCount("one two\n<!-- asset:hero -->\nthree"), 3);
});

test("the limit is the budget plus a counting margin, in integers", () => {
  assert.equal(articleWordLimit(1200), 1320);
  assert.equal(articleWordLimit(0), 0);
  assert.equal(articleWordLimit(undefined), 0);
});
