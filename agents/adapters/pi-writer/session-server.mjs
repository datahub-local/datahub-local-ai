#!/usr/bin/env node
// The v1alpha2 session endpoint for the Pi writer adapter.
//
// One job: given a brief, fetch the pages it cites and draft `article.md` plus the
// `sources.json` ledger that says where each fenced block was read. A `HarnessSession`
// runs this as a long-lived Deployment, so Pi keeps its state across turns and the
// caller's retry continues the same directory instead of paying for every source again.
//
// Derived from the maintained Pi adapter's session-server.mjs, which is the reference
// for this contract. The deltas are the article lane's own:
//
//   * `--no-tools` is dropped, so Pi can fetch pages and validate a manifest.
//   * `--no-skills` stays: no skill is installed in this image, and one found in the
//     run directory or HOME would compete with the instruction file.
//   * the tools reach the network only through the loopback proxy below, because an
//     allowlist in an instruction is not enforcement.
//   * after the turn the server refetches every ledgered URL and rewrites the ledger
//     with what it saw, so the model is never the authority on whether a source exists.
//
// Everything else — the contract check, the credential checks, the provider config,
// the bounded body and output, serialized turns, SSE framing, client disconnect
// cancellation — is upstream's shape, so the platform sees the behaviour it expects.

import http from "node:http";
import net from "node:net";
import { createReadStream } from "node:fs";
import { mkdir, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { join } from "node:path";

import {
  safeSessionId,
  runDir as resolveRunDir,
  resolveArtifact,
  contentTypeFor,
  expiredRunDirs,
  expiredTranscripts,
  exists,
  DEFAULT_SESSION_WORKSPACE,
  DEFAULT_RETRY,
  agentSettings,
  parseSourceHosts,
  fillSourceHosts,
  parseLedger,
  serialiseLedger,
  revalidateLedger,
  articleTurnInstruction,
  hostAllowed,
  isBlockedHostname,
  ARTICLE_NAME,
  LEDGER_NAME,
} from "./session-lib.mjs";

const port = Number(process.env.SYMPOZIUM_SESSION_PORT || "8080");
const maxBody = 1_048_576;
const maxOutput = 2_000_000;
// The session PVC is mounted at /tmp, so Pi's transcript survives a pod restart.
const sessionDir = "/tmp/pi-sessions";
const promptDir = process.env.PI_WRITER_PROMPT_DIR || "/opt/pi-writer/prompts";
const instructionFile = "writing.md";
const proxyPort = Number(process.env.PI_WRITER_PROXY_PORT || "8081");
// A session container mounts the session PVC at /tmp and does **not** mount
// /workspace (only the Job path does), so the workspace must default under the PVC.
// The caller can still override it.
const workDir = process.env.SYMPOZIUM_WORKSPACE || DEFAULT_SESSION_WORKSPACE;

// Session state is durable, so it has to expire: an abandoned row would otherwise
// keep its run directory and Pi transcript forever, and the PVC would fill. The
// default matches the article sheet's own retention window so a run's row and its
// files expire together. 0 (or a non-number) disables the sweep.
const retentionDays = Number(process.env.PI_WRITER_SESSION_TTL_DAYS ?? "7");
const sweepIntervalMs = 60 * 60 * 1000;

async function listEntries(dir) {
  try {
    const names = await readdir(dir);
    const entries = await Promise.all(
      names.map(async (name) => {
        try {
          const info = await stat(join(dir, name));
          return { name, mtimeMs: info.mtimeMs };
        } catch {
          return null;
        }
      })
    );
    return entries.filter(Boolean);
  } catch {
    return [];
  }
}

// Best-effort: a failed unlink is logged and the turn carries on. `keep` is the
// session in flight, which must never be swept under its own turn.
let lastSweep = Date.now();
async function sweepSessions(keep) {
  if (!Number.isFinite(retentionDays) || retentionDays <= 0) return;
  const cutoffMs = Date.now() - retentionDays * 24 * 60 * 60 * 1000;
  try {
    for (const name of expiredRunDirs(await listEntries(join(workDir, "runs")), { cutoffMs, keep })) {
      await rm(join(workDir, "runs", name), { recursive: true, force: true });
      console.log(`sympozium pi writer session: swept expired session ${name}`);
    }
    for (const name of expiredTranscripts(await listEntries(sessionDir), { cutoffMs, keep })) {
      await rm(join(sessionDir, name), { force: true });
      console.log(`sympozium pi writer session: swept expired transcript ${name}`);
    }
    lastSweep = Date.now();
  } catch (err) {
    console.error(`sympozium pi writer session: sweep failed: ${err?.message ?? err}`);
  }
}

async function sweepIfDue(keep) {
  if (Date.now() - lastSweep < sweepIntervalMs) return;
  await sweepSessions(keep);
}

function fail(message) {
  console.error(`sympozium pi writer session: ${message}`);
  process.exit(1);
}

for (const name of ["MODEL_NAME", "MODEL_BASE_URL", "OPENAI_API_KEY"]) {
  if (!process.env[name]) fail(`${name} is required`);
}
if (process.env.SYMPOZIUM_HARNESS_CONTRACT_VERSION !== "v1alpha2") {
  fail("unsupported harness contract");
}

await mkdir(`${process.env.HOME}/.pi/agent`, { recursive: true });
await mkdir(sessionDir, { recursive: true });
await mkdir(workDir, { recursive: true });

// Reclaim anything already past the window before serving the first turn.
await sweepSessions(undefined);

await writeFile(
  `${process.env.HOME}/.pi/agent/models.json`,
  JSON.stringify({
    providers: {
      sympozium: {
        baseUrl: process.env.MODEL_BASE_URL,
        api: "openai-completions",
        apiKey: "$OPENAI_API_KEY",
        compat: { supportsDeveloperRole: false, supportsReasoningEffort: true },
        models: [
          {
            id: process.env.MODEL_NAME,
            reasoning: true,
            input: ["text"],
            contextWindow: Number(process.env.PI_WRITER_CONTEXT_WINDOW || "262144"),
            // The gateway's reasoning is billed as output and, left on, this model
            // spends every token it is given thinking and returns no content at all.
            // Pi only sends `reasoning_effort` for a non-off thinking level, so the
            // session runs at `minimal`, which this map turns into the `none` the
            // gateway honours. Both numbers are overridable so they can move without
            // a rebuild.
            thinkingLevelMap: { minimal: "none" },
            maxTokens: Number(process.env.PI_WRITER_MAX_TOKENS || "65536"),
          },
        ],
      },
    },
  })
);

// Pi's retry and idle-timeout settings, which Pi reads from the same agent directory.
// Without this file the writer runs on the vendor's defaults, where a stream that
// stalls for longer than the gateway's per-read timeout ends the attempt with no
// window left to retry in.
await writeFile(
  `${process.env.HOME}/.pi/agent/settings.json`,
  JSON.stringify(
    agentSettings({
      idleTimeoutMs: Number(process.env.PI_WRITER_HTTP_IDLE_MS || DEFAULT_RETRY.idleTimeoutMs),
      maxRetries: Number(process.env.PI_WRITER_RETRY_MAX || DEFAULT_RETRY.maxRetries),
      baseDelayMs: Number(process.env.PI_WRITER_RETRY_BASE_MS || DEFAULT_RETRY.baseDelayMs),
      maxAgentDelayMs: Number(process.env.PI_WRITER_RETRY_MAX_DELAY_MS || DEFAULT_RETRY.maxAgentDelayMs),
    })
  )
);

async function writingMethod() {
  const path = join(promptDir, instructionFile);
  try {
    return await readFile(path, "utf8");
  } catch {
    // A missing prompt is loud on the first turn rather than fatal at startup:
    // the session still comes up and the error names the path.
    return `The writing instruction file is missing at ${path}. Report that rather than improvising.`;
  }
}

function readJSON(req) {
  return new Promise((resolve, reject) => {
    let size = 0;
    let body = "";
    req.setEncoding("utf8");
    req.on("data", (chunk) => {
      size += Buffer.byteLength(chunk);
      if (size > maxBody) {
        reject(new Error("request body exceeds 1 MiB"));
        req.destroy();
        return;
      }
      body += chunk;
    });
    req.on("end", () => {
      try {
        resolve(JSON.parse(body));
      } catch {
        reject(new Error("request must be valid JSON"));
      }
    });
    req.on("error", reject);
  });
}

function promptFrom(messages) {
  if (!Array.isArray(messages)) throw new Error("messages is required");
  const users = messages.filter((m) => m && m.role === "user" && typeof m.content === "string");
  if (!users.length) throw new Error("messages must contain a user message");
  return users.at(-1).content;
}

// The failure the caller reads. Pi reports a stalled call in one word from its own
// stream plumbing, so the endpoint is named here: without it an exhausted retry
// window and a bad brief are the same string in the run record.
function piFailure(code, stderr) {
  const detail = stderr
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .at(-1);
  const endpoint = process.env.MODEL_BASE_URL ?? "the model endpoint";
  return new Error(`Pi exited ${code} calling ${endpoint}${detail ? `: ${detail.slice(-800)}` : ""}`);
}

// Pi emits its response on stdout; forwarding each chunk keeps `stream: true`
// genuine rather than a UI replaying a finished answer.
function runPi(prompt, sessionID, onOutput, signal, cwd = workDir) {
  return new Promise((resolve, reject) => {
    const args = [
      "--print",
      "--no-prompt-templates",
      // Tools stay enabled: fetching the cited pages with the proxy's allowlist and
      // rendering a manifest are the job. Discovery is off: no skills or extensions
      // are installed anywhere this pod can see.
      "--no-skills",
      "--no-extensions",
      "--provider",
      "sympozium",
      "--model",
      process.env.MODEL_NAME,
      // The level is only a key into the model's thinkingLevelMap, which turns it
      // into `reasoning_effort: none`; without a non-off level Pi sends no effort
      // and the model reasons until it hits the token cap and returns nothing.
      "--thinking",
      "minimal",
      "--session-id",
      sessionID,
      "--session-dir",
      sessionDir,
      prompt,
    ];
    const child = spawn("pi", args, { cwd, env: process.env, stdio: ["ignore", "pipe", "pipe"] });
    let output = "";
    let stderr = "";
    let exceeded = false;
    let cancelled = false;
    const cancel = () => {
      cancelled = true;
      child.kill("SIGTERM");
    };
    if (signal?.aborted) cancel();
    else signal?.addEventListener("abort", cancel, { once: true });
    const collect = (chunk, outputStream) => {
      if (output.length + stderr.length + chunk.length > maxOutput) {
        exceeded = true;
        child.kill("SIGTERM");
        return;
      }
      if (outputStream) {
        output += chunk;
        onOutput?.(chunk);
      } else {
        stderr += chunk;
      }
    };
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk) => collect(chunk, true));
    child.stderr.on("data", (chunk) => collect(chunk, false));
    child.on("error", reject);
    child.on("close", (code) => {
      signal?.removeEventListener("abort", cancel);
      if (cancelled) return reject(new Error("request cancelled"));
      if (exceeded) return reject(new Error("adapter output exceeded 2 MB"));
      if (code !== 0) return reject(piFailure(code, stderr));
      if (!output.trim()) return reject(new Error("Pi returned an empty response"));
      resolve(output.trim());
    });
  });
}

