// End-to-end test of the session server's authoring + artifact contract, with a
// stub `pi` on PATH so no model, engine or ffmpeg is needed. Exercises the MP4
// path (no transcode); the format helpers are covered by session-lib.test.mjs.

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { mkdtemp, mkdir, readFile, writeFile, chmod, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { DEFAULT_GATEWAY_STREAM_TIMEOUT_MS, DEFAULT_RETRY } from "../session-lib.mjs";

const serverPath = fileURLToPath(new URL("../session-server.mjs", import.meta.url));
const port = 18000 + Math.floor(Math.random() * 2000);
const base = `http://127.0.0.1:${port}`;
const gatewayPort = port + 1;
const gatewayBase = `http://127.0.0.1:${gatewayPort}/v1`;
// A still of a clip needs ffmpeg, which CI does not install: the tests that need one say so
// and skip rather than fail for the environment's sake.
const hasFfmpeg = spawnSync("ffmpeg", ["-version"], { stdio: "ignore" }).status === 0;

let dir;
let child;
let workspace;
let serverLog = "";

// A stand-in for Pi: it writes the two files the real agent writes, in its cwd
// (the per-run directory), and reports on stdout. It also records the prompt it was
// handed, so the test can assert the author/edit instruction the server chose.
const STUB_PI = `#!/usr/bin/env node
const fs = require("node:fs");
const { spawnSync } = require("node:child_process");
fs.writeFileSync("index.html", "<div>stub</div>");
fs.writeFileSync("out.html", "<html>stub deck</html>");
fs.writeFileSync("out.mp4", Buffer.from([0, 0, 0, 0x18, 0x66, 0x74, 0x79, 0x70]));
fs.writeFileSync("out.png", Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));
fs.writeFileSync("review-1.png", Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));
fs.writeFileSync("prompt.txt", process.argv.at(-1) || "");
fs.writeFileSync("args.log", process.argv.slice(2).join("\\n"));
fs.appendFileSync("prompts.log", (process.argv.at(-1) || "") + "\\n---TURN---\\n");
// A format change needs a render ffmpeg can read; the eight-byte header above is only
// enough for the paths that must NOT transcode. The test that asks for png says so.
if ((process.argv.at(-1) || "").includes("VALID_MP4")) {
  const made = spawnSync("ffmpeg", ["-loglevel", "error", "-f", "lavfi", "-i",
    "color=c=black:s=64x64:d=1:r=30", "-pix_fmt", "yuv420p", "-y", "out.mp4"]);
  if (made.status !== 0) process.exit(3);
}
// The failure path: Pi reports a stalled model call as one word of its own, and
// names no endpoint unless the server adds it.
if ((process.argv.at(-1) || "").includes("FAIL_PROBE")) {
  process.stderr.write("noise before the reason\\nstream terminated by peer");
  process.exit(9);
}
process.stdout.write("rendered 1 frame");
`;

// A stand-in for the gateway's chat endpoint: it answers the critic's call with the verdict
// the test asked for, and counts the calls so a bound can be asserted.
let gatewayCalls = 0;
let gatewayAnswer = () => "{\"verdict\": \"ok\", \"findings\": []}";
let gateway;

async function startGateway(port) {
  const http = await import("node:http");
  gateway = http.createServer((req, res) => {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      gatewayCalls += 1;
      const answer = gatewayAnswer(body);
      if (answer === null) {
        res.writeHead(500, { "content-type": "application/json" }).end("{}");
        return;
      }
      const payload = JSON.stringify({ choices: [{ message: { role: "assistant", content: answer } }] });
      res.writeHead(200, { "content-type": "application/json" }).end(payload);
    });
  });
  await new Promise((r) => gateway.listen(port, "127.0.0.1", r));
}

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
  workspace = join(dir, "workspace");
  const bin = join(dir, "bin");
  const vendor = join(dir, "vendor");
  await mkdir(home, { recursive: true });
  await mkdir(workspace, { recursive: true });
  await mkdir(bin, { recursive: true });
  await mkdir(vendor, { recursive: true });
  await writeFile(join(vendor, "gsap.min.js"), "/* staged gsap */");
  const pi = join(bin, "pi");
  await writeFile(pi, STUB_PI);
  await chmod(pi, 0o755);
  child = spawn(process.execPath, [serverPath], {
    env: {
      ...process.env,
      PATH: `${bin}:${process.env.PATH}`,
      HOME: home,
      SYMPOZIUM_WORKSPACE: workspace,
      SYMPOZIUM_VENDOR_DIR: vendor,
      SYMPOZIUM_SESSION_PORT: String(port),
      SYMPOZIUM_HARNESS_CONTRACT_VERSION: "v1alpha2",
      MODEL_NAME: "stub",
      MODEL_BASE_URL: gatewayBase,
      OPENAI_API_KEY: "stub",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  child.stderr.on("data", (chunk) => {
    serverLog += chunk.toString();
  });
  await startGateway(gatewayPort);
  await waitForHealth();
});

after(async () => {
  gateway?.close();
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

test("a turn reports the container it served and why nothing was conformed", async () => {
  const res = await fetch(`${base}/v1/chat/completions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      messages: [{ role: "user", content: "make a card" }],
      session_id: "run_note",
      format: "mp4",
      fps: 30,
      width: 1280,
      height: 720,
      frames: 360,
      durationSeconds: 12,
    }),
  });
  assert.equal(res.status, 200, "a container that cannot be read never fails the turn");
  const body = await res.json();
  // The stub writes eight bytes of ftyp rather than a clip, and CI installs no ffmpeg:
  // either way the render's container cannot be read, so the note says so and the caller
  // still receives the bytes the engine produced.
  assert.equal(body.conformance.frame, "1280x720");
  assert.equal(body.conformance.fit, "unknown");
  assert.ok(body.conformance.reason, "an unreadable render says why it is unknown");
  assert.equal(body.conformance.durationSeconds, 12);
  assert.equal(body.conformance.short, false, "nothing is claimed about a length nobody read");
  const art = await fetch(`${base}/artifacts/run_note/out.mp4`);
  assert.equal(art.status, 200);
});

test("the vendored GSAP is staged beside the composition", async () => {
  // `<script src="gsap.min.js">` resolves as a sibling; an absolute /opt path 404s.
  const staged = await readFile(join(dir, "workspace", "runs", "run_a", "gsap.min.js"), "utf8");
  assert.equal(staged, "/* staged gsap */");
});

test("the session writes Pi's retry and idle-timeout settings", async () => {
  // Without this file Pi runs on the vendor's defaults (300s idle timeout, three
  // retries) because `--session-dir` and the agent directory are the only config Pi
  // reads; the tuned window is what lets a stalled model call be retried.
  const settings = JSON.parse(await readFile(join(dir, "home", ".pi/agent/settings.json"), "utf8"));
  assert.equal(settings.httpIdleTimeoutMs, DEFAULT_RETRY.idleTimeoutMs);
  assert.ok(
    settings.httpIdleTimeoutMs > DEFAULT_GATEWAY_STREAM_TIMEOUT_MS,
    "the composer must outlast the gateway's streaming timeout"
  );
  assert.deepEqual(settings.retry, {
    enabled: true,
    maxRetries: DEFAULT_RETRY.maxRetries,
    baseDelayMs: DEFAULT_RETRY.baseDelayMs,
    maxAgentDelayMs: DEFAULT_RETRY.maxAgentDelayMs,
  });
});

test("a deck turn serves the deck and its paired video", async () => {
  const res = await fetch(`${base}/v1/chat/completions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ messages: [{ role: "user", content: "make a deck" }], session_id: "run_deck", format: "html" }),
  });
  assert.equal(res.status, 200);
  const deck = await fetch(`${base}/artifacts/run_deck/out.html`);
  assert.equal(deck.status, 200);
  assert.equal(deck.headers.get("content-type"), "text/html");
  assert.equal(await deck.text(), "<html>stub deck</html>");
  const video = await fetch(`${base}/artifacts/run_deck/out.mp4`);
  assert.equal(video.status, 200);
  assert.equal(video.headers.get("content-type"), "video/mp4");
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

test("Pi runs with tools but without skill or extension discovery", async () => {
  // Tools are the job. Discovery is not: no skills or extensions are installed, and one
  // found in the run directory or HOME would be a second, unversioned contract beside the
  // engine's own docs. This asserts the flags rather than trusting the arg list by eye.
  const res = await fetch(`${base}/v1/chat/completions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ messages: [{ role: "user", content: "make a card" }], session_id: "run_args" }),
  });
  assert.equal(res.status, 200);
  const args = await readFile(join(workspace, "runs", "run_args", "args.log"), "utf8");
  for (const flag of ["--no-prompt-templates", "--no-skills", "--no-extensions"]) {
    assert.ok(args.includes(flag), `Pi was not run with ${flag}`);
  }
  assert.ok(!args.includes("--no-tools"), "Pi was run without tools; authoring needs them");
});

test("the second turn in a session is an edit, not a fresh authoring", async () => {
  // The server follows the directory, not the caller: after turn 1 wrote
  // index.html, turn 2 must be told to edit it in place.
  const turn = (content) =>
    fetch(`${base}/v1/chat/completions`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ messages: [{ role: "user", content }], session_id: "run_iter" }),
    });
  assert.equal((await turn("make a card")).status, 200);
  const firstPrompt = await readFile(join(dir, "workspace", "runs", "run_iter", "prompt.txt"), "utf8");
  assert.ok(firstPrompt.includes("Write the composition to `index.html`"), "the first turn authors");
  assert.ok(!firstPrompt.includes("earlier turn"), "the first turn claims no prior work");

  assert.equal((await turn("make the headline bigger")).status, 200);
  const secondPrompt = await readFile(join(dir, "workspace", "runs", "run_iter", "prompt.txt"), "utf8");
  assert.ok(secondPrompt.includes("earlier turn"), "the second turn is an edit");
  assert.ok(secondPrompt.includes("in place"), "the edit keeps the rest");
  assert.ok(secondPrompt.includes("make the headline bigger"), "the change reaches the composer");
  // The turn is still served from the same directory and the artifact is refreshed.
  assert.equal((await fetch(`${base}/artifacts/run_iter/out.mp4`)).status, 200);
});

test("the artifact route refuses traversal and unknown names", async () => {
  assert.equal((await fetch(`${base}/artifacts/run_a/../out.mp4`)).status, 404);
  assert.equal((await fetch(`${base}/artifacts/run_a/index.html`)).status, 404);
  assert.equal((await fetch(`${base}/artifacts/run_a/out.txt`)).status, 404);
  assert.equal((await fetch(`${base}/artifacts/nope/out.mp4`)).status, 404);
});

test("a failed turn names the model endpoint and Pi's own reason", async () => {
  // Pi's account of an exhausted retry window is its stream plumbing's word, so
  // the endpoint has to come from the server: a caller reading the run record
  // must be able to tell a stalled model call from a bad brief.
  const res = await fetch(`${base}/v1/chat/completions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ messages: [{ role: "user", content: "FAIL_PROBE" }], session_id: "run_fail" }),
  });
  assert.equal(res.status, 400);
  const { error } = await res.json();
  assert.match(error.message, /Pi exited 9/);
  assert.ok(error.message.includes(gatewayBase), `the endpoint is named: ${error.message}`);
  assert.ok(error.message.includes("stream terminated by peer"), `the reason is carried: ${error.message}`);
});


