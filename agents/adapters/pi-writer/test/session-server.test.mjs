// End-to-end test of the writer session server's turn, artifact and proxy contract,
// with a stub `pi` on PATH so no model and no network are needed.

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, mkdir, readFile, writeFile, chmod, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const serverPath = fileURLToPath(new URL("../session-server.mjs", import.meta.url));
const promptsDir = fileURLToPath(new URL("../prompts", import.meta.url));
const port = 20000 + Math.floor(Math.random() * 2000);
const base = `http://127.0.0.1:${port}`;

let dir;
let child;
let workspace;
let serverLog = "";

// A stand-in for Pi: it writes the two files the real agent writes, in its cwd (the
// per-run directory), and reports on stdout. It records the prompt it was handed, so
// the test can assert the author/correct instruction the server chose, and the proxy
// it was given, because the proxy is enforcement rather than instruction.
const STUB_PI = `#!/usr/bin/env node
const fs = require("node:fs");
const prompt = process.argv.at(-1) || "";
fs.writeFileSync("prompt.txt", prompt);
fs.writeFileSync("env.log", process.env.HTTPS_PROXY || "none");
// A quoted manifest, as the real turn would write it after reading the page.
fs.writeFileSync("article.md", "# Probe\\n\\n## Install\\n\\n" + "\\u0060\\u0060\\u0060bash\\nhelm upgrade --install probe ./chart\\n\\u0060\\u0060\\u0060\\n");
fs.writeFileSync("sources.json", JSON.stringify({ sources: [
  { block: "helm upgrade --install probe ./chart", url: "http://127.0.0.1:9/page" },
  { block: "helm upgrade --install probe ./chart", url: "https://source.invalid/page" }
] }));
if (prompt.includes("NO_LEDGER")) fs.rmSync("sources.json", { force: true });
if (prompt.includes("BROKEN_LEDGER")) fs.writeFileSync("sources.json", "{not json");
// A tool that connects to a host off the list must be refused by the proxy itself, so
// the turn records the reply it got.
if (prompt.includes("PROXY_PROBE")) {
  const net = require("node:net");
  const proxy = new URL(process.env.HTTPS_PROXY || "http://127.0.0.1:1");
  // A declared host is not a licence for a private address: the probe names one to prove
  // the proxy applies the same address policy as the server's own ledger fetch.
  const target = prompt.includes("PROXY_PROBE_PRIVATE")
    ? "127.0.0.1:443"
    : prompt.includes("PROXY_PROBE_PORT")
      ? "github.com:80"
      : "blocked.example:443";
  const socket = net.connect(Number(proxy.port), proxy.hostname, () => {
    socket.write("CONNECT " + target + " HTTP/1.1\\r\\nHost: " + target + "\\r\\n\\r\\n");
  });
  socket.on("data", (d) => {
    fs.writeFileSync("proxy.log", String(d).split("\\n")[0]);
    socket.destroy();
    process.exit(0);
  });
  socket.on("error", (e) => {
    fs.writeFileSync("proxy.log", "ERROR " + e.message);
    process.exit(4);
  });
}
process.stdout.write("drafted the probe article");
`;

async function waitForHealth(timeoutMs = 10000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`${base}/healthz`);
      if (res.ok) return;
    } catch {
      // not listening yet
    }
    await new Promise((r) => setTimeout(r, 50));
  }
  throw new Error(`session server did not become healthy: ${serverLog}`);
}

