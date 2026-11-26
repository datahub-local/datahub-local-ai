// Pure helpers for the pi-render session server: request/artifact path safety and
// the output-format post-processing. Kept out of session-server.mjs so they can be
// unit-tested with `node --test` without starting the HTTP server.

import { basename, join, normalize, sep } from "node:path";
import { copyFile, rm, stat } from "node:fs/promises";

// The shape session-server.mjs accepts for session_id: a run identifier that is
// safe as a single path segment. `.` and `..` are excluded even though the
// character class would allow them — as a directory segment they escape the runs
// directory.
export const SESSION_ID_RE = /^(?!\.{1,2}$)[a-zA-Z0-9._-]{1,80}$/;

// A produced artifact name. Deliberately narrower than session_id: only the names
// this server writes are ever served.
const ARTIFACT_NAME_RE = /^out\.(mp4|gif|webp|png|svg|html)$/;
// The stills of a render, served beside it: the studio's critic fetches one of these. They
// are the only other names this server writes, so the route stays a whitelist rather than a
// path a caller can steer. The contact sheet is one of them: the critic fetches it by name.
const STILL_NAME_RE = /^review-(final|\d+|sheet)\.(png|jpg)$/;

export const DEFAULT_FORMAT = "mp4";

// A session container mounts the session PVC at /tmp and does not mount /workspace
// (only the Job path does). The default workspace must therefore live under /tmp, or
// the first turn fails with "mkdir '/workspace/runs'".
export const DEFAULT_SESSION_WORKSPACE = "/tmp/aivideo";

// format -> how it is produced and served.
export const FORMATS = {
  mp4: { ext: "mp4", mime: "video/mp4" },
  gif: { ext: "gif", mime: "image/gif" },
  webp: { ext: "webp", mime: "image/webp" },
  png: { ext: "png", mime: "image/png" },
  svg: { ext: "svg", mime: "image/svg+xml" },
  // A deck is authored directly as one self-contained HTML file, and the same turn
  // renders its paired out.mp4; there is nothing to transcode for the deck itself.
  html: { ext: "html", mime: "text/html" },
};

export function isValidSessionId(value) {
  return typeof value === "string" && SESSION_ID_RE.test(value);
}

export function safeSessionId(value) {
  return isValidSessionId(value) ? value : "default";
}

export function safeFormat(value) {
  return typeof value === "string" && Object.prototype.hasOwnProperty.call(FORMATS, value)
    ? value
    : DEFAULT_FORMAT;
}

// The run's file name for a format; the caller derives the same name to fetch it.
export function artifactName(format) {
  return `out.${FORMATS[safeFormat(format)].ext}`;
}

// <workspace>/runs/<session_id> — one directory per run so sequential turns never
// overwrite one another's artifact.
export function runDir(workspace, sessionId) {
  return join(workspace, "runs", safeSessionId(sessionId));
}

// The assets the composition loads as siblings. An absolute /opt path 404s at render
// time (hit live), so each is staged next to the composition. Two sources, because
// they are different things: `vendor/` is third-party and never edited (`gsap.min.js`),
// `runtime/` is this adapter's own browser code (`connectors.js`). Keeping them apart
// is what stops a future "vendored" edit from rewriting our helper, or the reverse.
export const VENDOR_DIR = process.env.SYMPOZIUM_VENDOR_DIR || "/opt/hyperframes/vendor";
export const RUNTIME_DIR = process.env.SYMPOZIUM_RUNTIME_DIR || "/opt/hyperframes/runtime";
export const VENDOR_ASSETS = ["gsap.min.js"];
export const RUNTIME_ASSETS = ["connectors.js"];

// Copy the served assets into a run directory before the composer runs. Best effort:
// a missing asset is a render-time failure the composer reports, not a reason to fail
// the turn. Returns the names staged.
export async function stageRunAssets(dir, vendorDir = VENDOR_DIR, runtimeDir = RUNTIME_DIR) {
  const staged = [];
  for (const [source, name] of [
    ...VENDOR_ASSETS.map((n) => [vendorDir, n]),
    ...RUNTIME_ASSETS.map((n) => [runtimeDir, n]),
  ]) {
    try {
      await copyFile(join(source, name), join(dir, name));
      staged.push(name);
    } catch {
      // left out of staged; the composition fails loudly if it needs it
    }
  }
  return staged;
}

// Resolve a fetch to an absolute path inside the run directory, or null when the
// name is not an artifact this server writes. `basename` plus a prefix check makes
// traversal (`..`, absolute paths, separators) resolve to null rather than escape.
export function resolveArtifact(workspace, sessionId, name) {
  if (!isValidSessionId(sessionId)) return null;
  if (typeof name !== "string" || (!ARTIFACT_NAME_RE.test(name) && !STILL_NAME_RE.test(name))) return null;
  if (basename(name) !== name) return null;
  const dir = runDir(workspace, sessionId);
  const full = normalize(join(dir, name));
  if (full !== join(dir, name)) return null;
  if (!full.startsWith(dir + sep)) return null;
  return full;
}

export function contentTypeFor(name) {
  for (const { ext, mime } of Object.values(FORMATS)) {
    if (name === `out.${ext}`) return mime;
  }
  if (name.endsWith(".png")) return "image/png";
  if (name.endsWith(".jpg")) return "image/jpeg";
  return "application/octet-stream";
}

// The file whose presence means a session has already been authored in. A later
// turn in the same session is an edit of it, not a first authoring. An SVG and a
// deck author a different artifact than a video, so the marker follows the format.
export function compositionMarker(format) {
  switch (safeFormat(format)) {
    case "svg":
      return "out.svg";
    case "html":
      return "out.html";
    default:
      return "index.html";
  }
}

// The trailing instruction for a turn. The caller's brief carries the content and
// any change; this is the mechanical part — where to write and whether the turn
// authors or edits. An edit names the artifact already in the session so the
// composer continues from it instead of starting over.
export function turnInstruction({ format, isIteration } = {}) {
  const f = safeFormat(format);
  if (f === "svg") {
    return isIteration
      ? "`out.svg` in this directory is the animated SVG from an earlier turn in this session. Apply the request above to it in place - change what it names and keep the rest - and write `out.svg` again. Do not write index.html and do not render."
      : "Author one self-contained animated SVG and write it to `out.svg` in this directory. Do not write index.html and do not render.";
  }
  if (f === "html") {
    return isIteration
      ? "`out.html` and `index.html` in this directory are the deck and its video from an earlier turn in this session. Apply the request above to both in place - change what it names and keep the rest - then re-render `out.mp4` so the video matches the deck."
      : "Author one self-contained HTML deck and write it to `out.html` in this directory, then author a composition of the same plan to `index.html` here and render it to `out.mp4` so the video matches the deck.";
  }
  return isIteration
    ? "`index.html` in this directory is the composition from an earlier turn in this session. Apply the request above to it in place - change what it names and keep the rest - then re-render `out.mp4` in this same directory."
    : "Write the composition to `index.html` here and render it to `out.mp4` in this same directory.";
}