test("a pre-turn failure is logged, not only answered", async () => {
  // The failure injection that exercised the studio's fallback was a regular file where the
  // run directory belongs, and this is that shape: the turn dies before Pi starts, so Pi's
  // output says nothing and the 400 body is the only account -- which the caller may drop.
  await mkdir(join(workspace, "runs"), { recursive: true });
  await writeFile(join(workspace, "runs", "run_blocked"), "");
  const res = await fetch(`${base}/v1/chat/completions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ messages: [{ role: "user", content: "make a card" }], session_id: "run_blocked" }),
  });
  assert.equal(res.status, 400);
  const { error } = await res.json();
  assert.match(error.message, /EEXIST/);
  const deadline = Date.now() + 2000;
  while (Date.now() < deadline && !/turn failed: .*EEXIST/.test(serverLog)) {
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  assert.match(serverLog, /sympozium pi render session: turn failed: .*EEXIST/, "the pod log names the reason");
});


test("a turn reports the stills a critic can look at", async () => {
  // The contract is the field: which stills exist depends on the tools the pod has (a
  // browser for a document, ffmpeg for a clip), and the studio fetches the names it is given.
  const res = await fetch(`${base}/v1/chat/completions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ messages: [{ role: "user", content: "make a card" }], session_id: "run_stills", format: "mp4" }),
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.ok(Array.isArray(body.stills), "the stills are reported");
});

