import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const prompt = await readFile(new URL("../prompts/article_review.md", import.meta.url), "utf8");

test("the fact check accepts a page the writer fetched", () => {
  assert.match(prompt, /a page the writer fetched during this run/);
  assert.match(prompt, /A fact from a fetched page is sourced/);
  assert.match(prompt, /absent from all of them is invented/);
});

test("the source link is not rejected as an unfetched citation", () => {
  assert.match(prompt, /the entry's source link is not/);
});

test("the source block names the seed page, not the whole fetched corpus", () => {
  assert.match(prompt, /The entry's seed page\./);
  assert.doesNotMatch(prompt, /what the writer fetched during the run/);
});