// The forms a plan may name, copied from the vocabulary in
// `agents/n8n/prompts/visual_forms.md`. A caller routes on the id, so an id this adapter
// does not know is an error rather than a shape the caller has to guess at. `auto` is not
// here: it is a caller's request to choose, not a form a plan can settle on.
export const PLAN_FORMS = [
  "diagram",
  "story",
  "data",
  "chart",
  "code",
  "timeline",
  "quote",
  "poster",
  "ui",
  "manga",
  "retro",
  "launch",
  "tiles",
  "sketch",
];

// The first JSON object in a model answer, tolerating a code fence and prose around it.
// The scan is brace-matched rather than a slice between the first `{` and the last `}`:
// two objects in one answer would otherwise be cut into one unparsable string.
function firstJsonObject(text) {
  for (let start = text.indexOf("{"); start !== -1; start = text.indexOf("{", start + 1)) {
    let depth = 0;
    let inString = false;
    let escaped = false;
    for (let i = start; i < text.length; i += 1) {
      const ch = text[i];
      if (inString) {
        if (escaped) escaped = false;
        else if (ch === "\\") escaped = true;
        else if (ch === '"') inString = false;
        continue;
      }
      if (ch === '"') inString = true;
      else if (ch === "{") depth += 1;
      else if (ch === "}") {
        depth -= 1;
        if (depth === 0) {
          try {
            const value = JSON.parse(text.slice(start, i + 1));
            if (value && typeof value === "object" && !Array.isArray(value)) return value;
          } catch {
            // not an object after all; the next opening brace may start one
          }
          break;
        }
      }
    }
  }
  return null;
}

const PLAN_FIELDS = ["form", "subject", "question", "scenes", "close", "arc"];
const PLAN_SCENE_FIELDS = ["n", "beat", "line", "device", "motion", "transition"];
const PLAN_CLOSE_FIELDS = ["line"];

function blank(value) {
  if (value === undefined || value === null) return true;
  return typeof value === "string" && !value.trim();
}

function plainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

// The storyboard a plan turn returned, or why it cannot be read. It never throws: a bad
// answer is the caller's signal to retry or ask again, not a failed turn, and the raw
// answer is returned beside the plan so the caller can report what the model wrote.
export function parsePlan(answer) {
  const plan = firstJsonObject(String(answer ?? ""));
  if (!plan) return { plan: null, error: "the answer carries no JSON object" };
  for (const field of PLAN_FIELDS) {
    if (blank(plan[field])) return { plan: null, error: `the plan carries no ${field}` };
  }
  const form = String(plan.form).trim().toLowerCase();
  if (!PLAN_FORMS.includes(form)) {
    return { plan: null, error: `the plan names form "${plan.form}", which is not in the form vocabulary` };
  }
  plan.form = form;
  if (!Array.isArray(plan.scenes) || !plan.scenes.length) {
    return { plan: null, error: "the plan carries no scenes" };
  }
  for (const [index, scene] of plan.scenes.entries()) {
    const label = `scene ${index + 1}`;
    if (!plainObject(scene)) return { plan: null, error: `${label} is not an object` };
    for (const field of PLAN_SCENE_FIELDS) {
      if (blank(scene[field])) return { plan: null, error: `${label} carries no ${field}` };
    }
  }
  if (!plainObject(plan.close)) return { plan: null, error: "the plan's close is not an object" };
  for (const field of PLAN_CLOSE_FIELDS) {
    if (blank(plan.close[field])) return { plan: null, error: `the close carries no ${field}` };
  }
  plan.close.source = String(plan.close.source ?? "").trim();
  return { plan, error: "" };
}

// The plan turn's mechanical instruction, as `turnInstruction` is the authoring turn's:
// the caller's brief carries the content, this says that nothing is authored and what the
// answer must hold. The planning method beside it is `prompts/plan.md`.
export function planInstruction({ format, isIteration } = {}) {
  return [
    `Plan the ${safeFormat(format)} visual the brief above asks for, before it is authored.`,
    "This is a plan turn: write no file, run no render, and call no tool.",
    "Answer with one JSON object and nothing else - no prose around it and no code fence.",
    "One idea per scene: name the intro question the first scene asks, the conclusion the close settles, and the Source the brief cites.",
    isIteration
      ? "This session already holds an authored artifact; plan the change the brief asks for, not a fresh piece."
      : "Plan the storyboard the brief calls for, from the beginning.",
  ].join(" ");
}

// The first form-options answer, or why nothing in it can be used. An option that names
// a form outside the vocabulary, or carries no rationale or sketch, is named and dropped:
// the caller keeps the valid options and reports the rest, rather than guessing at one.
// `firstJsonObject` already tolerates a fence and prose; the contract is one object.
export function parseFormOptions(answer) {
  const value = firstJsonObject(String(answer ?? ""));
  if (!value) return { forms: [], error: "the answer carries no JSON object" };
  if (!Array.isArray(value.options)) return { forms: [], error: "the answer carries no options array" };
  const forms = [];
  const rejected = [];
  const ids = new Set();
  for (const [index, option] of value.options.entries()) {
    const label = plainObject(option) && !blank(option.id) ? `option "${option.id}"` : `option ${index + 1}`;
    if (!plainObject(option)) {
      rejected.push(`${label} is not an object`);
      continue;
    }
    if (blank(option.id)) {
      rejected.push(`${label} carries no id`);
      continue;
    }
    const form = String(option.form ?? "").trim().toLowerCase();
    if (!PLAN_FORMS.includes(form)) {
      rejected.push(`${label} names form "${option.form ?? ""}", which is not in the form vocabulary`);
      continue;
    }
    if (blank(option.why)) {
      rejected.push(`${label} carries no why`);
      continue;
    }
    if (blank(option.sketch)) {
      rejected.push(`${label} carries no sketch`);
      continue;
    }
    const id = String(option.id).trim();
    if (ids.has(id)) {
      rejected.push(`${label} repeats an id`);
      continue;
    }
    ids.add(id);
    forms.push({ id, form, why: String(option.why).trim(), sketch: String(option.sketch).trim() });
  }
  const error = forms.length
    ? (rejected.length ? `rejected ${rejected.join("; ")}` : "")
    : (rejected.length ? `no valid form option: ${rejected.join("; ")}` : "the answer carries no form options");
  return { forms, error };
}