function writeSSE(res, value) {
  if (!res.writableEnded) res.write(`data: ${JSON.stringify(value)}\n\n`);
}

// One turn at a time: Pi's session file is a shared resource and concurrent turns
// against it interleave. The contract asks adapters to serialize.
let queue = Promise.resolve();

// ---------------------------------------------------------------------------
// The source allowlist proxy.
//
// An instruction is not enforcement, and the CNI here is not FQDN-aware, so the
// allowlist lives in front of the tools: `curl` in a bash tool honours
// `HTTPS_PROXY`, and anything off the list answers 403 here with the host logged.
// The list is per turn because the caller names the hosts; turns are serialized, so
// one module-level value is the turn's.
let articleHosts = null;

function proxyRefusal(host) {
  if (!articleHosts) return "no turn is fetching";
  // The same address policy as the server's own fetch: a caller that declares a private
  // or loopback host does not make it reachable, or the two gates disagree on what may
  // be read.
  if (isBlockedHostname(host)) return `host ${host} is private or loopback`;
  if (!hostAllowed(host, articleHosts)) return `host ${host} is not a declared source host`;
  return null;
}

function splitHostPort(value) {
  const text = String(value || "");
  if (text.startsWith("[")) {
    const end = text.indexOf("]");
    return [text.slice(1, end), text.slice(end + 2)];
  }
  const colon = text.lastIndexOf(":");
  return colon < 0 ? [text, "443"] : [text.slice(0, colon), text.slice(colon + 1)];
}

