// The writer's in-turn check has to report the number the gate will enforce, or a draft that
// passed locally is rejected by the code gate and the run spends another attempt. These tests
// run the real script against a fake run directory: no Pi, no model, no cluster.

import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { cp, mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const adapter = join(here, "..");

async function check(bodyWords, budget) {
  const dir = await mkdtemp(join(tmpdir(), "check-article-"));
  await cp(join(adapter, "bin", "check-article.mjs"), join(dir, "check-article.mjs"));
  await cp(join(adapter, "session-lib.mjs"), join(dir, "session-lib.mjs"));
  await writeFile(join(dir, "article.md"), `# Probe\n\n${Array.from({ length: bodyWords }, () => "word").join(" ")}\n`);
  const sessions = join(dir, "sessions");
  await mkdir(sessions);
  // An empty transcript is enough: this article has no fence, and the budget verdict must not
  // depend on a page having been read.
  await writeFile(join(sessions, "20260101_probe.jsonl"), "");
  const result = spawnSync(process.execPath, [join(dir, "check-article.mjs"), "article.md"], {
    cwd: dir,
    encoding: "utf8",
    env: {
      ...process.env,
      PI_WRITER_SESSION_ID: "probe",
      PI_WRITER_SESSION_DIR: sessions,
      PI_WRITER_MAX_WORDS: String(budget),
    },
  });
  return result;
}

test("a body past the counting margin fails with the words to cut", async () => {
  const result = await check(120, 100);
  assert.equal(result.status, 1);
  assert.match(result.stdout, /WORDS: 120 of 110 \(budget 100\) — cut at least 10 words/);
  assert.match(result.stdout, /0 block\(s\) quoted, 0 missing/);
});

test("a body inside the limit passes", async () => {
  const result = await check(100, 100);
  assert.equal(result.status, 0);
  assert.match(result.stdout, /WORDS: 100 of 110 \(budget 100\)/);
});

test("no budget on the turn reports the count without a verdict", async () => {
  const result = await check(120, 0);
  assert.equal(result.status, 0);
  assert.doesNotMatch(result.stdout, /WORDS:/);
});