// The storyboard options for a chosen form, or why none is usable. Each plan is validated
// through `parsePlan`; when `form` is given, an option that plans another form is rejected
// too, because the caller asked for storyboards of the form it chose.
export function parsePlanOptions(answer, { form = "" } = {}) {
  const value = firstJsonObject(String(answer ?? ""));
  if (!value) return { plans: [], error: "the answer carries no JSON object" };
  if (!Array.isArray(value.options)) return { plans: [], error: "the answer carries no options array" };
  const wanted = String(form ?? "").trim().toLowerCase();
  const plans = [];
  const rejected = [];
  const ids = new Set();
  for (const [index, option] of value.options.entries()) {
    const label = plainObject(option) && !blank(option.id) ? `plan option "${option.id}"` : `plan option ${index + 1}`;
    if (!plainObject(option)) {
      rejected.push(`${label} is not an object`);
      continue;
    }
    if (blank(option.id)) {
      rejected.push(`${label} carries no id`);
      continue;
    }
    if (!plainObject(option.plan)) {
      rejected.push(`${label} carries no plan object`);
      continue;
    }
    const id = String(option.id).trim();
    if (ids.has(id)) {
      rejected.push(`${label} repeats an id`);
      continue;
    }
    const { plan, error } = parsePlan(JSON.stringify(option.plan));
    if (!plan) {
      rejected.push(`${label}: ${error}`);
      continue;
    }
    if (wanted && plan.form !== wanted) {
      rejected.push(`${label} names form "${plan.form}", not the chosen "${wanted}"`);
      continue;
    }
    ids.add(id);
    plans.push({ id, plan });
  }
  const error = plans.length
    ? (rejected.length ? `rejected ${rejected.join("; ")}` : "")
    : (rejected.length ? `no valid plan option: ${rejected.join("; ")}` : "the answer carries no plan options");
  return { plans, error };
}

function optionCount(count) {
  const n = Number(count);
  return Number.isFinite(n) ? Math.min(3, Math.max(2, Math.round(n))) : 3;
}

// The form-options turn's mechanical instruction, beside `prompts/forms.md`. The caller's
// brief carries the content; this says nothing is authored, what the answer holds, and
// how many options to return.
export function formOptionsInstruction({ format, count = 3 } = {}) {
  const n = optionCount(count);
  return [
    `Propose the forms the ${safeFormat(format)} visual could take, before any storyboard is planned.`,
    "This is a form-options turn: write no file, run no render, and call no tool.",
    "Answer with one JSON object and nothing else - no prose around it and no code fence.",
    `Return up to ${n} options, each {"id","form","why","sketch"}: the id is short and unique, the form is one id from the form vocabulary, why is one line on why this content needs that shape, and sketch is one line on the composition.`,
    "The options must differ in composition, not in wording.",
  ].join(" ");
}

// The plan-options turn's mechanical instruction. The plan method is `prompts/plan.md`,
// which defines the plan object; `prompts/plans.md` defines the wrapper.
export function planOptionsInstruction({ format, form = "", count = 3 } = {}) {
  const n = optionCount(count);
  const chosen = String(form ?? "").trim().toLowerCase();
  return [
    `Plan the ${safeFormat(format)} visual as ${chosen ? `the ${chosen} form` : "the form the content needs"}, before it is authored.`,
    "This is a plan-options turn: write no file, run no render, and call no tool.",
    "Answer with one JSON object and nothing else - no prose around it and no code fence.",
    `Return up to ${n} options, each {"id","plan"}, where plan carries the fields the plan method defines: form, subject, question, scenes, close and arc.`,
    chosen ? `Every option uses the ${chosen} form.` : "Choose the form from the brief for each option.",
    "The options are different storyboards of the same subject, not paraphrases of one.",
  ].join(" ");
}

// Pi names a transcript `<ISO timestamp>_<session id>.jsonl`; the timestamp carries
// no underscore, so the id is everything after the first one. Returns null for a
// name this server did not write, so a foreign file is never swept.
export function sessionIdFromTranscript(name) {
  const match = /^[^_]+_(.+)\.jsonl$/.exec(String(name ?? ""));
  return match ? match[1] : null;
}

// Expired run directories: older than the cutoff, and never the session in flight.
export function expiredRunDirs(entries, { cutoffMs, keep } = {}) {
  return entries
    .filter((e) => Number.isFinite(e.mtimeMs) && e.mtimeMs < cutoffMs && e.name !== keep)
    .map((e) => e.name);
}

// Expired transcripts: older than the cutoff, not the session in flight, and only
// names this server wrote (an unattributable file is left alone).
export function expiredTranscripts(entries, { cutoffMs, keep } = {}) {
  return entries
    .filter((e) => {
      if (!Number.isFinite(e.mtimeMs) || e.mtimeMs >= cutoffMs) return false;
      const id = sessionIdFromTranscript(e.name);
      return id !== null && id !== keep;
    })
    .map((e) => e.name);
}

// The catalog's GitHub server exposes 45 tools including writes; an authoring turn reads
// only these. The server stays hidden, so the rest cannot be reached by name.
export const GITHUB_READ_TOOLS = [
  "search_code",
  "search_repositories",
  "get_file_contents",
  "list_branches",
  "list_commits",
  "list_tags",
];
export const FIRECRAWL_READ_TOOLS = ["firecrawl_search", "firecrawl_scrape", "firecrawl_map"];

// The mcp.json Pi reads from `<agent-dir>/mcp.json`. The URLs come from the deployment,
// never the image: a release name is a cluster fact, and the core admission policy injects
// the two variables into this pod. A variable that is unset omits that server, and the
// instruction names the catalog only when it is there. `direct` is deliberate: codemode is
// the default exposure and would put a third calling convention between the model and a
// handful of read tools the instruction names by name.
export function mcpConfig({ githubUrl = "", firecrawlUrl = "" } = {}) {
  const direct = (tools) => Object.fromEntries(tools.map((tool) => [tool, "direct"]));
  const servers = {};
  if (githubUrl) {
    servers.github = {
      url: githubUrl,
      exposure: "hidden",
      toolExposure: direct(GITHUB_READ_TOOLS),
      description: "Search GitHub repositories for code, examples and documentation",
    };
  }
  if (firecrawlUrl) {
    servers.firecrawl = {
      url: firecrawlUrl,
      exposure: "hidden",
      toolExposure: direct(FIRECRAWL_READ_TOOLS),
      description: "Search and read documentation pages on the web",
    };
  }
  return { mcpServers: servers };
}

// The sampling rate for the converted animation. The caller's declared `frames`
// over `durationSeconds` wins, so a type can be tuned entirely from data (a long,
// slow clip at a low frame rate) without touching the image; otherwise the declared
// `fps`, otherwise a safe default.
export function outputFps({ frames, durationSeconds, fps } = {}) {
  const f = Number(frames);
  const d = Number(durationSeconds);
  const p = Number(fps);
  if (Number.isFinite(f) && f > 0 && Number.isFinite(d) && d > 0) return f / d;
  if (Number.isFinite(p) && p > 0) return p;
  return 8;
}