function refuseThroughProxy(host, reason, res) {
  console.log(`sympozium pi writer session: refused ${host} through the source proxy: ${reason}`);
  if (res && !res.headersSent) {
    res.writeHead(403, { "content-type": "text/plain" }).end(`blocked source host: ${host}`);
  }
}

const proxyServer = http.createServer((req, res) => {
  let target;
  try {
    target = new URL(req.url?.startsWith("http") ? req.url : `http://${req.headers.host}${req.url}`);
  } catch {
    res.writeHead(400).end();
    return;
  }
  const refusal = proxyRefusal(target.hostname);
  if (refusal) {
    refuseThroughProxy(target.hostname, refusal, res);
    return;
  }
  const upstream = http.request(
    {
      protocol: target.protocol,
      hostname: target.hostname,
      port: target.port || 80,
      path: `${target.pathname}${target.search}`,
      method: req.method,
      headers: { ...req.headers, host: target.host },
    },
    (answer) => {
      res.writeHead(answer.statusCode || 502, answer.headers);
      answer.pipe(res);
    }
  );
  upstream.on("error", (err) => {
    if (!res.headersSent) res.writeHead(502);
    res.end(String(err?.message ?? err));
  });
  req.pipe(upstream);
});

proxyServer.on("connect", (req, socket, head) => {
  const [host, port] = splitHostPort(req.url);
  const refusal = proxyRefusal(host);
  if (refusal) {
    console.log(`sympozium pi writer session: refused ${host} through the source proxy: ${refusal}`);
    socket.write("HTTP/1.1 403 Forbidden\r\n\r\n");
    socket.destroy();
    return;
  }
  const upstream = net.connect(Number(port) || 443, host, () => {
    socket.write("HTTP/1.1 200 Connection Established\r\n\r\n");
    upstream.write(head);
    upstream.pipe(socket);
    socket.pipe(upstream);
  });
  upstream.on("error", () => socket.destroy());
  socket.on("error", () => upstream.destroy());
});

