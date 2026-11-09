#!/usr/bin/env node
// The writer's own check, before it answers: every fenced block in the article has to appear on a
// page this session scraped. Same rule the server applies afterwards, so a missing block is caught
// while the turn can still fix it instead of costing a rejected round.
//
// Usage: check-article [article.md]

import { readFile, readdir } from "node:fs/promises";
import { join } from "node:path";

import { transcriptPages, deriveLedger } from "./session-lib.mjs";

const dir = process.env.PI_WRITER_SESSION_DIR || "/tmp/pi-sessions";
const id = process.env.PI_WRITER_SESSION_ID || "";
const article = process.argv[2] || "article.md";

async function main() {
  if (!id) {
    console.error("check-article: PI_WRITER_SESSION_ID is not set; nothing to check against");
    return 2;
  }
  let text;
  try {
    text = await readFile(article, "utf8");
  } catch {
    console.error(`check-article: no ${article} in ${process.cwd()}`);
    return 2;
  }
  const names = (await readdir(dir).catch(() => [])).filter((name) => name.endsWith(`_${id}.jsonl`)).sort();
  const file = names.at(-1);
  if (!file) {
    console.error(`check-article: no transcript for ${id} in ${dir}; no page can be proved`);
    return 2;
  }
  const rows = [];
  for (const line of (await readFile(join(dir, file), "utf8")).split("\n")) {
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
  return unquoted.length ? 1 : 0;
}

process.exitCode = await main();