// The gateway's streaming timeout, and the composer's own settings. Pi reads these
// from `<agent-dir>/settings.json`, which the session server writes beside the
// models.json it already writes; without the file Pi runs on the vendor's defaults
// (idle timeout 300s, three retries) and the composer has no tuned window at all.
//
// The idle timeout is the client's patience for one HTTP response, and the gateway's
// `stream_timeout` is the same wait on the far side of the proxy — for a streaming
// call, the gap between chunks. The client must be the more patient of the two, or it
// abandons an attempt before the gateway reports what happened, and the retry sees a
// different error than the one it was tuned for. Measured 2026-10-16: the gateway's
// 30s per-read timeout killed nine consecutive attempts (run 13648), the composer
// authored nothing, and the caller's artifact fetch answered 404.
//
// The retry numbers are what make a stall survivable: roughly `maxRetries` attempts,
// each up to the idle timeout, separated by an exponential backoff capped at
// `maxAgentDelayMs`. At the defaults that spans the ~12 minutes the measured outage
// lasted, and bounds a dead endpoint at ~17 minutes.
export const DEFAULT_GATEWAY_STREAM_TIMEOUT_MS = 120_000;
export const DEFAULT_RETRY = {
  idleTimeoutMs: 240_000,
  maxRetries: 6,
  baseDelayMs: 5_000,
  maxAgentDelayMs: 60_000,
};

// The object Pi reads as settings.json. Throws rather than writing a file whose idle
// timeout would kill an attempt before the gateway could report why it failed.
export function agentSettings({
  idleTimeoutMs = DEFAULT_RETRY.idleTimeoutMs,
  maxRetries = DEFAULT_RETRY.maxRetries,
  baseDelayMs = DEFAULT_RETRY.baseDelayMs,
  maxAgentDelayMs = DEFAULT_RETRY.maxAgentDelayMs,
  gatewayStreamTimeoutMs = DEFAULT_GATEWAY_STREAM_TIMEOUT_MS,
} = {}) {
  if (!(idleTimeoutMs > gatewayStreamTimeoutMs)) {
    throw new Error(
      `the composer's idle timeout (${idleTimeoutMs}ms) must exceed the gateway's streaming timeout (${gatewayStreamTimeoutMs}ms)`
    );
  }
  return {
    httpIdleTimeoutMs: idleTimeoutMs,
    // Stated rather than left to the vendor's default: a silent change to it would
    // turn the retry window off, which is the whole of this configuration.
    retry: { enabled: true, maxRetries, baseDelayMs, maxAgentDelayMs },
  };
}

function trimNumber(n) {
  return String(Math.round(n * 1000) / 1000);
}

// The container an artifact is in: its frame, its length and its rate. A render whose
// container could not be read is passed as null, which is conformed rather than trusted --
// an unprobed render is not evidence that it matches.
export function containerOf(value) {
  const v = value || {};
  const positive = (n, round) => {
    const x = Number(n);
    return Number.isFinite(x) && x > 0 ? (round ? Math.round(x) : x) : 0;
  };
  return {
    width: positive(v.width, true),
    height: positive(v.height, true),
    durationSeconds: positive(v.durationSeconds),
    fps: positive(v.fps),
  };
}

// What a request declared, in the same terms: the frame and length it named and the rate
// derived from the frame count it budgeted.
function declaredContainer({ fps, width, height, frames, durationSeconds } = {}) {
  return containerOf({ width, height, durationSeconds, fps: outputFps({ frames, durationSeconds, fps }) });
}

// A clip within a frame and a half of the declared length at the declared rate is the same
// clip; a half-second difference is a different one. One tolerance, used by the decision to
// conform and by the note, so the two never disagree.
function lengthTolerance(declared) {
  return declared.fps > 0 ? 1.5 / declared.fps : 0.05;
}

// Whether the engine's render needs conforming to what the request declared. A render whose
// container cannot be read needs it, and a request that declared neither a frame nor a length
// has nothing to conform to.
export function needsConformance(opts = {}, actual = null) {
  const d = declaredContainer(opts);
  if (!d.width && !d.durationSeconds) return false;
  const a = containerOf(actual);
  if (!a.width || !a.height || !a.durationSeconds) return true;
  if (d.width && d.height && (a.width !== d.width || a.height !== d.height)) return true;
  if (d.durationSeconds && Math.abs(a.durationSeconds - d.durationSeconds) > lengthTolerance(d)) return true;
  if (Math.abs(a.fps - d.fps) > 0.01 * d.fps) return true;
  return false;
}

// What the conformance did, in terms a caller can read off the asset: the frame the artifact
// is served at, the frame the composition was authored at where the two differ, and whether
// the render was shorter than the declared length. Nothing extends a render -- a held last
// frame is the frozen tail the composition rules forbid, so a short render is reported.
export function conformanceNote({ opts = {}, actual = null, conformed = false, reason = "" } = {}) {
  const d = declaredContainer(opts);
  const a = containerOf(actual);
  const frame = d.width && d.height ? `${d.width}x${d.height}` : `${a.width}x${a.height}`;
  if (!a.width || !a.height || !a.durationSeconds) {
    return {
      frame,
      authored: "",
      fit: "unknown",
      durationSeconds: d.durationSeconds,
      authoredSeconds: 0,
      short: false,
      reason: reason || "the render's container could not be read",
    };
  }
  const aspect = (c) => c.width / c.height;
  const sameAspect = d.width && d.height ? Math.abs(aspect(a) - aspect(d)) / aspect(d) < 0.01 : true;
  return {
    frame,
    authored: `${a.width}x${a.height}`,
    fit: !conformed ? "none" : sameAspect ? "scale" : "crop",
    durationSeconds: d.durationSeconds,
    authoredSeconds: a.durationSeconds,
    short: Boolean(d.durationSeconds && a.durationSeconds < d.durationSeconds - lengthTolerance(d)),
    reason,
  };
}

// Where a conformed mp4 is written before it replaces the engine's own output: ffmpeg cannot
// read and write one file, and the artifact the engine produced IS out.mp4.
export const CONFORMED_TEMP = "out.conformed.mp4";

