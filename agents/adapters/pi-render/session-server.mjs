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
import { createReadStream } from "node:fs";
import { mkdir, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
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
  stageVendorAssets,
  compositionMarker,
  turnInstruction,
  expiredRunDirs,
  expiredTranscripts,
  DEFAULT_SESSION_WORKSPACE,
  DEFAULT_RETRY,
  agentSettings,
  stillArgs,
} from "./session-lib.mjs";

const port = Number(process.env.SYMPOZIUM_SESSION_PORT || "8080");
const maxBody = 1_048_576;
const maxOutput = 2_000_000;
// The session PVC is mounted at /tmp, so Pi's transcript survives a pod restart.
const sessionDir = "/tmp/pi-sessions";
const promptPath = "/opt/pi-render/prompts/authoring.md";
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

async function authoringMethod() {
  try {
    return await readFile(promptPath, "utf8");
  } catch {
    // A missing prompt is loud on the first turn rather than fatal at startup:
    // the session still comes up and the error names the path.
    return `The authoring method file is missing at ${promptPath}. Report that rather than improvising.`;
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

// A bounded child process (ffmpeg) whose failure names its stderr, so a transcode
// problem is legible rather than a bare exit code.
function runCommand(command, args, cwd) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd, env: process.env, stdio: ["ignore", "pipe", "pipe"] });
    let stderr = "";
    child.stderr.setEncoding("utf8");
    child.stderr.on("data", (chunk) => {
      if (stderr.length < 4000) stderr += chunk;
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) return resolve();
      reject(new Error(`${command} exited ${code}: ${stderr.slice(-1000)}`));
    });
  });
}

// The engine always renders out.mp4. A caller that asked for another format gets it
// produced here, after the render, from the type's declared fps/width — deterministic
// post-processing, not a model decision. MP4 needs no step.
async function transcode(dir, format, opts) {
  const args = transcodeArgs(format, opts);
  if (!args) return artifactName(format);
  await runCommand("ffmpeg", args, dir);
  return artifactName(format);
}

function writeSSE(res, value) {
  if (!res.writableEnded) res.write(`data: ${JSON.stringify(value)}\n\n`);
}

// The stills of the render, produced here because the artifact is here and left in the run
// directory for the studio to fetch. This server makes no model call: the review is the
// workflow's, and all it needs from here is something to look at.
async function makeStills(dir, { format, width, height, durationSeconds }) {
  const f = safeFormat(format);
  const jobs = stillArgs({ format: f, runDir: dir, width, height, durationSeconds });
  if (!jobs.length) {
    // A still png IS the still, and the launch card is one: nothing to sample.
    return [artifactName(f)];
  }
  const names = [];
  for (const job of jobs) {
    try {
      await runCommand(job.command, job.args, dir);
      names.push(job.output);
    } catch {
      // one still that cannot be made does not fail the turn: the others still show it
    }
  }
  return names;
}

// One turn at a time: Pi's session file is a shared resource and concurrent
// turns against it interleave. The contract asks adapters to serialize.
let queue = Promise.resolve();

const method = await authoringMethod();

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
      const sessionID = safeSessionId(request.session_id);
      const format = safeFormat(request.format);
      const fps = Number(request.fps);
      const width = Number(request.width);
      const height = Number(request.height);
      const frames = Number(request.frames);
      const durationSeconds = Number(request.durationSeconds);
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
      // The vendored GSAP resolves as a sibling of the composition; stage it before
      // the turn so the composer's `<script src="gsap.min.js">` is served.
      await stageVendorAssets(dir);
      // The instruction follows the directory, not the caller: a session that already
      // holds a composition is edited, so a declaration and a swept session agree.
      const isIteration = await exists(join(dir, compositionMarker(format)));
      const prompt =
        `${brief}\n\n---\n\nWorking directory: ${dir}\n${turnInstruction({ format, isIteration })}\n\n${method}`;

      const response = await (queue = queue.catch(() => undefined).then(() =>
        runPi(
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
        )
      ));

      // Produce the caller's requested format from the engine's out.mp4, in the
      // same run directory, before answering.
      await transcode(dir, format, { fps, width, frames, durationSeconds });

      // Then hand back stills of it. The studio's critic looks at these; the review, its
      // bound and its verdict belong to the workflow, not to this server.
      const stills = await makeStills(dir, { format, width, height, durationSeconds });

      await sweepIfDue(sessionID);

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
      });
      res.writeHead(200, { "content-type": "application/json", "content-length": Buffer.byteLength(body) }).end(body);
    } catch (err) {
      const message = err instanceof Error ? err.message : "session request failed";
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
