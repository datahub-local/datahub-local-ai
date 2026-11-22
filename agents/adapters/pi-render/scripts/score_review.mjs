#!/usr/bin/env node
// Hand-run evaluation of the studio's critic prompt. Not CI: it needs the gateway and a
// labelled corpus, and the point is to measure a prompt edit before it reaches a live run.
//
//   REVIEW_BASE_URL=https://gateway/v1 REVIEW_API_KEY=... REVIEW_MODEL=opencode-go/minimax-m3 \
//     node scripts/score_review.mjs --cases test/fixtures/review \
//     --prompt ../../n8n/prompts/visual_review_composition.md
//
// `--cases` names a directory with `cases.json` and its stills. The schema is in
// `test/fixtures/review/README.md`. TPR is the share of labelled-defect cases whose verdict is
// `fix` and that name at least one expected defect; TNR is the share of clean cases whose verdict
// is `ok`. `unparsed` is the share of answers with no parseable object.

import { readFile } from "node:fs/promises";
import { dirname, extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const args = process.argv.slice(2);
const flag = (name, fallback) => {
  const i = args.indexOf(name);
  return i === -1 ? fallback : args[i + 1];
};

const adapterRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const samples = Math.max(1, Number(flag("--samples", "1")) || 1);
const casesArg = flag("--cases", null);
const promptArg = flag("--prompt", null);
const casesDir = casesArg ? resolve(casesArg) : join(adapterRoot, "test/fixtures/review");
const promptPath = promptArg ? resolve(promptArg) : resolve(adapterRoot, "../../n8n/prompts/visual_review_composition.md");
const base = String(process.env.REVIEW_BASE_URL || "").replace(/\/+$/, "");
const key = String(process.env.REVIEW_API_KEY || "");
const model = String(process.env.REVIEW_MODEL || "opencode-go/minimax-m3");

const MIME = { ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp" };

function parseAnswer(raw) {
  const start = raw.indexOf("{");
  const end = raw.lastIndexOf("}");
  if (start === -1 || end <= start) return null;
  try {
    const parsed = JSON.parse(raw.slice(start, end + 1));
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

// A labelled defect is found when any of its keywords appears in the answer's findings. Keywords
// are deliberately short ("no head", "overlap") so a paraphrase still counts; punctuation and
// case are removed because a model writes "counter reads '0'" where the label says "counter
// reads 0".
const norm = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ").trim();
function found(expected, answer) {
  const text = norm((Array.isArray(answer.findings) ? answer.findings : [])
    .map((f) => `${f.where || ""} ${f.what || ""} ${f.fix || ""}`)
    .join(" "));
  return (expected.findings || []).some((f) =>
    String(f.what || "").split(";").map(norm).filter(Boolean).some((k) => text.includes(k)));
}

async function ask(prompt, brief, stills, sheet) {
  const content = [{ type: "text", text: prompt + "\n\n---\n\nThe brief the composer was given:\n" + brief }];
  const files = sheet ? [sheet, ...stills] : stills;
  if (sheet) content.push({ type: "text", text: "The first image is a contact sheet: one frame per second, row-major. Use it to see what plays between the detailed stills; the detailed stills follow it, and the last detailed still is the settled frame." });
  for (const file of files) {
    const bytes = await readFile(resolve(casesDir, file));
    content.push({ type: "image_url", image_url: { url: `data:${MIME[extname(file).toLowerCase()] || "image/jpeg"};base64,${bytes.toString("base64")}` } });
  }
  const res = await fetch(`${base}/chat/completions`, {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${key}` },
    body: JSON.stringify({ model, messages: [{ role: "user", content }] }),
    signal: AbortSignal.timeout(600_000),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${(await res.text()).slice(0, 300)}`);
  const body = await res.json();
  return String((((body.choices || [])[0] || {}).message || {}).content || "").trim();
}

const cases = await (async () => {
  try {
    return JSON.parse(await readFile(join(casesDir, "cases.json"), "utf8"));
  } catch {
    return null;
  }
})();
const prompt = (await readFile(promptPath, "utf8")).trim();
if (!Array.isArray(cases) || !cases.length) {
  console.error(`no cases in ${join(casesDir, "cases.json")}; see test/fixtures/review/README.md`);
  process.exit(2);
}
if (!base || !key) {
  console.error("set REVIEW_BASE_URL and REVIEW_API_KEY (and optionally REVIEW_MODEL)");
  process.exit(2);
}

let positives = 0;
let negatives = 0;
let unparsed = 0;
const rows = [];

for (const entry of cases) {
  const expected = entry.expected || {};
  const isDefect = String(expected.verdict || "").toLowerCase() === "fix";
  if (isDefect) positives += 1; else negatives += 1;
  const runs = [];
  for (let i = 0; i < samples; i += 1) {
    const raw = await ask(prompt, String(entry.brief || ""), entry.stills || [], entry.sheet);
    const answer = parseAnswer(raw);
    if (!answer) unparsed += 1;
    const verdict = answer ? String(answer.verdict || "").toLowerCase() : "unparsed";
    const verdictHit = isDefect ? verdict === "fix" : verdict === "ok";
    const findingHit = answer && isDefect ? found(expected, answer) : isDefect ? false : true;
    runs.push({ verdict, verdictHit, findingHit, raw: raw.slice(0, 400) });
  }
  rows.push({ name: entry.name || "(unnamed)", expected: expected.verdict || "ok", runs });
}

const pct = (n, d) => (d ? `${Math.round((n / d) * 1000) / 10}%` : "n/a");
console.log(`model ${model}  cases ${cases.length}  samples ${samples}  unparsed ${pct(unparsed, cases.length * samples)}`);
for (const row of rows) {
  const hits = row.runs.filter((x) => x.verdictHit && x.findingHit).length;
  const anyVerdict = row.runs.filter((x) => x.verdictHit).length;
  console.log(`${hits ? "PASS" : "FAIL"}  ${row.name}  expected ${row.expected}  verdict ${anyVerdict}/${samples}  finding ${hits}/${samples}`);
  for (const x of row.runs.filter((y) => !(y.verdictHit && y.findingHit))) console.log(`      got ${x.verdict}: ${x.raw}`);
}
const pos = rows.filter((r) => r.expected === "fix");
const neg = rows.filter((r) => r.expected !== "fix");
// TPR counts a case when at least one sample names a labelled defect; TNR when at least one
// sample is clean. Per-sample counts are printed above, because the critic is not stable.
const tpr = pos.filter((r) => r.runs.some((x) => x.verdictHit && x.findingHit)).length;
const tnr = neg.filter((r) => r.runs.some((x) => x.verdictHit)).length;
console.log(`TPR ${tpr}/${pos.length} = ${pct(tpr, pos.length)}   TNR ${tnr}/${neg.length} = ${pct(tnr, neg.length)}`);
console.log(`finding recall ${pct(pos.reduce((n, r) => n + r.runs.filter((x) => x.findingHit).length, 0), pos.length * samples)}`);
process.exit(unparsed ? 1 : 0);