// The ffmpeg argument list that turns the engine's out.mp4 into the requested container and
// format inside runDir. `actual` is the engine render's probed container: for mp4 this returns
// null when nothing differs, so a render that already matches is never encoded twice. Every
// kind receives the declared frame, the declared rate (so the frame count is what the type
// budget says it is even if the render ran long) and the declared length, trimmed and never
// extended.
export function transcodeArgs(format, { fps, width, height, frames, durationSeconds, actual = null } = {}) {
  const rate = outputFps({ frames, durationSeconds, fps });
  const w = Math.round(Number(width) || 0);
  const h = Math.round(Number(height) || 0);
  const frameFilters = [];
  if (w > 0 && h > 0) {
    // Increase-then-crop is a plain scale when the aspect already agrees, and fills the
    // declared frame when it does not. A declared frame means filled, so the overflow is
    // cropped rather than letterboxed, and the note names the authored frame.
    frameFilters.push(`scale=${w}:${h}:force_original_aspect_ratio=increase`);
    frameFilters.push(`crop=${w}:${h}`);
  } else if (w > 0) {
    frameFilters.push(`scale=${w}:-2:flags=lanczos`);
  }
  const filters = [`fps=${trimNumber(rate)}`, ...frameFilters];
  const trim = Number.isFinite(durationSeconds) && durationSeconds > 0 ? ["-t", trimNumber(durationSeconds)] : [];
  switch (safeFormat(format)) {
    case "mp4": {
      if (!needsConformance({ fps, width, height, frames, durationSeconds }, actual)) return null;
      return [
        "-y",
        ...trim,
        "-i",
        "out.mp4",
        "-vf",
        filters.join(","),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        CONFORMED_TEMP,
      ];
    }
    case "gif": {
      // Palettegen/paletteuse is what makes a flat-colour diagram GIF small and
      // clean; -loop 0 makes it animate.
      return [
        "-y",
        ...trim,
        "-i",
        "out.mp4",
        "-vf",
        `${filters.join(",")},split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse`,
        "-loop",
        "0",
        "out.gif",
      ];
    }
    case "webp":
      return [
        "-y",
        ...trim,
        "-i",
        "out.mp4",
        "-vcodec",
        "libwebp",
        "-loop",
        "0",
        "-vf",
        filters.join(","),
        "out.webp",
      ];
    case "png":
      // A still is sampled from the END of the render, not its first frame. An
      // authored composition animates its subjects in, so frame 1 is the empty
      // page: measured against a real launch card (2026-10-16, run 13581), frame 1
      // was 4,107 bytes and exactly one colour where the final frame was 251,865
      // bytes and 12,257 colours. The last frame is the settled card whatever the
      // composer's entrance timing, so the artifact does not depend on it. Its frame
      // is conformed like any other artifact's: a still ships the declared frame.
      return [
        "-y",
        "-sseof",
        "-0.1",
        "-i",
        "out.mp4",
        "-frames:v",
        "1",
        ...(frameFilters.length ? ["-vf", frameFilters.join(",")] : []),
        "out.png",
      ];
    case "svg":
      // Authored directly by the composer as a self-contained animated SVG; there is
      // no engine out.mp4 to derive it from, so nothing to transcode.
      return null;
    case "html":
      // The deck is authored directly and its paired out.mp4 is rendered by the
      // composer in the same turn; the deck itself needs no transcode.
      return null;
    default:
      return null;
  }
}


// ---------------------------------------------------------------------------
// Stills: what a critic can look at, produced here because the artifact is here.
//
// The review itself is orchestrated by the studio -- the critic is a call the workflow
// makes, not something this server knows about. What this server owns is the render, so it
// hands back stills of it: a browser screenshot for an authored document, frames for a clip.
// No model call, and no new dependency: Chromium and ffmpeg are what the render already uses.
// The first sample is the opening scene: a clip is briefed to introduce its subject there,
// and a quarter of a 30 s clip (7.5 s) skipped it, so a cold open was never in a still.
// Eight samples sit about three seconds apart, which is what makes the review cover a clip
// rather than sample it: a 30 s clip with its seven scenes was seen in three moments and its
// last frame, so a defect in any other scene reached the human unseen (2026-11-21).
// The server now samples by scene (`stillTimesFor`); these remain the fallback for a caller
// that computed no times.
export const DEFAULT_STILL_OFFSETS = [0.08, 0.2, 0.32, 0.44, 0.56, 0.68, 0.8, 0.92];

// The seek that reaches a clip's final frame. ffmpeg's `-sseof` shorter than one frame
// interval exits 0 and writes NOTHING: on the 8 fps artifact this pipeline derives from 24
// frames over 3 s, `-0.05`/`-0.1`/`-0.11`/`-0.12` wrote no file while `-0.125`/`-0.13`/
// `-0.15`/`-0.2` wrote the frame (measured 2026-10-17, run 13785, with this server's own
// argument list and `spawn` path). One frame interval is therefore the floor, and half a
// second the fallback for a rate nobody reported.
export function settledFrameSeek(fps) {
  const rate = Number(fps);
  if (!Number.isFinite(rate) || rate <= 0) return 0.5;
  return Math.max(1, Math.ceil(1 / rate)) / rate;
}

// Capture one still and report whether it was really made. The output name is fixed and a
// session reuses its run directory, so an earlier turn's file at that name would otherwise
// be served as this turn's still: the target is removed before the capture and the still is
// reported only when the capture wrote bytes, not when it merely exited 0.
export async function captureStill({ dir, output, run } = {}) {
  const target = join(dir, output);
  await rm(target, { force: true });
  try {
    await run();
  } catch {
    return false;
  }
  try {
    const info = await stat(target);
    return info.size > 0;
  } catch {
    return false;
  }
}

// A clip's contact sheet: one tile per second, in one image. The scene-aware stills sample the
// moments a cut defines, so a defect between two of them is invisible; a 30 s clip read as
// 8-12 stills covered a fraction of its seconds. The sheet trades resolution for coverage --
// it shows layout and where a frame is empty, not whether small text is legible, so it
// complements the full-size stills rather than replacing them.
// The grid is near-square (capped at six columns) because a single row is a strip, not a
// sheet: 12 s is the 4x3 sheet verified in the pod, 30 s is 6x5.
export const SHEET_NAME = "review-sheet.jpg";

export function sheetArgs({ runDir, durationSeconds, width = 1280 } = {}) {
  const dir = String(runDir || "").replace(/\/+$/, "");
  const w = Number(width) > 0 ? Number(width) : 1280;
  const seconds = Number(durationSeconds);
  const n = Math.max(1, Math.round(Number.isFinite(seconds) && seconds > 0 ? seconds : 1));
  const cols = Math.min(6, Math.max(1, Math.ceil(Math.sqrt(n))));
  const rows = Math.ceil(n / cols);
  const tileWidth = Math.max(120, Math.floor(w / cols));
  return {
    command: "ffmpeg",
    args: [
      "-y",
      "-i",
      "out.mp4",
      "-vf",
      `fps=1,scale=${tileWidth}:-2,tile=${cols}x${rows}:padding=2:margin=2`,
      "-frames:v",
      "1",
      `${dir}/${SHEET_NAME}`,
    ],
    output: SHEET_NAME,
    mime: "image/jpeg",
  };
}

