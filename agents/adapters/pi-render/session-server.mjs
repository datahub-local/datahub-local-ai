#!/usr/bin/env node
// The v1alpha2 session endpoint for the Pi render adapter.
//
// A `HarnessSession` runs this as a long-lived Deployment rather than a Job, which
// is the point: it keeps the agent's state across turns (Pi's session file lives on
// the session PVC), it costs one pod instead of one per request, and — the reason
// this file exists — a session Deployment honours `AgentRuntime.spec.resources`,
// where a Job's agent container is hardcoded to 1Gi and OOMKills a render.
//
// Derived from the maintained Pi adapter's session-server.mjs, which is the
// reference for this contract. Three deltas, each deliberate:
//
//   * `--no-tools` is dropped, so Pi can write the composition and run the engine.
//   * `--no-skills` is dropped, so Pi can read the skills baked into the image.
//   * the toolchain is pointed at our vendored engine and browser, and each turn
//     gets the authoring method appended to whatever the caller sent.
//
// Everything else — the contract check, the credential checks, the provider
// config, the bounded body and output, serialized turns, SSE framing, client
// disconnect cancellation — is upstream's shape, so the platform sees the
// behaviour it expects.

import http from "node:http";
import net from "node:net";
import { createReadStream } from "node:fs";
import { mkdir, readFile, readdir, rename, rm, stat, writeFile } from "node:fs/promises";
import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { join } from "node:path";

import {
  safeSessionId,
  safeFormat,
  artifactName,
  runDir as resolveRunDir,
  resolveArtifact,
  contentTypeFor,
  transcodeArgs,
  conformanceNote,
  CONFORMED_TEMP,
  stageVendorAssets,
  compositionMarker,
  turnInstruction,
  expiredRunDirs,
  expiredTranscripts,
  DEFAULT_SESSION_WORKSPACE,
  DEFAULT_RETRY,
  agentSettings,
  stillArgs,
  captureStill,
  outputFps,
  parseProfile,
  PROFILES,
  ARTICLE_NAME,
  LEDGER_NAME,
  parseSourceHosts,
  fillSourceHosts,
  parseLedger,
  serialiseLedger,
  revalidateLedger,
  articleTurnInstruction,
  hostAllowed,
} from "./session-lib.mjs";

const port = Number(process.env.SYMPOZIUM_SESSION_PORT || "8080");
const maxBody = 1_048_576;
const maxOutput = 2_000_000;
// The session PVC is mounted at /tmp, so Pi's transcript survives a pod restart.
const sessionDir = "/tmp/pi-sessions";
const promptDir = process.env.PI_RENDER_PROMPT_DIR || "/opt/pi-render/prompts";
const proxyPort = Number(process.env.ARTICLE_PROXY_PORT || "8081");
// A session container mounts the session PVC at /tmp and does **not** mount
// /workspace (only the Job path does), so the workspace must default under the PVC.
// The caller can still override it.
const workDir = process.env.SYMPOZIUM_WORKSPACE || DEFAULT_SESSION_WORKSPACE;

// Session state is durable, so it has to expire: an abandoned thread would otherwise
// keep its run directory and Pi transcript forever, and a render loop would fill the
// PVC and then fail every turn. 0 (or a non-number) disables the sweep. The default
// matches Visual Studio Prune's seven-day table-row window, so a run's row and its
// files expire together.
const retentionDays = Number(process.env.PI_RENDER_SESSION_TTL_DAYS ?? "7");
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
async function sweepSessions(keep) {
  if (!Number.isFinite(retentionDays) || retentionDays <= 0) return;
  const cutoffMs = Date.now() - retentionDays * 24 * 60 * 60 * 1000;
  try {
    for (const name of expiredRunDirs(await listEntries(join(workDir, "runs")), { cutoffMs, keep })) {
      await rm(join(workDir, "runs", name), { recursive: true, force: true });
      console.log(`sympozium pi render session: swept expired session ${name}`);
    }
    for (const name of expiredTranscripts(await listEntries(sessionDir), { cutoffMs, keep })) {
      await rm(join(sessionDir, name), { force: true });
      console.log(`sympozium pi render session: swept expired transcript ${name}`);
    }
    lastSweep = Date.now();
  } catch (err) {
    console.error(`sympozium pi render session: sweep failed: ${err?.message ?? err}`);
  }
}

let lastSweep = Date.now();
async function sweepIfDue(keep) {
  if (Date.now() - lastSweep < sweepIntervalMs) return;
  await sweepSessions(keep);
}

async function exists(path) {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
}

function fail(message) {
  console.error(`sympozium pi render session: ${message}`);
  process.exit(1);
}

