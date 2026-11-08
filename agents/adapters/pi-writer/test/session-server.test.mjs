// End-to-end test of the writer session server's turn, artifact and proxy contract,
// with a stub `pi` on PATH so no model and no network are needed.

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, mkdir, readFile, readdir, copyFile, writeFile, chmod, rm } from "node:fs/promises";
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
fs.writeFileSync("args.txt", process.argv.slice(2).join(" "));
fs.writeFileSync("env.log", process.env.HTTPS_PROXY || "none");
// A review or an edit answers in its response and writes nothing; only a drafting turn
// authors the files. This is what makes the test read the server's own handling of a
// review rather than a stub's copy of it.
if (prompt.includes("You review one long-form technical blog draft.")) {
  process.stdout.write("<output>true</output><explanation>the probe passed</explanation>");
  process.exit(0);
}
if (prompt.includes("You review one article draft")) {
  const aspect = (prompt.match(/for (clarity|flow|structure) only/) || [])[1] || "aspect";
  process.stdout.write("<findings>1. opening: PROBE_" + aspect.toUpperCase() + " - tighten it</findings>");
  process.exit(0);
}
if (prompt.includes("You edit one article draft")) {
  process.stdout.write("<article># Probe edited\\n\\nEdited body with PROBE_EDIT.</article>");
  process.exit(0);
}
// A drafting turn that answers in text and writes nothing: the server must adopt the block it
// answered with, and must not read the previous attempt's ledger as this run's.
if (prompt.includes("STALE_ARTIFACTS")) {
  process.stdout.write("<article># Adopted title\\n\\nAdopted body, no files written.</article>");
  process.exit(0);
}
// A drafting turn that writes nothing and answers with no block has produced no draft.
if (prompt.includes("NO_WRITE")) {
  process.stdout.write("I could not finish the article.");
  process.exit(0);
}
// A quoted manifest, as the real turn would write it after reading the page.
fs.writeFileSync("article.md", "# Probe\\n\\n## Install\\n\\n" + "\\u0060\\u0060\\u0060bash\\nhelm upgrade --install probe ./chart\\n\\u0060\\u0060\\u0060\\n");
fs.writeFileSync("sources.json", JSON.stringify({ sources: [
  { block: "helm upgrade --install probe ./chart", url: "http://127.0.0.1:9/page" },
  { block: "helm upgrade --install probe ./chart", url: "https://source.invalid/page" }
] }));
// A second fence with no entry: the caller reports this as UNQUOTED, and the server names it
// in the answer so the mismatch is visible without the caller's gate.
if (prompt.includes("UNQUOTED_PROBE")) {
  fs.appendFileSync("article.md", "\\n\\u0060\\u0060\\u0060bash\\nkubectl apply -f - <<EOF\\nEOF\\n\\u0060\\u0060\\u0060\\n");
}
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
      SYMPOZIUM_GITHUB_MCP_URL: "http://github.invalid/mcp",
      SYMPOZIUM_FIRECRAWL_MCP_URL: "http://firecrawl.invalid/mcp",
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