test("the artifact route serves the stills beside the artifact, and nothing else", async () => {
  // The stub render leaves a still behind, so this needs neither a browser nor ffmpeg.
  const still = await fetch(`${base}/artifacts/run_a/review-1.png`);
  assert.equal(still.status, 200);
  assert.equal(still.headers.get("content-type"), "image/png");
  assert.equal((await fetch(`${base}/artifacts/run_a/review-1.html`)).status, 404);
  assert.equal((await fetch(`${base}/artifacts/run_a/prompt.txt`)).status, 404);
});

test("a still that was not written this turn is not offered, and the earlier frame is cleared", async () => {
  // The output name is fixed and a session reuses its run directory, so a capture that
  // wrote nothing would leave the previous turn's frame to be served as this turn's still
  // (measured 2026-10-17, run 13785: turns 1 and 2 both offered review-final.jpg at turn
  // 0's mtime). Here the capture cannot produce a file, and the planted one must be gone
  // rather than offered.
  const runDir = join(dir, "workspace", "runs", "run_stale");
  await mkdir(runDir, { recursive: true });
  await writeFile(join(runDir, "review-final.jpg"), "the previous turn's frame");
  const res = await fetch(`${base}/v1/chat/completions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ messages: [{ role: "user", content: "make a card" }], session_id: "run_stale", format: "mp4" }),
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.ok(!body.stills.includes("review-final.jpg"), `a stale frame was offered: ${JSON.stringify(body.stills)}`);
  await assert.rejects(readFile(join(runDir, "review-final.jpg")), "the earlier turn's frame must not stand in");
  assert.equal((await fetch(`${base}/artifacts/run_stale/review-final.jpg`)).status, 404);
});

test("a still png type hands back its artifact as the still", { skip: !hasFfmpeg && "ffmpeg is not installed" }, async () => {
  // A png is the transcode's output, so this is the one case where the render must be a
  // clip ffmpeg can read; VALID_MP4 makes the stub write one. Without ffmpeg there is no
  // png at all, which is what the skip says.
  const res = await fetch(`${base}/v1/chat/completions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ messages: [{ role: "user", content: "make a card VALID_MP4" }], session_id: "run_png", format: "png" }),
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.deepEqual(body.stills, ["out.png"]);
  assert.equal((await fetch(`${base}/artifacts/run_png/out.png`)).status, 200);
});
