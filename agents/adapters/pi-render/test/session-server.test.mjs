// End-to-end test of the session server's authoring + artifact contract, with a
// stub `pi` on PATH so no model, engine or ffmpeg is needed. Exercises the MP4
// path (no transcode); the format helpers are covered by session-lib.test.mjs.

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, mkdir, readFile, writeFile, chmod, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const serverPath = fileURLToPath(new URL("../session-server.mjs", import.meta.url));
const port = 18000 + Math.floor(Math.random() * 2000);
const base = `http://127.0.0.1:${port}`;

let dir;
let child;

// A stand-in for Pi: it writes the two files the real agent writes, in its cwd
// (the per-run directory), and reports on stdout.
const STUB_PI = `#!/usr/bin/env node
const fs = require("node:fs");
fs.writeFileSync("index.html", "<div>stub</div>");
fs.writeFileSync("out.mp4", Buffer.from([0, 0, 0, 0x18, 0x66, 0x74, 0x79, 0x70]));
process.stdout.write("rendered 1 frame");
`;

async function waitForHealth(timeoutMs = 10000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(`${base}/healthz`);
      if (r.ok) return;
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error("session server did not become healthy");
}

before(async () => {
  dir = await mkdtemp(join(tmpdir(), "pi-render-"));
  const home = join(dir, "home");
  const workspace = join(dir, "workspace");
  const bin = join(dir, "bin");
  await mkdir(home, { recursive: true });
  await mkdir(workspace, { recursive: true });
  await mkdir(bin, { recursive: true });
  const pi = join(bin, "pi");
  await writeFile(pi, STUB_PI);
  await chmod(pi, 0o755);
  child = spawn(process.execPath, [serverPath], {
    env: {
      ...process.env,
      PATH: `${bin}:${process.env.PATH}`,
      HOME: home,
      SYMPOZIUM_WORKSPACE: workspace,
      SYMPOZIUM_SESSION_PORT: String(port),
      SYMPOZIUM_HARNESS_CONTRACT_VERSION: "v1alpha2",
      MODEL_NAME: "stub",
      MODEL_BASE_URL: "http://127.0.0.1:1/v1",
      OPENAI_API_KEY: "stub",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  await waitForHealth();
});

after(async () => {
  child?.kill("SIGTERM");
  await rm(dir, { recursive: true, force: true });
});

test("an authoring turn writes into its own run directory and returns its artifact", async () => {
  const res = await fetch(`${base}/v1/chat/completions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ messages: [{ role: "user", content: "make a card" }], session_id: "run_a" }),
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.choices[0].message.content, "rendered 1 frame");

  const art = await fetch(`${base}/artifacts/run_a/out.mp4`);
  assert.equal(art.status, 200);
  assert.equal(art.headers.get("content-type"), "video/mp4");
  const bytes = Buffer.from(await art.arrayBuffer());
  assert.deepEqual([...bytes], [0, 0, 0, 0x18, 0x66, 0x74, 0x79, 0x70]);
});

test("a second run does not overwrite the first", async () => {
  await fetch(`${base}/v1/chat/completions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ messages: [{ role: "user", content: "again" }], session_id: "run_b" }),
  });
  const first = await fetch(`${base}/artifacts/run_a/out.mp4`);
  const second = await fetch(`${base}/artifacts/run_b/out.mp4`);
  assert.equal(first.status, 200);
  assert.equal(second.status, 200);
});

test("the artifact route refuses traversal and unknown names", async () => {
  assert.equal((await fetch(`${base}/artifacts/run_a/../out.mp4`)).status, 404);
  assert.equal((await fetch(`${base}/artifacts/run_a/index.html`)).status, 404);
  assert.equal((await fetch(`${base}/artifacts/run_a/out.txt`)).status, 404);
  assert.equal((await fetch(`${base}/artifacts/nope/out.mp4`)).status, 404);
});