for (const name of ["MODEL_NAME", "MODEL_BASE_URL", "OPENAI_API_KEY"]) {
  if (!process.env[name]) fail(`${name} is required`);
}
if (process.env.SYMPOZIUM_HARNESS_CONTRACT_VERSION !== "v1alpha2") {
  fail("unsupported harness contract");
}

// The toolchain must be reachable before the first turn, or every request fails
// with a message the caller has to decode. Fail at startup instead, where the
// session's Ready condition carries it.
const browser = process.env.HYPERFRAMES_BROWSER_PATH || "/usr/bin/chromium";
const engine = "/usr/local/bin/hyperframes";

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
            contextWindow: Number(process.env.PI_RENDER_CONTEXT_WINDOW || "262144"),
            // The gateway's reasoning is billed as output and, left on, this model
            // spends every token it is given thinking and returns no content at all
            // (8192 and 32768 both came back `length` with empty content). Pi only
            // sends `reasoning_effort` for a non-off thinking level, so the session
            // runs at `minimal`, which this map turns into the `none` the gateway
            // honours. Both numbers are overridable so they can move without a rebuild.
            thinkingLevelMap: { minimal: "none" },
            maxTokens: Number(process.env.PI_RENDER_MAX_TOKENS || "65536"),
          },
        ],
      },
    },
  })
);

// Pi's retry and idle-timeout settings, which Pi reads from the same agent directory.
// Without this file the composer runs on the vendor's defaults, where a stream that
// stalls for longer than the gateway's per-read timeout ends the attempt with no
// window left to retry in. Overridable like the numbers above, so the window can move
// without a rebuild; `agentSettings` refuses an idle timeout the gateway would beat.
await writeFile(
  `${process.env.HOME}/.pi/agent/settings.json`,
  JSON.stringify(
    agentSettings({
      idleTimeoutMs: Number(process.env.PI_RENDER_HTTP_IDLE_MS || DEFAULT_RETRY.idleTimeoutMs),
      maxRetries: Number(process.env.PI_RENDER_RETRY_MAX || DEFAULT_RETRY.maxRetries),
      baseDelayMs: Number(process.env.PI_RENDER_RETRY_BASE_MS || DEFAULT_RETRY.baseDelayMs),
      maxAgentDelayMs: Number(process.env.PI_RENDER_RETRY_MAX_DELAY_MS || DEFAULT_RETRY.maxAgentDelayMs),
    })
  )
);

process.env.HYPERFRAMES_BROWSER_PATH = browser;
process.env.HYPERFRAMES_SKIP_SKILLS = "1";

async function authoringMethod(profile) {
  const name = PROFILES[profile].instruction;
  const path = join(promptDir, name);
  try {
    return await readFile(path, "utf8");
  } catch {
    // A missing prompt is loud on the first turn rather than fatal at startup:
    // the session still comes up and the error names the path.
    return `The ${profile} instruction file is missing at ${path}. Report that rather than improvising.`;
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
// window and a bad brief are the same string in the run record, and the caller
// cannot tell a model-endpoint problem from its own.
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
      // Tools stay enabled — writing the composition and running the engine is the job —
      // but discovery is off: no skills or extensions are installed anywhere this pod can
      // see, and a skill found in the run directory or HOME would compete with the engine's
      // own documentation, which is the only contract this adapter relies on.
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

// A bounded child process (ffmpeg, ffprobe) whose failure names its stderr, so a transcode
// problem is legible rather than a bare exit code. `capture` resolves the child's stdout,
// which is how ffprobe's container report is read.
function runCommand(command, args, cwd, { capture = false } = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd, env: process.env, stdio: ["ignore", "pipe", "pipe"] });
    let stderr = "";
    let stdout = "";
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      if (capture && stdout.length < 100_000) stdout += chunk;
    });
    child.stderr.setEncoding("utf8");
    child.stderr.on("data", (chunk) => {
      if (stderr.length < 4000) stderr += chunk;
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) return resolve(capture ? stdout : undefined);
      reject(new Error(`${command} exited ${code}: ${stderr.slice(-1000)}`));
    });
  });
}

// The container the engine actually produced. A composition carries its own frame in its
// markup, so a render can disagree with the request that asked for it: measured on the
// tiles type (2026-10-17, run 13762), a request declaring 16:9 / viewport 1280 / 12s was
// rendered at 1080x1350 / 3s. `null` means it could not be read -- which is conformed
// rather than trusted, and reported rather than failed.
async function probeContainer(dir, name) {
  try {
    const raw = await runCommand(
      "ffprobe",
      [
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        name,
      ],
      dir,
      { capture: true }
    );
    const parsed = JSON.parse(raw);
    const stream = ((parsed.streams || [])[0]) || {};
    const [num, den] = String(stream.r_frame_rate || "").split("/").map(Number);
    return {
      width: stream.width,
      height: stream.height,
      durationSeconds: Number((parsed.format || {}).duration),
      fps: den ? num / den : num,
    };
  } catch {
    return null;
  }
}