// The stills to make, per medium. A clip's FINAL frame is always one of them: "nothing fully
// stops" is the rule, so a frozen clip hides in its last frame. An SVG or a deck has no
// composition to render for the svg type (the composer writes no index.html), so Chromium
// screenshots the artifact itself at the declared frame. A still png IS the still, so it
// needs no command -- the artifact is what the critic looks at.
//
// `times` are absolute seconds from `stillTimesFor`; they replace the uniform `offsets` for a
// clip, so the samples follow the render's own cuts. An authored document keeps its own timing
// (a page's clock is advanced by a budget, not seeked), so `times` does not apply there.
export function stillArgs({ format, runDir, width, height, durationSeconds, fps, offsets = DEFAULT_STILL_OFFSETS, times } = {}) {
  const f = safeFormat(format);
  const dir = String(runDir || "").replace(/\/+$/, "");
  const w = Math.max(1, Math.round(Number(width) || 1280));
  const h = Math.max(1, Math.round(Number(height) || (w * 9) / 16));
  if (f === "svg" || f === "html") {
    const page = f === "svg" ? "out.svg" : "out.html";
    const seconds = Number(durationSeconds);
    const total = Number.isFinite(seconds) && seconds > 0 ? seconds : 3;
    // An authored document has to be captured AFTER its entrances run. Chromium screenshots
    // at t=0 otherwise, and the first live review spent a whole fix cycle on an empty frame
    // ("no diagram content is visible", execution 13770). `--virtual-time-budget` advances
    // the page's clock before the capture and costs no wall time (measured: 3,886 bytes at
    // t=0 against 8,011 once a 3 s-delayed element had appeared).
    //
    // An animated SVG is a timeline, so it gets the same shape a clip does -- the declared
    // duration's offsets plus the settled frame. A deck's page is not a timeline: one
    // settled shot is what there is to see.
    const budgets =
      f === "svg"
        ? [0.25, 0.5, 0.75, 1].map((o) => Math.round(total * o * 1000))
        : [Math.max(3000, Math.round(total * 1000))];
    return budgets.map((ms, i) => ({
      command: "chromium",
      args: [
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--hide-scrollbars",
        `--virtual-time-budget=${ms}`,
        `--window-size=${w},${h}`,
        `--screenshot=${dir}/review-${i + 1}.png`,
        `file://${dir}/${page}`,
      ],
      output: `review-${i + 1}.png`,
      mime: "image/png",
    }));
  }
  if (f === "png") return [];
  const artifact = artifactName(f);
  const seconds = Number(durationSeconds);
  const seekTimes =
    Array.isArray(times) && times.length
      ? times.filter((t) => Number.isFinite(t) && t >= 0)
      : Number.isFinite(seconds) && seconds > 0
        ? offsets.map((o) => Math.round(seconds * o * 100) / 100)
        : [];
  const out = seekTimes.map((t, i) => ({
    command: "ffmpeg",
    args: ["-y", "-ss", String(t), "-i", artifact, "-frames:v", "1", "-vf", "scale='min(1280,iw)':-2", `${dir}/review-${i + 1}.jpg`],
    output: `review-${i + 1}.jpg`,
    mime: "image/jpeg",
  }));
  out.push({
    command: "ffmpeg",
    args: ["-y", "-sseof", `-${settledFrameSeek(fps)}`, "-i", artifact, "-frames:v", "1", "-vf", "scale='min(1280,iw)':-2", `${dir}/review-final.jpg`],
    output: "review-final.jpg",
    mime: "image/jpeg",
  });
  return out;
}

// ---------------------------------------------------------------------------
// The deterministic gate. The engine and ffmpeg already decide the perceptual facts
// (overlaps, freezes, black frames, cut structure); this adapter is the only place that
// can run them against the bytes it delivered. Everything here is a pure parser of what
// those processes wrote: session-server.mjs spawns them, so a report shape can be tested
// without a browser or an encoder.
//
// A gate that did not run is not a pass: `ran: false` with a reason is what the asset
// records, and the workflow treats it as absent evidence rather than as clean.

// A pathological report must not bloat the execution record; errors and warnings come first.
export const CHECK_FINDING_CAP = 25;

// The sections of `hyperframes check --json` that expose `findings`. A release that renames
// or drops one contributes nothing rather than failing the parse.
const CHECK_SECTIONS = ["lint", "runtime", "layout", "motion", "contrast", "craft", "audio", "hdr"];
const CHECK_SEVERITY_ORDER = { error: 0, warning: 1, info: 2 };

// The engine the image pins is 0.9.1: it has no `--no-cache` (the parser reads it as
// `--cache`, "Unknown flag", exit 2) and no `--budget`, and its render-ready wait defaults to
// 10 s, which a 30 s composition does not settle in. The invocation lives here so the
// argument list is a tested value rather than a line in the server.
export const CHECK_TIMEOUT_MS = 45_000;
export function checkArgs(dir) {
  return ["check", dir, "--json", "--at-transitions", `--timeout=${CHECK_TIMEOUT_MS}`];
}

// A severity this parser does not recognise is kept as a warning: an unknown level is more
// likely a louder finding than a quiet one, and dropping it would hide the finding entirely.
function checkSeverity(value) {
  const s = String(value ?? "").toLowerCase();
  if (s === "error" || s === "err" || s === "fatal" || s === "1") return "error";
  if (s === "info" || s === "note" || s === "hint" || s === "3") return "info";
  return "warning";
}

function sectionFindings(section) {
  if (Array.isArray(section)) return section;
  if (section && typeof section === "object" && Array.isArray(section.findings)) return section.findings;
  return [];
}

// A real finding carries `bbox` as `{x,y,width,height}`; some shapes carry `[x,y,w,h]`. Both
// normalize to `{x,y,w,h}` so a consumer never branches on the report's shape.
function bboxOf(value) {
  if (Array.isArray(value)) {
    if (value.length < 4) return null;
    const [x, y, w, h] = value.slice(0, 4).map(Number);
    return [x, y, w, h].every(Number.isFinite) ? { x, y, w, h } : null;
  }
  if (value && typeof value === "object") {
    const box = {
      x: Number(value.x),
      y: Number(value.y),
      w: Number(value.width ?? value.w),
      h: Number(value.height ?? value.h),
    };
    return Object.values(box).every(Number.isFinite) ? box : null;
  }
  return null;
}

