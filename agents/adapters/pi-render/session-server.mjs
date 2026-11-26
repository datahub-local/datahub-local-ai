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
//   * skills and extensions stay disabled; only the built-in MCP client is loaded, so
//     the turn can read the catalog's GitHub and Firecrawl servers and nothing else.
//   * the toolchain is pointed at our vendored engine and browser, and each turn
//     gets the authoring method appended to whatever the caller sent.
//
// Everything else — the contract check, the credential checks, the provider
// config, the bounded body and output, serialized turns, SSE framing, client
// disconnect cancellation — is upstream's shape, so the platform sees the
// behaviour it expects.

import http from "node:http";
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
  stageRunAssets,
  compositionMarker,
  turnInstruction,
  planInstruction,
  parsePlan,
  parseFormOptions,
  parsePlanOptions,
  formOptionsInstruction,
  planOptionsInstruction,
  PLAN_FORMS,
  expiredRunDirs,
  expiredTranscripts,
  DEFAULT_SESSION_WORKSPACE,
  DEFAULT_RETRY,
  agentSettings,
  mcpConfig,
  stillArgs,
  captureStill,
  outputFps,
  sheetArgs,
  parseCheckReport,
  parseMotionSignals,
  stillTimesFor,
  connectorsVerification,
  checkArgs,
  MOTION_FILTER,
} from "./session-lib.mjs";

const port = Number(process.env.SYMPOZIUM_SESSION_PORT || "8080");
const maxBody = 1_048_576;
const maxOutput = 2_000_000;
// The session PVC is mounted at /tmp, so Pi's transcript survives a pod restart.
const sessionDir = "/tmp/pi-sessions";
const promptPath = "/opt/pi-render/prompts/authoring.md";
const planPromptPath = "/opt/pi-render/prompts/plan.md";
const formsPromptPath = "/opt/pi-render/prompts/forms.md";
const plansPromptPath = "/opt/pi-render/prompts/plans.md";
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