// The engine always renders out.mp4. A caller that asked for another format gets it
// produced here, after the render, and every kind is conformed to the container the request
// declared -- frame, rate and length -- because the engine's frame is the composition's own
// markup rather than the request's. Deterministic post-processing, not a model decision.
// Returns what ran, so the note can say whether anything was conformed and why not.
async function transcode(dir, format, opts) {
  const args = transcodeArgs(format, opts);
  if (!args) return { name: artifactName(format), conformed: false, reason: "" };
  try {
    await runCommand("ffmpeg", args, dir);
  } catch (err) {
    // An mp4 already has a valid artifact -- the engine's own render -- so a conformance
    // that could not run is reported rather than fatal, and the caller still gets bytes.
    // A format change has no such fallback: without it there is no artifact to serve.
    if (safeFormat(format) !== "mp4") throw err;
    const message = err instanceof Error ? err.message : "the conformance did not run";
    return { name: artifactName(format), conformed: false, reason: message };
  }
  // ffmpeg cannot read and write one file, and for mp4 the artifact IS the engine's output,
  // so the conformance wrote a sibling that replaces it here.
  if (safeFormat(format) === "mp4") await rename(join(dir, CONFORMED_TEMP), join(dir, artifactName(format)));
  return { name: artifactName(format), conformed: true, reason: "" };
}

function writeSSE(res, value) {
  if (!res.writableEnded) res.write(`data: ${JSON.stringify(value)}\n\n`);
}

// The stills of the render, produced here because the artifact is here and left in the run
// directory for the studio to fetch. This server makes no model call: the review is the
// workflow's, and all it needs from here is something to look at.
async function makeStills(dir, { format, width, height, durationSeconds, fps }) {
  const f = safeFormat(format);
  const jobs = stillArgs({ format: f, runDir: dir, width, height, durationSeconds, fps });
  if (!jobs.length) {
    // A still png IS the still, and the launch card is one: nothing to sample.
    return [artifactName(f)];
  }
  const names = [];
  for (const job of jobs) {
    // A still that could not be made does not fail the turn: the others still show it. It
    // is not offered either -- the studio fetches the names it is given, so a name whose
    // file was not written this turn is one more still the review judges nothing on.
    const made = await captureStill({ dir, output: job.output, run: () => runCommand(job.command, job.args, dir) });
    if (made) names.push(job.output);
  }
  return names;
}

// One turn at a time: Pi's session file is a shared resource and concurrent
// turns against it interleave. The contract asks adapters to serialize.
let queue = Promise.resolve();

// ---------------------------------------------------------------------------
// The article allowlist proxy.
//
// An instruction is not enforcement, and the CNI here is not FQDN-aware, so the
// allowlist lives in front of the tools: `curl` in a bash tool honours
// `HTTPS_PROXY`, and anything off the list answers 403 here with the host logged.
// The list is per turn because the caller names the hosts; turns are serialized, so
// one module-level value is the turn's.
let articleHosts = null;

