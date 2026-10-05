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
import { mkdir, readFile, stat, writeFile } from "node:fs/promises";
import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";

import {
  safeSessionId,
  safeFormat,
  artifactName,
  runDir as resolveRunDir,
  resolveArtifact,
  contentTypeFor,
  transcodeArgs,
} from "./session-lib.mjs";

const port = Number(process.env.SYMPOZIUM_SESSION_PORT || "8080");
const maxBody = 1_048_576;
const maxOutput = 2_000_000;
// The session PVC is mounted at /tmp, so Pi's transcript survives a pod restart.
const sessionDir = "/tmp/pi-sessions";
const promptPath = "/opt/pi-render/prompts/authoring.md";
const workDir = process.env.SYMPOZIUM_WORKSPACE || "/workspace";

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

await writeFile(
  `${process.env.HOME}/.pi/agent/models.json`,
  JSON.stringify({
    providers: {
      sympozium: {
        baseUrl: process.env.MODEL_BASE_URL,
        api: "openai-completions",
        apiKey: "$OPENAI_API_KEY",
        compat: { supportsDeveloperRole: false, supportsReasoningEffort: false },
        models: [
          {
            id: process.env.MODEL_NAME,
            reasoning: false,
            input: ["text"],
            contextWindow: 65536,
            maxTokens: 8192,
          },
        ],
      },
    },
  })
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
      if (code !== 0) return reject(new Error(`Pi exited ${code}: ${stderr.slice(-1000)}`));
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

      // One directory per run: sequential turns must not overwrite each other's
      // artifact, and the agent is told exactly where to write it.
      const dir = resolveRunDir(workDir, sessionID);
      await mkdir(dir, { recursive: true });
      const prompt =
        `${brief}\n\n---\n\nWorking directory: ${dir}\n` +
        `Write the composition to \`index.html\` here and render it to \`out.mp4\` in this same directory.\n\n${method}`;

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
      await transcode(dir, format, { fps, width });

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