// The element identity a ledger entry keys on. A real finding names no `dataId`; it carries the
// element's own `data-*` attributes, whose `id` is the stable name (the rest as a capped JSON
// string, so a selector that moved still has something to match). An element with no `data-*`
// attributes at all has no identity here: `"{}"` is not one.
function dataIdOf(raw) {
  if (raw.dataId != null && raw.dataId !== "") return String(raw.dataId);
  const attributes = raw.dataAttributes;
  if (!attributes || typeof attributes !== "object" || !Object.keys(attributes).length) return "";
  if (attributes.id != null && attributes.id !== "") return String(attributes.id);
  try {
    const json = JSON.stringify(attributes);
    return json.length > 120 ? `${json.slice(0, 117)}...` : json;
  } catch {
    return "";
  }
}

// `hyperframes check --json` writes one envelope. A non-zero exit still carries it, so the
// caller parses the bytes it got; only an unreadable body is `ran: false`.
export function parseCheckReport(stdout) {
  const empty = { ran: false, ok: false, reason: "the check report could not be read", counts: { error: 0, warning: 0, info: 0 }, findings: [] };
  const text = String(stdout ?? "").trim();
  if (!text) return empty;
  let report = null;
  // The engine can print a banner before the envelope, so the outermost object is the fallback.
  for (const candidate of [text, text.slice(text.indexOf("{"), text.lastIndexOf("}") + 1)]) {
    if (!candidate) continue;
    try {
      report = JSON.parse(candidate);
      break;
    } catch {
      // try the next shape
    }
  }
  if (!report || typeof report !== "object" || Array.isArray(report)) return empty;

  const all = [];
  for (const name of CHECK_SECTIONS) {
    for (const raw of sectionFindings(report[name])) {
      if (!raw || typeof raw !== "object") continue;
      all.push({
        section: name,
        code: String(raw.code ?? ""),
        severity: checkSeverity(raw.severity),
        selector: String(raw.selector ?? ""),
        message: String(raw.message ?? ""),
        fixHint: String(raw.fixHint || ""),
        dataId: dataIdOf(raw),
        time: Number.isFinite(Number(raw.time)) ? Number(raw.time) : null,
        bbox: bboxOf(raw.bbox),
      });
    }
  }
  const counts = { error: 0, warning: 0, info: 0 };
  for (const finding of all) counts[finding.severity] += 1;
  const findings = all
    .map((finding, index) => ({ finding, index }))
    .sort((a, b) => CHECK_SEVERITY_ORDER[a.finding.severity] - CHECK_SEVERITY_ORDER[b.finding.severity] || a.index - b.index)
    .slice(0, CHECK_FINDING_CAP)
    .map((entry) => entry.finding);
  return { ran: true, ok: report.ok === true, reason: "", counts, findings };
}

function escapedKey(key) {
  return key.replace(/\./g, "\\.");
}

function timeValues(stderr, key) {
  const values = [];
  for (const match of String(stderr ?? "").matchAll(new RegExp(`${escapedKey(key)}:\\s*(-?\\d+(?:\\.\\d+)?)`, "g"))) {
    const t = Number(match[1]);
    if (Number.isFinite(t) && t >= 0) values.push(t);
  }
  return values.sort((a, b) => a - b);
}

// A detected span pairs the k-th start with the k-th end. A video that ends frozen writes no
// end, so the span closes at the artifact's duration instead of being dropped.
function spansOf(starts, ends, durationSeconds) {
  const out = [];
  for (let i = 0; i < starts.length; i += 1) {
    const start = starts[i];
    const end = ends[i] ?? (durationSeconds > start ? durationSeconds : null);
    if (end === null || end < start) continue;
    out.push({ start, end });
  }
  return out;
}

// What one `-f null` pass reported: freeze and black spans, and the cut times. Both the plain
// `freeze_start: 1.2` and the `lavfi.freezedetect.freeze_start: 1.2` form match the same key.
// Cuts closer than 0.2 s are one cut: a hard cut scores on adjacent frames.
//
// `pix_th=0.10` false-positived on the brand's own dark surface: `lips-60` reported seven
// black spans (0-0.47 s, 4.3-5.27 s, ...) and `lips-j5n6da` likewise, while both report zero
// at `pix_th=0.02:pic_th=0.99` and a synthetic 1 s true-black clip still reports 0-1 s.
export const MOTION_FILTER = "freezedetect=n=0.003:d=0.5,blackdetect=d=0.1:pix_th=0.02:pic_th=0.99";

export function parseMotionSignals(stderr, durationSeconds) {
  const total = Number(durationSeconds);
  const duration = Number.isFinite(total) && total > 0 ? total : 0;
  const freeze = spansOf(timeValues(stderr, "freeze_start"), timeValues(stderr, "freeze_end"), duration);
  const black = spansOf(timeValues(stderr, "black_start"), timeValues(stderr, "black_end"), duration);
  const cuts = [];
  for (const t of timeValues(stderr, "lavfi.scd.time")) {
    if (duration && t >= duration) continue;
    if (cuts.length && t - cuts.at(-1) < 0.2) continue;
    cuts.push(t);
  }
  // Scenes are the intervals between cuts. No cut means nothing was detected, which is the
  // fallback case `stillTimesFor` handles; a single "scene" is not assumed.
  const scenes = [];
  if (cuts.length && duration) {
    const bounds = [0, ...cuts, duration];
    for (let i = 0; i + 1 < bounds.length; i += 1) {
      if (bounds[i + 1] > bounds[i]) scenes.push({ start: bounds[i], end: bounds[i + 1] });
    }
  } else if (cuts.length) {
    for (let i = 0; i < cuts.length; i += 1) {
      const start = i === 0 ? 0 : cuts[i - 1];
      if (cuts[i] > start) scenes.push({ start, end: cuts[i] });
    }
  }
  return { freeze, black, cuts, scenes, scenesSeen: scenes.length };
}

// Evenly spaced members of a list, so a cap drops samples across the whole render rather than
// truncating its tail.
function evenPick(list, count) {
  if (count <= 0) return [];
  if (list.length <= count) return [...list];
  if (count === 1) return [list[Math.floor(list.length / 2)]];
  const out = [];
  for (let i = 0; i < count; i += 1) out.push(list[Math.round((i * (list.length - 1)) / (count - 1))]);
  return out;
}

const roundTime = (t) => Math.round(t * 1000) / 1000;