function proxyRefusal(host) {
  if (!articleHosts) return "no article turn is fetching";
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
  console.log(`sympozium pi render session: refused ${host} through the article proxy: ${reason}`);
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
    console.log(`sympozium pi render session: refused ${host} through the article proxy: ${refusal}`);
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
console.log(`sympozium pi render session: article proxy listening on 127.0.0.1:${proxyPort}`);

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

// After an article turn: the ledger's every URL is fetched here, the entries whose
// URL does not answer are dropped, and the file is rewritten with what the server
// saw. The model is never the authority on whether a source exists.
async function verifyLedger(dir, hosts) {
  const path = join(dir, LEDGER_NAME);
  let raw;
  try {
    raw = await readFile(path, "utf8");
  } catch {
    console.log("sympozium pi render session: the article turn wrote no sources.json");
    return { sources: 0, quoted: 0, dropped: [], error: "the turn wrote no sources.json" };
  }
  let ledger;
  try {
    ledger = parseLedger(raw);
  } catch (err) {
    console.log(`sympozium pi render session: sources.json is unreadable: ${err?.message ?? err}`);
    return { sources: 0, quoted: 0, dropped: [], error: String(err?.message ?? err) };
  }
  const { sources, dropped } = await revalidateLedger(ledger, { allowedHosts: hosts });
  for (const entry of dropped) {
    console.log(`sympozium pi render session: dropped ledger entry ${entry.url}: ${entry.reason}`);
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
    // The artifact a workflow fetches after authoring. Only files this server
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
      const profile = parseProfile(request.profile);
      const isArticle = profile === "article";
      const sessionID = safeSessionId(request.session_id);
      const format = safeFormat(request.format);
      const fps = Number(request.fps);
      const width = Number(request.width);
      const height = Number(request.height);
      const frames = Number(request.frames);
      const durationSeconds = Number(request.durationSeconds);
      const hosts = isArticle ? parseSourceHosts(request.source_hosts) : [];
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
      // one is isolated so sequential turns never overwrite each other's artifact.
      const dir = resolveRunDir(workDir, sessionID);
      await mkdir(dir, { recursive: true });
      // The instruction follows the directory, not the caller: a session that already
      // holds an artifact is edited, so a declaration and a swept session agree. An
      // article's correction is also declared by `attempt > 1`, because the artifact
      // may not have been written by a turn that failed mid-way.
      let isIteration;
      if (isArticle) {
        isIteration = (await exists(join(dir, ARTICLE_NAME))) || Number(request.attempt) > 1;
      } else {
        // The vendored GSAP resolves as a sibling of the composition; stage it before
        // the turn so the composer's `<script src="gsap.min.js">` is served.
        await stageVendorAssets(dir);
        isIteration = await exists(join(dir, compositionMarker(format)));
      }
      const method = fillSourceHosts(await authoringMethod(profile), hosts);
      const instruction = isArticle
        ? articleTurnInstruction({ isIteration })
        : turnInstruction({ format, isIteration });
      const prompt = `${brief}\n\n---\n\nWorking directory: ${dir}\n${instruction}\n\n${method}`;

      const response = await (queue = queue
        .catch(() => undefined)
        .then(async () => {
          if (isArticle) {
            articleHosts = hosts;
            proxyEnv(hosts);
          }
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
            if (isArticle) {
              articleHosts = null;
              proxyEnv(null);
            }
          }
        }));

      await sweepIfDue(sessionID);

      if (isArticle) {
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
          stills: [],
          article: { name: ARTICLE_NAME, ledger: LEDGER_NAME, ...ledger },
        });
        res.writeHead(200, { "content-type": "application/json", "content-length": Buffer.byteLength(body) }).end(body);
        return;
      }

      // Produce the caller's requested format from the engine's out.mp4, in the
      // same run directory, before answering -- and conform it to the declared container,
      // which the composition's own frame may not match (probed, not assumed).
      const engineContainer = await probeContainer(dir, "out.mp4");
      const containerOpts = { fps, width, height, frames, durationSeconds, actual: engineContainer };
      const { conformed, reason } = await transcode(dir, format, containerOpts);
      const conformance = conformanceNote({ opts: containerOpts, actual: engineContainer, conformed, reason });

      // Then hand back stills of it. The studio's critic looks at these; the review, its
      // bound and its verdict belong to the workflow, not to this server. They are made
      // after the conformance so the critic sees the artifact the caller receives.
      //
      // The rate they are sampled at is the one the conformance DELIVERS, from the
      // declaration -- not the engine's pre-conformance rate, which is exactly the trap
      // this fixes: an 8 fps artifact produced from a 30 fps render would be seeked at
      // 1/30 s and lose its settled frame.
      const stills = await makeStills(dir, {
        format, width, height, durationSeconds,
        fps: outputFps({ frames, durationSeconds, fps }),
      });

      if (stream) {
        writeSSE(res, {
          id,
          object: "chat.completion.chunk",
          created: Math.floor(Date.now() / 1000),
          model: process.env.MODEL_NAME,
          choices: [{ index: 0, delta: {}, finish_reason: "stop" }],
        });
        // The stills are a field, not a chunk: the studio's own call is not a stream.
        if (!res.writableEnded) res.end("data: [DONE]\n\n");
        return;
      }
      const body = JSON.stringify({
        id,
        object: "chat.completion",
        created: Math.floor(Date.now() / 1000),
        model: process.env.MODEL_NAME,
        choices: [{ index: 0, message: { role: "assistant", content: response }, finish_reason: "stop" }],
        stills,
        conformance,
      });
      res.writeHead(200, { "content-type": "application/json", "content-length": Buffer.byteLength(body) }).end(body);
    } catch (err) {
      const message = err instanceof Error ? err.message : "session request failed";
      // A pre-turn failure (staging, an unreadable workspace) leaves no trace in Pi's own
      // output, and the caller only sees a 400 it may not record -- so the pod log is the
      // operator's only evidence of why a turn never started.
      console.error(`sympozium pi render session: turn failed: ${message}`);
      if (res.headersSent) {
        writeSSE(res, { error: { message, type: "harness_session_error" } });
        if (!res.writableEnded) res.end("data: [DONE]\n\n");
        return;
      }
      const body = JSON.stringify({ error: { message, type: "harness_session_error" } });
      res.writeHead(400, { "content-type": "application/json", "content-length": Buffer.byteLength(body) }).end(body);
    }
  })
  .listen(port, "0.0.0.0", () => console.log(`sympozium pi render session listening on ${port}`));