await new Promise((resolve) => proxyServer.listen(proxyPort, "127.0.0.1", resolve));
console.log(`sympozium pi writer session: source proxy listening on 127.0.0.1:${proxyPort}`);

// The model endpoint must never go through the proxy: the allowlist is about source
// pages, and a proxied model call would be refused as an undeclared host. Cluster
// names and loopback are excluded for the same reason.
const modelHost = (() => {
  try {
    return new URL(process.env.MODEL_BASE_URL).hostname;
  } catch {
    return "";
  }
})();
process.env.NO_PROXY = ["127.0.0.1", "localhost", "::1", modelHost, ".svc", ".cluster.local"]
  .filter(Boolean)
  .join(",");

function proxyEnv(hosts) {
  if (!hosts) {
    for (const name of ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]) delete process.env[name];
    return;
  }
  const url = `http://127.0.0.1:${proxyPort}`;
  for (const name of ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]) process.env[name] = url;
}

// After a turn: the ledger's every URL is fetched here, the entries whose URL does
// not answer are dropped, and the file is rewritten with what the server saw.
async function verifyLedger(dir, hosts) {
  const path = join(dir, LEDGER_NAME);
  let raw;
  try {
    raw = await readFile(path, "utf8");
  } catch {
    console.log("sympozium pi writer session: the turn wrote no sources.json");
    return { sources: 0, quoted: 0, dropped: [], error: "the turn wrote no sources.json" };
  }
  let ledger;
  try {
    ledger = parseLedger(raw);
  } catch (err) {
    console.log(`sympozium pi writer session: sources.json is unreadable: ${err?.message ?? err}`);
    return { sources: 0, quoted: 0, dropped: [], error: String(err?.message ?? err) };
  }
  const { sources, dropped } = await revalidateLedger(ledger, { allowedHosts: hosts });
  for (const entry of dropped) {
    console.log(`sympozium pi writer session: dropped ledger entry ${entry.url}: ${entry.reason}`);
  }
  await writeFile(path, serialiseLedger(sources));
  return {
    sources: sources.length,
    quoted: sources.filter((entry) => entry.found).length,
    dropped,
    error: "",
  };
}