before(async () => {
  dir = await mkdtemp(join(tmpdir(), "pi-writer-test-"));
  const bin = join(dir, "bin");
  workspace = join(dir, "workspace");
  const home = join(dir, "home");
  await mkdir(bin, { recursive: true });
  await mkdir(home, { recursive: true });
  const stub = join(bin, "pi");
  await writeFile(stub, STUB_PI);
  await chmod(stub, 0o755);
  child = spawn(process.execPath, [serverPath], {
    env: {
      ...process.env,
      HOME: home,
      PATH: `${bin}:${process.env.PATH}`,
      SYMPOZIUM_WORKSPACE: workspace,
      SYMPOZIUM_SESSION_PORT: String(port),
      PI_WRITER_PROMPT_DIR: promptsDir,
      SYMPOZIUM_HARNESS_CONTRACT_VERSION: "v1alpha2",
      MODEL_NAME: "stub",
      MODEL_BASE_URL: "http://127.0.0.1:9/v1",
      OPENAI_API_KEY: "test-key",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  child.stdout.on("data", (chunk) => {
    serverLog += chunk.toString();
  });
  child.stderr.on("data", (chunk) => {
    serverLog += chunk.toString();
  });
  await waitForHealth();
});

after(async () => {
  child?.kill("SIGTERM");
  await rm(dir, { recursive: true, force: true });
});

const turn = (body) =>
  fetch(`${base}/v1/chat/completions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });

test("a turn drafts both files and returns the ledger the server verified", async () => {
  const res = await turn({
    messages: [{ role: "user", content: "write about installing the release" }],
    session_id: "article-1",
    source_hosts: ["github.com"],
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.article.name, "article.md");
  assert.equal(body.article.ledger, "sources.json");
  // Neither entry survives: one is http, the other names a host the caller did not
  // declare. The server is the authority on both, and it rewrites the file rather
  // than reporting.
  assert.equal(body.article.sources, 0);
  assert.equal(body.article.quoted, 0);
  assert.equal(body.article.dropped.length, 2);
  assert.ok(body.article.dropped.some((entry) => /not https/.test(entry.reason)), JSON.stringify(body.article.dropped));
  assert.ok(
    body.article.dropped.some((entry) => /not a declared source host/.test(entry.reason)),
    JSON.stringify(body.article.dropped)
  );

  const article = await fetch(`${base}/artifacts/article-1/article.md`);
  assert.equal(article.status, 200);
  assert.equal(article.headers.get("content-type"), "text/markdown; charset=utf-8");
  const written = await article.text();
  assert.ok(written.startsWith("# Probe"), written);

  const ledger = await fetch(`${base}/artifacts/article-1/sources.json`);
  assert.equal(ledger.status, 200);
  assert.equal(ledger.headers.get("content-type"), "application/json; charset=utf-8");
  assert.deepEqual(JSON.parse(await ledger.text()), { sources: [] });
});

test("the artifact route serves only the two names the turn writes", async () => {
  for (const name of ["prompt.txt", "env.log", "..%2Fsources.json"]) {
    const res = await fetch(`${base}/artifacts/article-1/${name}`);
    assert.equal(res.status, 404, `${name} was served`);
  }
  assert.equal((await fetch(`${base}/artifacts/..%2F..%2Fetc/article.md`)).status, 404);
});

test("a turn that writes no ledger reports the error instead of a silent pass", async () => {
  const res = await turn({
    messages: [{ role: "user", content: "NO_LEDGER write about the release" }],
    session_id: "article-2",
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.article.sources, 0);
  assert.match(body.article.error, /wrote no sources\.json/);

  const broken = await turn({
    messages: [{ role: "user", content: "BROKEN_LEDGER write about the release" }],
    session_id: "article-3",
  });
  assert.equal(broken.status, 200);
  assert.match((await broken.json()).article.error, /not valid JSON/);
});

test("a retry is a correction of the directory, not a fresh authoring turn", async () => {
  await turn({
    messages: [{ role: "user", content: "tighten the install section" }],
    session_id: "article-1",
    attempt: 2,
  });
  const prompt = await readFile(join(workspace, "runs", "article-1", "prompt.txt"), "utf8");
  assert.ok(prompt.includes("in place"), "the correction instruction is missing");
  assert.ok(prompt.includes("Working directory:"), prompt);
});

test("the turn's tools see the proxy, and it is unset when the turn returns", async () => {
  await turn({
    messages: [{ role: "user", content: "write about the release" }],
    session_id: "article-4",
  });
  const env = await readFile(join(workspace, "runs", "article-4", "env.log"), "utf8");
  assert.match(env, /^http:\/\/127\.0\.0\.1:8081$/);
});

test("a host off the list is refused through the proxy and the refusal is logged", async () => {
  const res = await turn({
    messages: [{ role: "user", content: "PROXY_PROBE install the release" }],
    session_id: "article-proxy",
    source_hosts: ["github.com"],
  });
  assert.equal(res.status, 200);
  const reply = await readFile(join(workspace, "runs", "article-proxy", "proxy.log"), "utf8");
  assert.match(reply, /403/, `the proxy answered ${reply}`);
  const deadline = Date.now() + 2000;
  while (Date.now() < deadline && !/refused blocked\.example/.test(serverLog)) {
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  assert.match(
    serverLog,
    /refused blocked\.example through the source proxy: host blocked\.example is not a declared source host/
  );
});

test("a declared private host is refused through the proxy too", async () => {
  // The spec's scenario is "no bytes from that host reach the session", so declaring
  // 127.0.0.1 in source_hosts must not turn the proxy into a loopback hole.
  const res = await turn({
    messages: [{ role: "user", content: "PROXY_PROBE_PRIVATE install the release" }],
    session_id: "article-proxy-private",
    source_hosts: ["127.0.0.1"],
  });
  assert.equal(res.status, 200);
  const reply = await readFile(join(workspace, "runs", "article-proxy-private", "proxy.log"), "utf8");
  assert.match(reply, /403/, `the proxy answered ${reply}`);
  const deadline = Date.now() + 2000;
  while (Date.now() < deadline && !/refused 127\.0\.0\.1/.test(serverLog)) {
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  assert.match(
    serverLog,
    /refused 127\.0\.0\.1 through the source proxy: host 127\.0\.0\.1 is private or loopback/
  );
});

test("the proxy refuses a port other than 443", async () => {
  // The instruction says https on 443, and the server's own ledger fetch enforces it. A
  // proxy that forwarded plain http or another port would be a wider gate than the check
  // the ledger is verified against.
  const res = await turn({
    messages: [{ role: "user", content: "PROXY_PROBE_PORT install the release" }],
    session_id: "article-proxy-port",
    source_hosts: ["github.com"],
  });
  assert.equal(res.status, 200);
  const reply = await readFile(join(workspace, "runs", "article-proxy-port", "proxy.log"), "utf8");
  assert.match(reply, /403/, `the proxy answered ${reply}`);
  const deadline = Date.now() + 2000;
  while (Date.now() < deadline && !/refused github\.com/.test(serverLog)) {
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  assert.match(
    serverLog,
    /refused github\.com through the source proxy: port 80 is not 443/
  );
});

test("a streamed turn frames the answer and still ends with the done marker", async () => {
  const res = await turn({
    messages: [{ role: "user", content: "write about the release" }],
    session_id: "article-stream",
    stream: true,
  });
  assert.equal(res.status, 200);
  assert.match(res.headers.get("content-type"), /text\/event-stream/);
  const text = await res.text();
  assert.match(text, /"delta":\{"content":"drafted the probe article"\}/);
  assert.ok(text.trimEnd().endsWith("data: [DONE]"));
});