// The catalog servers that carry what the engine's own docs do not: worked examples and
// the repository's source. Pi reads this file beside models.json. The addresses are the
// deployment's, injected as env; the image carries no cluster names, and an unset variable
// leaves that server out.
await writeFile(
  `${process.env.HOME}/.pi/agent/mcp.json`,
  JSON.stringify(
    mcpConfig({
      githubUrl: process.env.SYMPOZIUM_GITHUB_MCP_URL ?? "",
      firecrawlUrl: process.env.SYMPOZIUM_FIRECRAWL_MCP_URL ?? "",
    })
  )
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

async function promptFile(path, label) {
  try {
    return await readFile(path, "utf8");
  } catch {
    // A missing prompt is loud on the first turn rather than fatal at startup:
    // the session still comes up and the error names the path.
    return `The ${label} file is missing at ${path}. Report that rather than improvising.`;
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
function runPi(prompt, sessionID, onOutput, signal, cwd = workDir, options = {}) {
  return new Promise((resolve, reject) => {
    const args = [
      "--print",
      "--no-prompt-templates",
      // Tools stay enabled — writing the composition and running the engine is the job —
      // but discovery is off: no skills or extensions are installed anywhere this pod can
      // see, and a skill found in the run directory or HOME would compete with the engine's
      // own documentation, which is the only contract this adapter relies on.
      "--no-skills",
      // The plan turn writes nothing and renders nothing, so it runs with no tools at all:
      // an instruction not to author is weaker than being unable to.
      ...(options.noTools ? ["--no-tools"] : []),
      // Discovery stays off, but MCP is a built-in extension and `--no-extensions` would
      // take it with the rest: only the catalog client is loaded back.
      "--no-extensions",
      "-e",
      "builtin:mcp",
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

// A bounded child process (ffmpeg, ffprobe, chromium, hyperframes) whose failure names its
// stderr, so a problem is legible rather than a bare exit code. `capture` resolves the child's
// stdout, which is how ffprobe's container report and chromium's DOM dump are read.
// `allowExit` resolves `{code, stdout, stderr}` instead of rejecting: the check report and the
// motion detector both write their finding to the stream even when the process exits non-zero.
function runCommand(command, args, cwd, { capture = false, maxStdout = 100_000, maxStderr = 4_000, allowExit = false } = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd, env: process.env, stdio: ["ignore", "pipe", "pipe"] });
    let stderr = "";
    let stdout = "";
    const keepStdout = capture || allowExit;
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      if (keepStdout && stdout.length < maxStdout) stdout += chunk.slice(0, maxStdout - stdout.length);
    });
    child.stderr.setEncoding("utf8");
    child.stderr.on("data", (chunk) => {
      if (stderr.length < maxStderr) stderr += chunk.slice(0, maxStderr - stderr.length);
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (allowExit) return resolve({ code, stdout, stderr });
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
async function makeStills(dir, { format, width, height, durationSeconds, fps, times }) {
  const f = safeFormat(format);
  const jobs = stillArgs({ format: f, runDir: dir, width, height, durationSeconds, fps, times });
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

// The deterministic gate over the artifact this server just produced. The engine and ffmpeg
// decide the perceptual facts (overlap, contrast, freeze, black, cut structure) and Chromium
// reports whether the connector helper resolved every declaration; the critic only decides
// what none of them can. Each part fails to a reported absence, never to a pass.
const EMPTY_SIGNALS = { freeze: [], black: [], cuts: [], scenes: [], scenesSeen: 0 };
const NO_CHECK = (reason) => ({ ran: false, ok: false, reason, counts: { error: 0, warning: 0, info: 0 }, findings: [] });

// `hyperframes check` launches its own Chrome and takes tens of seconds, so it runs once, on
// the delivered artifact. A non-zero exit still carries the report, which is why the code is
// read and the body parsed rather than the exit taken as the answer.
async function runCheck(dir, format) {
  if (safeFormat(format) === "svg" || safeFormat(format) === "png") {
    return NO_CHECK("the engine does not check this medium");
  }
  if (!(await exists(join(dir, "index.html")))) {
    // `hyperframes check` looks for index.html; a deck's out.html is a page, not a composition.
    const deck = await exists(join(dir, "out.html"));
    return NO_CHECK(deck ? "the deck's page is not a composition the engine checks" : "the run has no HTML composition to check");
  }
  try {
    const { code, stdout } = await runCommand("hyperframes", checkArgs(dir), dir, {
      allowExit: true,
      maxStdout: 2_000_000,
      maxStderr: 40_000,
    });
    const report = parseCheckReport(stdout);
    if (!report.ran) return NO_CHECK(`the check report could not be read (exit ${code})`);
    return report;
  } catch (err) {
    return NO_CHECK(err instanceof Error ? err.message : "the check did not run");
  }
}

// Two decode passes: freeze/black spans from the detectors, cut times from scdet. Their
// stderr is the result even when ffmpeg exits non-zero (a truncated clip), so both are parsed.
async function runMotion(dir, format, durationSeconds) {
  if (!["mp4", "gif", "webp"].includes(safeFormat(format))) return EMPTY_SIGNALS;
  const artifact = artifactName(format);
  let stderr = "";
  for (const filter of [MOTION_FILTER, "scdet=threshold=10"]) {
    try {
      const result = await runCommand(
        "ffmpeg",
        ["-hide_banner", "-nostats", "-i", artifact, "-vf", filter, "-f", "null", "-"],
        dir,
        { allowExit: true, maxStdout: 0, maxStderr: 4_000_000 }
      );
      stderr += result.stderr;
    } catch {
      // no decoder, no signals: reported as an empty shape rather than guessed
    }
  }
  return parseMotionSignals(stderr, durationSeconds);
}

// The declarations the composer wrote beside the composition. A missing or unreadable file is
// no declarations, not a failure of the turn.
async function readConnectorDeclarations(dir) {
  try {
    const parsed = JSON.parse(await readFile(join(dir, "connectors.json"), "utf8"));
    return Array.isArray(parsed?.connectors) ? parsed.connectors : [];
  } catch {
    return [];
  }
}

// Whether the helper ran and drew what was declared. Chromium dumps the settled DOM and the
// helper's own status attribute is read off it; a pass that could not run is an error naming
// the declaration count, so "no browser" never reads as "no arrows declared".
async function validateConnectors(dir, { declarations, durationSeconds }) {
  if (!declarations.length) return { declared: 0, drawn: 0, errors: [] };
  const seconds = Number(durationSeconds);
  const budget = Math.ceil((Number.isFinite(seconds) && seconds > 0 ? seconds : 3) * 1000) + 1000;
  const browserPath = process.env.HYPERFRAMES_BROWSER_PATH || "chromium";
  try {
    const { stdout } = await runCommand(
      browserPath,
      [
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--hide-scrollbars",
        `--virtual-time-budget=${budget}`,
        "--dump-dom",
        `file://${join(dir, "index.html")}`,
      ],
      dir,
      { allowExit: true, maxStdout: 5_000_000, maxStderr: 20_000 }
    );
    return connectorsVerification(stdout, declarations);
  } catch (err) {
    return {
      declared: declarations.length,
      drawn: 0,
      errors: [{ id: "*", reason: err instanceof Error ? err.message : "the DOM dump did not run" }],
    };
  }
}

// A clip's 1 fps contact sheet, made from the delivered artifact after the stills. It is one
// image for the whole clip rather than a sample of it, so a defect between two stills is still
// on the sheet. A sheet that could not be made is omitted, not reported as one.
async function makeSheet(dir, { format, durationSeconds, width }) {
  const f = safeFormat(format);
  if (!["mp4", "gif", "webp"].includes(f)) return "";
  const job = sheetArgs({ runDir: dir, durationSeconds, width });
  const made = await captureStill({ dir, output: job.output, run: () => runCommand(job.command, job.args, dir) });
  return made ? job.output : "";
}

// One turn at a time: Pi's session file is a shared resource and concurrent
// turns against it interleave. The contract asks adapters to serialize.
let queue = Promise.resolve();

const method = await promptFile(promptPath, "authoring method");
const planMethod = await promptFile(planPromptPath, "plan method");
const formsMethod = await promptFile(formsPromptPath, "form options method");
const plansMethod = await promptFile(plansPromptPath, "plan options method");

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
      // Absent `task` is the authoring turn every caller has always sent. `plan` is the
      // storyboard turn, `forms` the form-options turn and `plans` the plan-options turn; a
      // task this server does not serve is refused, not guessed at.
      const task = String(request.task ?? "").trim();
      if (task && !["plan", "forms", "plans"].includes(task)) throw new Error(`unknown task ${task}`);
      const id = `chatcmpl-${randomUUID()}`;
      const cancellation = new AbortController();
      res.once("close", () => {
        if (!res.writableEnded) cancellation.abort();
      });

      // A plan turn buys the storyboard before the authoring turn is paid for: Pi runs with
      // no tools, the answer is parsed, and nothing is authored — no render, no transcode,
      // no stills, no check, and no run directory written. It answers JSON even when the
      // caller streamed, because the plan is the object, not the prose around it.
      if (task === "plan") {
        // The session's directory is consulted, never created: the plan reads whether a
        // composition already exists, and a plan-only session leaves nothing behind. It
        // sweeps nothing either: expiring sessions is the authoring turn's job.
        const planDir = resolveRunDir(workDir, sessionID);
        const isIteration = await exists(join(planDir, compositionMarker(format)));
        const prompt = `${brief}\n\n---\n\n${planInstruction({ format, isIteration })}\n\n${planMethod}`;
        const response = await (queue = queue.catch(() => undefined).then(() =>
          runPi(prompt, sessionID, undefined, cancellation.signal, workDir, { noTools: true })
        ));
        const { plan, error } = parsePlan(response);
        const body = JSON.stringify({
          id,
          object: "chat.completion",
          created: Math.floor(Date.now() / 1000),
          model: process.env.MODEL_NAME,
          choices: [{ index: 0, message: { role: "assistant", content: response }, finish_reason: "stop" }],
          plan,
          raw: response,
          ...(error ? { error } : {}),
        });
        res.writeHead(200, { "content-type": "application/json", "content-length": Buffer.byteLength(body) }).end(body);
        return;
      }

      // The form-options and plan-options turns are the same shape as the plan turn: no
      // tools, no directory, no artifact. The options are data; a rejected option is named
      // in `error` while the valid ones are returned, so the caller can still choose.
      if (task === "forms" || task === "plans") {
        const count = Number(request.options);
        const form = String(request.form ?? "").trim().toLowerCase();
        if (task === "plans" && !PLAN_FORMS.includes(form)) {
          throw new Error(`unknown form ${form || "(none)"}; the plans turn needs a chosen form`);
        }
        const instruction = task === "forms"
          ? `${formOptionsInstruction({ format, count })}\n\n${formsMethod}`
          : `${planOptionsInstruction({ format, form, count })}\n\n${plansMethod}\n\n${planMethod}`;
        const prompt = `${brief}\n\n---\n\n${instruction}`;
        const response = await (queue = queue.catch(() => undefined).then(() =>
          runPi(prompt, sessionID, undefined, cancellation.signal, workDir, { noTools: true })
        ));
        const parsed = task === "forms"
          ? parseFormOptions(response)
          : parsePlanOptions(response, { form });
        const fields = task === "forms" ? { forms: parsed.forms } : { plans: parsed.plans };
        const body = JSON.stringify({
          id,
          object: "chat.completion",
          created: Math.floor(Date.now() / 1000),
          model: process.env.MODEL_NAME,
          choices: [{ index: 0, message: { role: "assistant", content: response }, finish_reason: "stop" }],
          ...fields,
          raw: response,
          ...(parsed.error ? { error: parsed.error } : {}),
        });
        res.writeHead(200, { "content-type": "application/json", "content-length": Buffer.byteLength(body) }).end(body);
        return;
      }

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
      await stageRunAssets(dir);
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
      // same run directory, before answering -- and conform it to the declared container,
      // which the composition's own frame may not match (probed, not assumed).
      const engineContainer = await probeContainer(dir, "out.mp4");
      const containerOpts = { fps, width, height, frames, durationSeconds, actual: engineContainer };
      const { conformed, reason } = await transcode(dir, format, containerOpts);
      const conformance = conformanceNote({ opts: containerOpts, actual: engineContainer, conformed, reason });

      // The deterministic gate, before the stills: what the engine and ffmpeg can decide about
      // the bytes just delivered, and what the connector helper left in the DOM. It is evidence
      // for the review, not a verdict, and a part that could not run says so.
      const deliveredFps = outputFps({ frames, durationSeconds, fps });
      const check = await runCheck(dir, format);
      const signals = await runMotion(dir, format, durationSeconds);
      const declarations =
        safeFormat(format) === "svg" || safeFormat(format) === "png" ? [] : await readConnectorDeclarations(dir);
      const connectors = await validateConnectors(dir, { declarations, durationSeconds });
      const { times, scenesCovered } = stillTimesFor(signals, durationSeconds, { fps: deliveredFps });

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
        fps: deliveredFps,
        times,
      });
      // One frame per second, in one image: coverage of every second the stills sample past.
      const sheet = await makeSheet(dir, { format, durationSeconds, width });

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
        conformance,
        check,
        signals: { ...signals, scenesCovered },
        connectors,
        ...(sheet ? { sheet } : {}),
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