http
  .createServer(async (req, res) => {
    if (req.method === "GET" && req.url === "/healthz") {
      res.writeHead(200).end("ok");
      return;
    }
    // The two files a workflow fetches after authoring. Only files this server
    // writes, under their own run directory, are reachable.
    const artifactMatch = req.method === "GET" && req.url.match(/^\/artifacts\/([^/]+)\/([^/]+)$/);
    if (artifactMatch) {
      let sessionId;
      let name;
      try {
        sessionId = decodeURIComponent(artifactMatch[1]);
        name = decodeURIComponent(artifactMatch[2]);
      } catch {
        res.writeHead(400).end();
        return;
      }
      const file = resolveArtifact(workDir, sessionId, name);
      if (!file) {
        res.writeHead(404).end();
        return;
      }
      try {
        const info = await stat(file);
        res.writeHead(200, { "content-type": contentTypeFor(name), "content-length": info.size });
        createReadStream(file).pipe(res);
      } catch {
        res.writeHead(404).end();
      }
      return;
    }
    if (req.method !== "POST" || req.url !== "/v1/chat/completions") {
      res.writeHead(404).end();
      return;
    }
    try {
      const request = await readJSON(req);
      const brief = promptFrom(request.messages);
      const sessionID = safeSessionId(request.session_id);
      const hosts = parseSourceHosts(request.source_hosts);
      const stream = request.stream === true;
      const id = `chatcmpl-${randomUUID()}`;
      const cancellation = new AbortController();
      res.once("close", () => {
        if (!res.writableEnded) cancellation.abort();
      });
      if (stream) {
        res.writeHead(200, {
          "content-type": "text/event-stream",
          "cache-control": "no-cache",
          connection: "keep-alive",
          "x-accel-buffering": "no",
        });
      }

      // One directory per session: a reused session continues in place, and a fresh
      // one is isolated so sequential turns never overwrite each other's artifacts.
      const dir = resolveRunDir(workDir, sessionID);
      await mkdir(dir, { recursive: true });
      // The instruction follows the directory, not the caller: a session that already
      // holds an article is edited. A correction is also declared by `attempt > 1`,
      // because the artifact may not have been written by a turn that failed mid-way.
      const isIteration = (await exists(join(dir, ARTICLE_NAME))) || Number(request.attempt) > 1;
      const method = fillSourceHosts(await writingMethod(), hosts);
      const instruction = articleTurnInstruction({ isIteration });
      const prompt = `${brief}\n\n---\n\nWorking directory: ${dir}\n${instruction}\n\n${method}`;

      const response = await (queue = queue
        .catch(() => undefined)
        .then(async () => {
          articleHosts = hosts;
          proxyEnv(hosts);
          try {
            return await runPi(
              prompt,
              sessionID,
              stream
                ? (chunk) =>
                    writeSSE(res, {
                      id,
                      object: "chat.completion.chunk",
                      created: Math.floor(Date.now() / 1000),
                      model: process.env.MODEL_NAME,
                      choices: [{ index: 0, delta: { content: chunk }, finish_reason: null }],
                    })
                : undefined,
              cancellation.signal,
              dir
            );
          } finally {
            articleHosts = null;
            proxyEnv(null);
          }
        }));

      await sweepIfDue(sessionID);

      const ledger = await verifyLedger(dir, hosts);
      if (stream) {
        writeSSE(res, {
          id,
          object: "chat.completion.chunk",
          created: Math.floor(Date.now() / 1000),
          model: process.env.MODEL_NAME,
          choices: [{ index: 0, delta: {}, finish_reason: "stop" }],
        });
        if (!res.writableEnded) res.end("data: [DONE]\n\n");
        return;
      }
      const body = JSON.stringify({
        id,
        object: "chat.completion",
        created: Math.floor(Date.now() / 1000),
        model: process.env.MODEL_NAME,
        choices: [{ index: 0, message: { role: "assistant", content: response }, finish_reason: "stop" }],
        article: { name: ARTICLE_NAME, ledger: LEDGER_NAME, ...ledger },
      });
      res.writeHead(200, { "content-type": "application/json", "content-length": Buffer.byteLength(body) }).end(body);
    } catch (err) {
      const message = err instanceof Error ? err.message : "session request failed";
      // A pre-turn failure leaves no trace in Pi's own output, and the caller only
      // sees a 400 it may not record -- so the pod log is the operator's only
      // evidence of why a turn never started.
      console.error(`sympozium pi writer session: turn failed: ${message}`);
      if (res.headersSent) {
        writeSSE(res, { error: { message, type: "harness_session_error" } });
        if (!res.writableEnded) res.end("data: [DONE]\n\n");
        return;
      }
      const body = JSON.stringify({ error: { message, type: "harness_session_error" } });
      res.writeHead(400, { "content-type": "application/json", "content-length": Buffer.byteLength(body) }).end(body);
    }
  })
  .listen(port, "0.0.0.0", () => console.log(`sympozium pi writer session listening on ${port}`));