// The times to sample a clip at. Scene midpoints come first because they are the structure the
// content has; the frames straddling a cut show the transition itself (where an arrow drifts or
// a panel overlaps). Over the cap, midpoints are kept evenly and the straddles are dropped.
//
// No detected cut is not "one scene": the 17510 render is a single continuous animation with no
// hard cut at all, so a sparse fixed list sampled it eight times across thirty seconds. The
// fallback is a uniform grid of about one still per 2.5 s (at least eight, never more than the
// cap), which keeps a cutless clip covered without pretending it has scenes.
export function stillTimesFor(signals, durationSeconds, { max = 12, fps } = {}) {
  const total = Number(durationSeconds);
  const duration = Number.isFinite(total) && total > 0 ? total : 0;
  const cap = Number.isFinite(Number(max)) && Number(max) > 0 ? Math.floor(Number(max)) : 12;
  const rate = Number(fps) > 0 ? Number(fps) : 30;
  const cutTimes = (signals?.cuts ?? []).filter((t) => Number.isFinite(t) && t > 0 && (!duration || t < duration));
  const scenes = (signals?.scenes ?? []).filter((s) => Number.isFinite(s?.start) && Number.isFinite(s?.end) && s.end > s.start);

  if (!cutTimes.length) {
    if (!duration) return { times: [], scenesCovered: 0 };
    const count = Math.min(Math.max(Math.ceil(duration / 2.5), 8), cap);
    const times = Array.from({ length: count }, (_, i) => roundTime(((i + 0.5) / count) * duration));
    return { times, scenesCovered: 0 };
  }

  const midpoints = evenPick(
    scenes.map((s) => roundTime((s.start + s.end) / 2)),
    cap
  );
  const times = [...midpoints];
  let room = cap - times.length;
  for (const cut of evenPick(cutTimes, Math.ceil(room / 2))) {
    for (const t of [cut - 1 / rate, cut + 1 / rate]) {
      if (room <= 0) break;
      if (t <= 0 || (duration && t >= duration)) continue;
      times.push(roundTime(t));
      room -= 1;
    }
  }
  // Straddles can land on a midpoint (a very short scene); one frame is one still.
  const unique = [...new Set(times)].sort((a, b) => a - b);
  return { times: unique.slice(0, cap), scenesCovered: midpoints.length };
}

// The geometry of one connector, in composition pixels. The line leaves the facing edge of
// `from` and lands on the facing edge of `to`, each inset by a gap, so the two boxes never
// touch the stroke. The head is a triangle at the target end and the line stops at its base.
//
// The same arithmetic is inlined in runtime/connectors.js, which runs in the browser with no
// imports; the two implementations are kept identical on purpose (the unit test checks this
// one, the DOM dump checks the other).
const CONNECTOR_GAP = 8;
const CONNECTOR_HEAD_LENGTH = 14;
const CONNECTOR_HEAD_WIDTH = 10;

function rectBox(value) {
  if (!value || typeof value !== "object") return null;
  const box = { x: Number(value.x), y: Number(value.y), w: Number(value.w), h: Number(value.h) };
  if (!Object.values(box).every(Number.isFinite) || box.w <= 0 || box.h <= 0) return null;
  return box;
}

const round2 = (n) => Math.round(n * 100) / 100;

export function connectorGeometry(rects, { from, to, head = true } = {}) {
  const a = rectBox(rects?.from);
  const b = rectBox(rects?.to);
  if (!a) return { ok: false, reason: `the ${from || "from"} box is missing` };
  if (!b) return { ok: false, reason: `the ${to || "to"} box is missing` };
  // Overlap is the one case where "the facing edge" is not defined; the critic sees the
  // overlap itself, and drawing a line across it would only add noise.
  if (a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h) {
    return { ok: false, reason: `the ${from || "from"} box and the ${to || "to"} box overlap` };
  }

  const acx = a.x + a.w / 2;
  const acy = a.y + a.h / 2;
  const bcx = b.x + b.w / 2;
  const bcy = b.y + b.h / 2;
  const dx = bcx - acx;
  const dy = bcy - acy;
  let x1;
  let y1;
  let x2;
  let y2;
  let dirX = 0;
  let dirY = 0;
  if (Math.abs(dx) >= Math.abs(dy)) {
    dirX = dx >= 0 ? 1 : -1;
    x1 = dirX > 0 ? a.x + a.w + CONNECTOR_GAP : a.x - CONNECTOR_GAP;
    x2 = dirX > 0 ? b.x - CONNECTOR_GAP : b.x + b.w + CONNECTOR_GAP;
    y1 = acy;
    y2 = bcy;
  } else {
    dirY = dy >= 0 ? 1 : -1;
    y1 = dirY > 0 ? a.y + a.h + CONNECTOR_GAP : a.y - CONNECTOR_GAP;
    y2 = dirY > 0 ? b.y - CONNECTOR_GAP : b.y + b.h + CONNECTOR_GAP;
    x1 = acx;
    x2 = bcx;
  }

  const span = dirX ? dirX * (x2 - x1) : dirY * (y2 - y1);
  // Two boxes closer than the two gaps leave no line: it collapses to the tip and the head
  // still marks the target edge rather than pointing past it.
  const back = head ? Math.min(CONNECTOR_HEAD_LENGTH, Math.max(0, span)) : 0;
  const tipX = round2(x2);
  const tipY = round2(y2);
  const lineX = round2(x2 - dirX * back);
  const lineY = round2(y2 - dirY * back);
  const halfWidth = CONNECTOR_HEAD_WIDTH / 2;
  const headPoints = head
    ? {
        points: [
          [tipX, tipY],
          [round2(lineX - dirY * halfWidth), round2(lineY - dirX * halfWidth)],
          [round2(lineX + dirY * halfWidth), round2(lineY + dirX * halfWidth)],
        ]
          .map(([x, y]) => `${x},${y}`)
          .join(" "),
      }
    : null;
  return { x1: round2(x1), y1: round2(y1), x2: lineX, y2: lineY, head: headPoints, ok: true };
}

// The status the helper left on the document, and the lines it actually drew. A connector
// declared but not drawn is the 17510 defect ("nine connectors never drew") in one number.
export function connectorsVerification(domText, declarations) {
  const declared = Array.isArray(declarations) ? declarations.length : 0;
  const text = String(domText ?? "");
  const status = /data-hf-connectors=(["'])([^"']*)\1/.exec(text);
  const drawn = (text.match(/data-connector=(?:"[^"]*"|'[^']*')/g) ?? []).length;
  if (!status) {
    if (!declared) return { declared, drawn: 0, errors: [] };
    return { declared, drawn: 0, errors: [{ id: "*", reason: "the connector helper did not run" }] };
  }
  const value = status[2].trim();
  if (value === "ok") return { declared, drawn, errors: [] };
  const ids = value.replace(/^error:?/, "").split(",").map((id) => id.trim()).filter(Boolean);
  if (!ids.length) {
    return { declared, drawn, errors: [{ id: "*", reason: "the connector helper reported an error without naming a declaration" }] };
  }
  return { declared, drawn, errors: ids.map((id) => ({ id, reason: "the connector's element was not found" })) };
}