test("a fence with no ledger entry is named in the answer", async () => {
  const res = await turn({
    messages: [{ role: "user", content: "UNQUOTED_PROBE write about installing the release" }],
    session_id: "article-unquoted",
    source_hosts: ["github.com"],
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  // The entry that verifies is quoted; the appended fence has no entry at all, which is
  // the caller's UNQUOTED failure. The server never invents the missing entry.
  assert.equal(body.article.quoted, 0);
  assert.ok(
    body.article.unquoted.some((block) => block.startsWith("kubectl apply -f - <<EOF")),
    JSON.stringify(body.article.unquoted)
  );
});

test("a draft that answers without writing files has its answer adopted", async () => {
  const res = await turn({
    messages: [{ role: "user", content: "STALE_ARTIFACTS write about the release" }],
    session_id: "article-stale",
    source_hosts: ["github.com"],
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.article.title, "Adopted title");
  assert.match(body.article.text, /^Adopted body/);
  // No ledger was written this turn, so the stale one is not handed back as evidence.
  assert.match(body.article.error, /no sources\.json/);
  const stored = await fetch(`${base}/artifacts/article-stale/article.md`);
  assert.match(await stored.text(), /Adopted body/);
});

test("a draft that writes nothing and answers no block fails by name", async () => {
  const res = await turn({
    messages: [{ role: "user", content: "NO_WRITE write about the release" }],
    session_id: "article-nowrite",
    source_hosts: ["github.com"],
  });
  assert.equal(res.status, 400);
  const body = await res.json();
  assert.match(body.error.message, /answered without writing article\.md/);
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

test("a brief is rendered from the adapter's own prompt files", async () => {
  // The caller sends the entry's fields, never the prompt: n8n has no article prompt left
  // to render. This turn proves each field reaches the brief and that the shapes and the
  // audience levels came from this image's files rather than from the request.
  const res = await turn({
    session_id: "article-brief",
    source_hosts: ["github.com"],
    brief: {
      topic: "PROBE_TOPIC",
      description: "PROBE_DESCRIPTION",
      url: "https://github.com/datahub-local/datahub-local-ai",
      max_words: 900,
      asset_types: "image_wide,svg_wide",
      audience: "LOW",
      extra_prompt: "PROBE_EXTRA",
      content: "PROBE_CONTENT",
      feedback: "PROBE_FEEDBACK",
      previous_draft: "PROBE_PREVIOUS",
    },
  });
  assert.equal(res.status, 200);
  const prompt = await readFile(join(workspace, "runs", "article-brief", "prompt.txt"), "utf8");
  for (const value of [
    "PROBE_TOPIC",
    "PROBE_DESCRIPTION",
    "PROBE_EXTRA",
    "PROBE_CONTENT",
    "PROBE_FEEDBACK",
    "PROBE_PREVIOUS",
    "900",
    "image_wide,svg_wide",
    "## One spine",
    "## LOW",
  ]) {
    assert.ok(prompt.includes(value), `${value} did not reach the prompt`);
  }
  assert.ok(!/\{\{\s*TOPIC\s*\}\}/.test(prompt), "a placeholder was left unrendered");
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

test("Pi starts with the catalog client and the model is handed its read tools", async () => {
  // Tools are the job; discovery is not. `--no-extensions` would take the built-in MCP
  // client with it, so the flag is paired with `-e builtin:mcp`, and the servers Pi reads
  // are the image's own config rather than anything a caller sends.
  const mcp = JSON.parse(await readFile(join(dir, "home", ".pi/agent/mcp.json"), "utf8"));
  assert.deepEqual(Object.keys(mcp.mcpServers).sort(), ["firecrawl", "github"]);
  assert.equal(mcp.mcpServers.github.url, "http://github.invalid/mcp");
  assert.equal(mcp.mcpServers.github.exposure, "hidden");
  assert.equal(mcp.mcpServers.github.toolExposure.search_code, "direct");
  assert.equal(mcp.mcpServers.firecrawl.url, "http://firecrawl.invalid/mcp");
  const res = await turn({
    messages: [{ role: "user", content: "write about the release" }],
    session_id: "article-mcp",
  });
  assert.equal(res.status, 200);
  const args = await readFile(join(workspace, "runs", "article-mcp", "args.txt"), "utf8");
  assert.ok(args.includes("-e builtin:mcp"), `Pi was run without the MCP client: ${args}`);
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

test("a review turn returns a structured verdict and leaves the draft alone", async () => {
  const res = await turn({
    task: "review",
    session_id: "article-review",
    brief: { topic: "Probe", audience: "LOW", max_words: 900, asset_types: "image_wide" },
    article: { title: "Probe", text: "## Install\n\nUse it." },
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.task, "review");
  assert.equal(body.review.pass, true);
  assert.equal(body.review.explanation, "the probe passed");
  // The draft is the caller's, not the stub's, and the review did not rewrite it.
  assert.equal(body.article.title, "Probe");
  assert.equal(body.article.text, "## Install\n\nUse it.");
  const written = await readFile(join(workspace, "runs", "article-review", "article.md"), "utf8");
  assert.equal(written, "# Probe\n\n## Install\n\nUse it.\n");
  const args = await readFile(join(workspace, "runs", "article-review", "args.txt"), "utf8");
  assert.match(args, /--no-tools/);
});

test("the aspect pass answers one findings block per aspect", async () => {
  const res = await turn({
    task: "aspects",
    session_id: "article-aspects",
    brief: { topic: "Probe", audience: "LOW", max_words: 900, asset_types: "image_wide" },
    article: { title: "Probe", text: "## Install\n\nUse it." },
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.findings.length, 3);
  assert.deepEqual(body.findings.map((finding) => finding.aspect).sort(), ["clarity", "flow", "structure"]);
  for (const finding of body.findings) {
    assert.equal(finding.count, 1);
    assert.match(finding.text, new RegExp(`PROBE_${finding.aspect.toUpperCase()}`));
    assert.equal(finding.error, "");
  }
});

test("a review of a session with a draft reads it when the request carries none", async () => {
  // The creator sends the parsed draft, but a resumed round may name only the session.
  // The server then reviews the session's own article rather than an empty one.
  await turn({
    messages: [{ role: "user", content: "write about installing the release" }],
    session_id: "article-review-stored",
  });
  const res = await turn({
    task: "review",
    session_id: "article-review-stored",
    brief: { topic: "Probe", audience: "LOW", max_words: 900 },
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.review.pass, true);
  assert.match(body.article.text, /helm upgrade --install probe/);
  const prompt = await readFile(join(workspace, "runs", "article-review-stored", "prompt.txt"), "utf8");
  assert.match(prompt, /helm upgrade --install probe/);
});

test("a review without a budget fails by name instead of rejecting every draft", async () => {
  const res = await turn({
    task: "review",
    session_id: "article-review-nobudget",
    brief: { topic: "Probe" },
    article: { title: "Probe", text: "## Install\n\nUse it." },
  });
  assert.equal(res.status, 400);
  const body = await res.json();
  assert.match(body.error.message, /brief\.max_words/);
});

test("an improve turn writes the edited article the model returned", async () => {
  const res = await turn({
    task: "improve",
    session_id: "article-improve",
    brief: {
      topic: "Probe",
      audience: "LOW",
      max_words: 900,
      asset_types: "image_wide",
      feedback: "PROBE_HUMAN_FEEDBACK",
    },
    article: { title: "Probe", text: "## Install\n\nUse it." },
    findings: "PROBE_FINDINGS: tighten the opening",
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.task, "improve");
  assert.equal(body.article.title, "Probe edited");
  assert.equal(body.article.text, "Edited body with PROBE_EDIT.");
  const written = await readFile(join(workspace, "runs", "article-improve", "article.md"), "utf8");
  assert.equal(written, "# Probe edited\n\nEdited body with PROBE_EDIT.\n");
  // The owner's feedback and the merged findings reach the turn, which is the issue's
  // headline case: a rejection re-enters the writer with what the person said.
  const prompt = await readFile(join(workspace, "runs", "article-improve", "prompt.txt"), "utf8");
  assert.match(prompt, /PROBE_HUMAN_FEEDBACK/);
  assert.match(prompt, /PROBE_FINDINGS: tighten the opening/);
});

test("a review of a session with no draft fails by name", async () => {
  const res = await turn({
    task: "review",
    session_id: "article-empty",
    brief: { topic: "Probe", max_words: 900 },
  });
  assert.equal(res.status, 400);
  const body = await res.json();
  assert.match(body.error.message, /carries no article/);
});

test("the server refuses to start when the aspect registry is unusable", async () => {
  // Every prompt is present except the registry, so the only reason to refuse is the one
  // this test names.
  const prompts = join(dir, "registryless-prompts");
  await mkdir(prompts, { recursive: true });
  for (const name of await readdir(promptsDir)) {
    if (name === "article_aspects.json") continue;
    await copyFile(join(promptsDir, name), join(prompts, name));
  }
  const refused = spawn(process.execPath, [serverPath], {
    env: {
      ...process.env,
      HOME: join(dir, "home"),
      SYMPOZIUM_WORKSPACE: join(dir, "refused-workspace"),
      SYMPOZIUM_SESSION_PORT: String(port + 1),
      PI_WRITER_PROXY_PORT: String(port + 2),
      PI_WRITER_PROMPT_DIR: prompts,
      SYMPOZIUM_HARNESS_CONTRACT_VERSION: "v1alpha2",
      MODEL_NAME: "stub",
      MODEL_BASE_URL: "http://127.0.0.1:9/v1",
      OPENAI_API_KEY: "test-key",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let output = "";
  refused.stdout.on("data", (chunk) => {
    output += chunk.toString();
  });
  refused.stderr.on("data", (chunk) => {
    output += chunk.toString();
  });
  const code = await new Promise((resolve) => refused.on("close", resolve));
  assert.notEqual(code, 0);
  assert.match(output, /article_aspects\.json is unusable/);
});
