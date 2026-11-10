#!/usr/bin/env node
// The writer's own check, before it answers: every fenced block in the article has to appear on a
// page this session scraped, and the body has to be inside this run's word limit. Same rules the
// server applies afterwards, so a miss is caught while the turn can still fix it instead of costing
// a rejected round.
//
// Usage: check-article [article.md]

import { readFile, readdir } from "node:fs/promises";
import { join } from "node:path";

import {
  transcriptPages,
  deriveLedger,
  splitArticle,
  articleWordCount,
  articleWordLimit,
} from "./session-lib.mjs";

const dir = process.env.PI_WRITER_SESSION_DIR || "/tmp/pi-sessions";
const id = process.env.PI_WRITER_SESSION_ID || "";
const file = process.argv[2] || "article.md";
// The budget is the turn's, not the file's: the server passes it on every drafting and editing
// turn, so a retry under the same row reads the same limit the gate will enforce.
const budget = Number(process.env.PI_WRITER_MAX_WORDS || 0);

// The gate counts the body after the H1, with markers removed. A plain `wc -w article.md` adds the
// title and every marker word, so the two numbers differ; this is the number the gate uses.
function wordVerdict(text) {
  if (!Number.isFinite(budget) || budget <= 0) return { over: false, line: "" };
  const limit = articleWordLimit(budget);
  const words = articleWordCount(splitArticle(text).text);
  const over = words > limit;
  const cut = over ? ` — cut at least ${words - limit} words` : "";
  return { over, line: `WORDS: ${words} of ${limit} (budget ${budget})${cut}` };
}

async function main() {
  if (!id) {
    console.error("check-article: PI_WRITER_SESSION_ID is not set; nothing to check against");
    return 2;
  }
  let text;
  try {
    text = await readFile(file, "utf8");
  } catch {
    console.error(`check-article: no ${file} in ${process.cwd()}`);
    return 2;
  }
  const words = wordVerdict(text);
  if (words.line) console.log(words.line);
  const names = (await readdir(dir).catch(() => [])).filter((name) => name.endsWith(`_${id}.jsonl`)).sort();
  const transcript = names.at(-1);
  if (!transcript) {
    console.error(`check-article: no transcript for ${id} in ${dir}; no page can be proved`);
    return 2;
  }
  const rows = [];
  for (const line of (await readFile(join(dir, transcript), "utf8")).split("\n")) {
    if (!line.trim()) continue;
    try {
      rows.push(JSON.parse(line));
    } catch {
      // a transcript cut mid-line is not evidence
    }
  }
  const { sources, unquoted, unquotedBlocks } = deriveLedger({ article: text, pages: transcriptPages(rows) });
  for (const block of unquotedBlocks ?? []) {
    console.log(`MISSING: ${block.firstLine}${block.reason ? ` — ${block.reason}` : ""}`);
  }
  console.log(`${sources.length} block(s) quoted, ${unquoted.length} missing`);
  return unquoted.length || words.over ? 1 : 0;
}

process.exitCode = await main();
