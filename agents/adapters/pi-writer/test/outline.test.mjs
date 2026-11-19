import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { outlinePrompt, parseOutline } from "../session-lib.mjs";

const prompt = (name) =>
  readFile(fileURLToPath(new URL(`../prompts/${name}`, import.meta.url)), "utf8");
const [template, structures, audiences] = await Promise.all([
  prompt("article_outline.md"),
  prompt("article_structures.md"),
  prompt("article_audiences.md"),
]);

const brief = {
  topic: "PROBE_TOPIC",
  description: "PROBE_DESCRIPTION",
  url: "https://github.com/datahub-local/datahub-local-ai",
  content: "PROBE_SEED",
  audience: "LOW",
  extra_prompt: "PROBE_EXTRA",
  max_words: 1200,
  asset_types: "image_wide,svg_wide",
};

const render = (over = {}) => outlinePrompt({ ...brief, ...over }, { template, structures, audiences });

test("the outline prompt is filled from the entry, the shapes and the audience levels", () => {
  const text = render();
  for (const value of ["PROBE_TOPIC", "PROBE_DESCRIPTION", "PROBE_SEED", "PROBE_EXTRA", "1200", "image_wide,svg_wide"]) {
    assert.ok(text.includes(value), `${value} did not reach the outline prompt`);
  }
  // The two rule files are the image's, not the caller's: the shape names the answer must choose
  // from and the audience level it writes for both arrive from prompts/.
  assert.ok(text.includes("## One spine"), "the shapes did not reach the outline prompt");
  assert.ok(text.includes("## Getting started"), "the shape headings did not reach the outline prompt");
  assert.ok(text.includes("## LOW"), "the audience levels did not reach the outline prompt");
  assert.match(text, /<outline>[\s\S]*Option 1[\s\S]*shape: /, "the pinned block is not in the prompt");
  assert.ok(!/\{\{\s*[A-Z_]+\s*\}\}/.test(text), "a placeholder was left unrendered");
});

const option = (n, shape, sections) =>
  [
    `Option ${n}`,
    `shape: ${shape}`,
    `outcome: outcome of option ${n}`,
    "sections:",
    ...sections.map(([name, job, form], index) => `${index + 1}. ${name} — ${job}${form ? ` [${form}]` : ""}`),
  ].join("\n");

const sections = [
  ["What to prepare", "name the cluster and the CLI before anything runs", "prose"],
  ["The smallest install", "run it and show what success looks like", "code"],
  ["Where it breaks", "the trap that stops this walk-through — and its fix", "prose"],
  ["What is next", "the first change to make after the install", "prose"],
];

test("a two-option answer parses into shapes, outcomes and sections", () => {
  const text = `<outline>\n${option(1, "Getting started", sections)}\n${option(2, "A comparison", sections)}\n</outline>`;
  const { options, error } = parseOutline(text);
  assert.equal(error, "");
  assert.equal(options.length, 2);
  assert.equal(options[0].shape, "Getting started");
  assert.equal(options[0].outcome, "outcome of option 1");
  assert.equal(options[0].sections.length, 4);
  assert.deepEqual(options[0].sections[0], {
    name: "What to prepare",
    job: "name the cluster and the CLI before anything runs",
    form: "prose",
  });
  // The job's own dash is not a second separator: only the first one splits the line.
  assert.equal(options[0].sections[2].job, "the trap that stops this walk-through — and its fix");
  assert.equal(options[0].sections[1].form, "code");
  assert.equal(options[1].shape, "A comparison");
});

test("a section carries its form, and anything else reads as prose", () => {
  const text = `<outline>\n${option(1, "A comparison", [
    ["What each is", "the deciding dimensions", "table"],
    ["Migration cost", "the work each move takes", "diagram"],
    ["Who picks which", "the boundary", undefined],
    ["Licence", "what each permits", "list"],
  ])}\n${option(2, "A comparison", sections)}\n</outline>`;
  const { options, error } = parseOutline(text);
  assert.equal(error, "");
  assert.deepEqual(options[0].sections.map((section) => section.form), ["table", "prose", "prose", "list"]);
  // The unknown bracket is the form's slot, not part of the job.
  assert.equal(options[0].sections[1].job, "the work each move takes");
  assert.equal(options[0].sections.filter((section) => section.form === "code").length, 0);
});

test("three options are accepted, and the answer may sit inside prose", () => {
  const inner = [1, 2, 3].map((n) => option(n, "A comparison", sections)).join("\n");
  const { options, error } = parseOutline(`Here are the indexes.\n\n<outline>\n${inner}\n</outline>\n`);
  assert.equal(error, "");
  assert.equal(options.length, 3);
});

test("an empty answer names the missing block and offers no options", () => {
  for (const text of ["", "   ", "I could not plan this article."]) {
    const { options, error } = parseOutline(text);
    assert.deepEqual(options, []);
    assert.match(error, /no balanced <outline> block/);
  }
});

test("unbalanced tags are not a block", () => {
  const unclosed = `<outline>\n${option(1, "Getting started", sections)}`;
  assert.match(parseOutline(unclosed).error, /no balanced <outline> block/);
  const closedWithoutOpen = `${option(1, "Getting started", sections)}\n</outline>`;
  assert.match(parseOutline(closedWithoutOpen).error, /no balanced <outline> block/);
});

test("an option with no sections fails by name", () => {
  const text = `<outline>\n${option(1, "Getting started", [])}\n${option(2, "A comparison", sections)}\n</outline>`;
  const { options, error } = parseOutline(text);
  assert.deepEqual(options, []);
  assert.match(error, /option 1 lists 0 sections; 3 to 8 are required/);
});

test("an option with no shape or no outcome fails by name", () => {
  const noShape = `<outline>\n${option(1, "", sections)}\n${option(2, "A comparison", sections)}\n</outline>`;
  assert.match(parseOutline(noShape).error, /option 1 names no shape/);
  const noOutcome = `<outline>\nOption 1\nshape: Getting started\nsections:\n- a — b\n- c — d\n- e — f\n${option(2, "A comparison", sections)}\n</outline>`;
  assert.match(parseOutline(noOutcome).error, /option 1 states no outcome/);
});

test("a section line without its job fails by name", () => {
  const text = `<outline>\n${option(1, "Getting started", [["What to prepare", ""]])}\n${option(2, "A comparison", sections)}\n</outline>`;
  assert.match(parseOutline(text).error, /carries no "name — job"/);
});

test("a block that is not the pinned form fails by name", () => {
  const stray = `<outline>\nprose before any option\n${option(1, "Getting started", sections)}\n</outline>`;
  assert.match(parseOutline(stray).error, /before its first option/);
  const noise = `<outline>\n${option(1, "Getting started", sections)}\nNotes: the second index is better\n${option(2, "A comparison", sections)}\n</outline>`;
  assert.match(parseOutline(noise).error, /not part of its form/);
});

test("the option count is the format's, not the model's choice", () => {
  const one = `<outline>\n${option(1, "Getting started", sections)}\n</outline>`;
  assert.match(parseOutline(one).error, /lists 1 options; 2 or 3 are required/);
  const four = [1, 2, 3, 4].map((n) => option(n, "A comparison", sections)).join("\n");
  assert.match(parseOutline(`<outline>\n${four}\n</outline>`).error, /lists 4 options; 2 or 3 are required/);
  const none = "<outline>\n</outline>";
  assert.match(parseOutline(none).error, /lists no option/);
});
