// Pure helpers for the pi-render session server: request/artifact path safety and
// the output-format post-processing. Kept out of session-server.mjs so they can be
// unit-tested with `node --test` without starting the HTTP server.

import { basename, join, normalize, sep } from "node:path";
import { copyFile, rm, stat } from "node:fs/promises";
import { createHash } from "node:crypto";

// The shape session-server.mjs accepts for session_id: a run identifier that is
// safe as a single path segment. `.` and `..` are excluded even though the
// character class would allow them — as a directory segment they escape the runs
// directory.
export const SESSION_ID_RE = /^(?!\.{1,2}$)[a-zA-Z0-9._-]{1,80}$/;

// A produced artifact name. Deliberately narrower than session_id: only the names
// this server writes are ever served.
const ARTIFACT_NAME_RE = /^out\.(mp4|gif|webp|png|svg|html)$/;
// An article turn writes two files. They are served on the same route as a render's
// artifact because they are written by this server's own turn, into the same run
// directory; a name outside this list is still refused.
const ARTICLE_ARTICLE_NAME = "article.md";
const ARTICLE_LEDGER_NAME = "sources.json";
// The stills of a render, served beside it: the studio's critic fetches one of these. They
// are the only other names this server writes, so the route stays a whitelist rather than a
// path a caller can steer.
const STILL_NAME_RE = /^review-(final|\d+)\.(png|jpg)$/;

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

// The vendored GSAP the composition loads. It lives in the image at
// /opt/hyperframes/vendor/gsap.min.js, but the served document resolves a sibling
// path: an absolute filesystem path 404s at render time (hit live). Staging it next
// to the composition as gsap.min.js is what makes `<script src="gsap.min.js">` work.
export const VENDOR_DIR = process.env.SYMPOZIUM_VENDOR_DIR || "/opt/hyperframes/vendor";
export const VENDOR_ASSETS = ["gsap.min.js"];

// Copy the vendored assets into a run directory before the composer runs. Best effort:
// a missing asset is a render-time failure the composer reports, not a reason to fail
// the turn. Returns the names staged.
export async function stageVendorAssets(dir, vendorDir = VENDOR_DIR) {
  const staged = [];
  for (const name of VENDOR_ASSETS) {
    try {
      await copyFile(join(vendorDir, name), join(dir, name));
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
  if (
    typeof name !== "string" ||
    (!ARTIFACT_NAME_RE.test(name) && !STILL_NAME_RE.test(name) && !isArticleArtifact(name))
  ) {
    return null;
  }
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
  if (name === ARTICLE_ARTICLE_NAME) return "text/markdown; charset=utf-8";
  if (name === ARTICLE_LEDGER_NAME) return "application/json; charset=utf-8";
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
export const DEFAULT_STILL_OFFSETS = [0.1, 0.4, 0.7];

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

// The stills to make, per medium. A clip's FINAL frame is always one of them: "nothing fully
// stops" is the rule, so a frozen clip hides in its last frame. An SVG or a deck has no
// composition to render for the svg type (the composer writes no index.html), so Chromium
// screenshots the artifact itself at the declared frame. A still png IS the still, so it
// needs no command -- the artifact is what the critic looks at.
export function stillArgs({ format, runDir, width, height, durationSeconds, fps, offsets = DEFAULT_STILL_OFFSETS } = {}) {
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
  const times = Number.isFinite(seconds) && seconds > 0 ? offsets.map((o) => Math.round(seconds * o * 100) / 100) : [];
  const out = times.map((t, i) => ({
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
// Profiles: one adapter image serves a render and an article.
//
// The profile picks the instruction file and the artifact contract. `render` is the
// default so an existing caller that sends no profile keeps its behaviour exactly;
// an unknown profile is refused by name rather than silently served as a render,
// because a typo in a caller would otherwise author the wrong kind of thing.

export const PROFILES = {
  render: { instruction: "authoring.md", artifacts: "render" },
  article: { instruction: "article.md", artifacts: "article" },
};
export const DEFAULT_PROFILE = "render";

export function parseProfile(value) {
  if (value === undefined || value === null || value === "") return DEFAULT_PROFILE;
  if (typeof value === "string" && Object.prototype.hasOwnProperty.call(PROFILES, value)) return value;
  throw new Error(
    `unknown profile ${JSON.stringify(value)}; expected ${Object.keys(PROFILES).join(" or ")}`
  );
}

// The two files an article turn writes, and the only article names the artifact route
// serves. A render's names are unchanged and still refused here.
export const ARTICLE_NAME = ARTICLE_ARTICLE_NAME;
export const LEDGER_NAME = ARTICLE_LEDGER_NAME;

export function isArticleArtifact(name) {
  return name === ARTICLE_ARTICLE_NAME || name === ARTICLE_LEDGER_NAME;
}

// The hosts the fleet writes about. The image default is what a session runs with
// when the caller names none; the caller's list wins because it is a property of the
// row's subject, not of the code.
export const DEFAULT_ARTICLE_SOURCE_HOSTS = [
  "github.com",
  "raw.githubusercontent.com",
  "datahub-local.alvsanand.com",
];

export function parseSourceHosts(value, fallback = DEFAULT_ARTICLE_SOURCE_HOSTS) {
  const list = Array.isArray(value) ? value : String(value ?? "").split(/[,\s]+/);
  const hosts = list
    .map((host) => String(host).trim().toLowerCase())
    .filter(Boolean)
    .map((host) => host.replace(/^https?:\/\//, "").replace(/\/.*$/, ""));
  return hosts.length ? [...new Set(hosts)] : [...fallback];
}

// The allowlist as the agent reads it, substituted into the instruction. The proxy,
// not this line, is what enforces it.
export function fillSourceHosts(text, hosts = DEFAULT_ARTICLE_SOURCE_HOSTS) {
  return String(text ?? "").replaceAll("{{ ARTICLE_SOURCE_HOSTS }}", hosts.join(", "));
}

// A fenced block's identity is its text with every whitespace run collapsed: the
// docs render the same YAML with other indentation and other blank lines, and a
// line-level match would accept `apiVersion: v1` as evidence for a whole manifest.
export function normaliseBlock(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim();
}

export function sha256Hex(value) {
  return createHash("sha256").update(String(value ?? ""), "utf8").digest("hex");
}

// Every fenced block in a Markdown body, with its info string. An unterminated fence
// is not a block: it is prose that was cut off, and the article gate rejects it as
// such rather than treating half a manifest as quoted.
export function extractFencedBlocks(markdown) {
  const blocks = [];
  const re = /^[ \t]*```([^\n`]*)\n([\s\S]*?)^[ \t]*```[ \t]*$/gm;
  let match;
  while ((match = re.exec(String(markdown ?? ""))) !== null) {
    const block = match[2].replace(/\n$/, "");
    if (block.trim()) blocks.push({ lang: match[1].trim(), block });
  }
  return blocks;
}

// The ledger's shape, in one place. A session may write either `{sources: [...]}` or
// a bare array; the server always rewrites it as the object, which is what n8n and
// the sheet column read. Unknown fields are kept so a server rewrite does not drop a
// field a later reader added.
export function normaliseLedgerEntry(entry) {
  const e = entry && typeof entry === "object" ? entry : {};
  const validated = String(e.validated ?? "none").trim().toLowerCase();
  return {
    ...e,
    block: String(e.block ?? ""),
    url: String(e.url ?? "").trim(),
    validated: validated === "dry-run" ? "dry-run" : "none",
    validation_error: String(e.validation_error ?? ""),
  };
}

export function parseLedger(text) {
  let data;
  try {
    data = typeof text === "string" ? JSON.parse(text) : text;
  } catch (err) {
    throw new Error(`sources.json is not valid JSON: ${err?.message ?? err}`);
  }
  const list = Array.isArray(data) ? data : data && Array.isArray(data.sources) ? data.sources : null;
  if (!list) throw new Error("sources.json carries no sources array");
  return list.map(normaliseLedgerEntry).filter((entry) => entry.block.trim() !== "");
}

export function serialiseLedger(sources) {
  return `${JSON.stringify({ sources: sources.map(normaliseLedgerEntry) }, null, 2)}\n`;
}

// ---------------------------------------------------------------------------
// What the server will fetch. The allowlist is the first gate; the address checks
// are the second, because an allowlisted name that resolves to a private address is
// the SSRF shape the design calls out. Literal addresses and local names are refused
// without a DNS answer, and every redirect target is checked again.

const PRIVATE_V4 = [
  [/^0\./, 8],
  [/^10\./, 8],
  [/^100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\./, 10],
  [/^127\./, 8],
  [/^169\.254\./, 16],
  [/^172\.(1[6-9]|2[0-9]|3[01])\./, 12],
  [/^192\.168\./, 16],
];

function isPrivateIPv4(host) {
  const parts = host.split(".");
  if (parts.length !== 4 || parts.some((p) => !/^\d{1,3}$/.test(p) || Number(p) > 255)) return false;
  return PRIVATE_V4.some(([re]) => re.test(host));
}

function isPrivateIPv6(host) {
  const h = host.toLowerCase();
  if (h.includes(".")) {
    // An IPv4-mapped or IPv4-embedded form: the trailing dotted quad is the address.
    const tail = h.slice(h.lastIndexOf(":") + 1);
    if (isPrivateIPv4(tail)) return true;
  }
  if (h === "::1" || h === "::") return true;
  if (/^fe[89ab]/.test(h)) return true; // link-local fe80::/10
  if (/^f[cd]/.test(h)) return true; // unique local fc00::/7
  return false;
}

export function isBlockedHostname(value) {
  const host = String(value ?? "").trim().toLowerCase().replace(/^\[|\]$/g, "").replace(/\.$/, "");
  if (!host) return true;
  if (host === "localhost" || host.endsWith(".localhost")) return true;
  return isPrivateIPv4(host) || isPrivateIPv6(host);
}

// Only the loopback exemption from the address policy, for the one caller that must reach
// a stub on its own machine. It does not extend to link-local or private ranges: an
// allowed loopback is not a reason to let a redirect reach 169.254.169.254.
export function isLoopbackHostname(value) {
  const host = String(value ?? "").trim().toLowerCase().replace(/^\[|\]$/g, "");
  if (host === "localhost" || host.endsWith(".localhost")) return true;
  if (host === "::1") return true;
  return /^127\./.test(host);
}

export function hostAllowed(host, allowedHosts = []) {
  const name = String(host ?? "").trim().toLowerCase();
  return allowedHosts.some((allowed) => {
    const a = String(allowed).trim().toLowerCase();
    return a !== "" && (name === a || name.endsWith(`.${a}`));
  });
}

// Why this URL may not be fetched, or null when it may. Every reason is a phrase a
// log line and a test can name.
export function sourceUrlRefusal(value, { allowedHosts = [], requireHttps = true, allowLoopback = false } = {}) {
  let url;
  try {
    url = new URL(String(value ?? ""));
  } catch {
    return "not a URL";
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") return `scheme ${url.protocol} is not http or https`;
  if (requireHttps && url.protocol !== "https:") return "not https";
  if (url.username || url.password) return "carries credentials";
  const host = url.hostname.toLowerCase().replace(/^\[|\]$/g, "");
  const blocked = allowLoopback && isLoopbackHostname(host) ? false : isBlockedHostname(host);
  if (blocked) return `host ${host} is private or loopback`;
  if (!hostAllowed(host, allowedHosts)) return `host ${host} is not a declared source host`;
  return null;
}

// The page's own text for a block, found as a contiguous run of the block's tokens
// with any whitespace between them. Returns null when the page does not carry it.
export function findExcerpt(body, block) {
  const tokens = normaliseBlock(block).split(" ").filter(Boolean);
  if (!tokens.length) return null;
  const escape = (token) => token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(tokens.map(escape).join("\\s+"));
  const match = re.exec(String(body ?? ""));
  return match ? match[0] : null;
}

export const DEFAULT_LEDGER_FETCH = {
  maxBytes: 2_000_000,
  maxRedirects: 3,
  timeoutMs: 15_000,
};

async function readCapped(res, maxBytes) {
  if (!res.body || typeof res.body.getReader !== "function") {
    const buf = Buffer.from(await res.arrayBuffer());
    return buf.subarray(0, maxBytes);
  }
  const reader = res.body.getReader();
  const chunks = [];
  let size = 0;
  while (size < maxBytes) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = Buffer.from(value);
    const room = maxBytes - size;
    chunks.push(chunk.subarray(0, room));
    size += Math.min(chunk.length, room);
    if (chunk.length > room) {
      try {
        await reader.cancel();
      } catch {
        // the body is already capped; cancelling best effort
      }
      break;
    }
  }
  return Buffer.concat(chunks);
}

// Fetch one URL with the policy's gates applied at the start and at every redirect.
// Returns `{body}` or `{refusal}`; a status is reported, never thrown, so the caller
// can name it in the drop reason.
async function fetchLedgerUrl(url, opts) {
  const {
    fetchUrl = fetch,
    allowedHosts = [],
    requireHttps = true,
    allowLoopback = false,
    maxBytes = DEFAULT_LEDGER_FETCH.maxBytes,
    maxRedirects = DEFAULT_LEDGER_FETCH.maxRedirects,
    timeoutMs = DEFAULT_LEDGER_FETCH.timeoutMs,
  } = opts;
  let current = String(url);
  for (let hop = 0; hop <= maxRedirects; hop += 1) {
    const refusal = sourceUrlRefusal(current, { allowedHosts, requireHttps, allowLoopback });
    if (refusal) return { refusal };
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    let res;
    try {
      res = await fetchUrl(current, { signal: controller.signal, redirect: "manual" });
    } catch (err) {
      clearTimeout(timer);
      return { refusal: `did not answer: ${err?.message ?? err}` };
    }
    clearTimeout(timer);
    if (res.status >= 300 && res.status < 400) {
      const location = res.headers.get("location");
      if (!location) return { refusal: `redirect ${res.status} without a location` };
      current = new URL(location, current).toString();
      continue;
    }
    if (!res.ok) return { refusal: `answered HTTP ${res.status}` };
    const body = await readCapped(res, maxBytes);
    return { status: res.status, body: body.toString("utf8"), bodyBytes: body.length };
  }
  return { refusal: `more than ${maxRedirects} redirects` };
}

// Verify a ledger against the pages it cites. An entry whose URL does not answer is
// dropped: the server, not the model, decides whether a source exists. A URL that
// answers but does not carry the block keeps its entry with `found: false`, which the
// n8n gate rejects with the block and the URL in the reason -- the two failures are
// different findings and only one of them is about the URL.
export async function revalidateLedger(entries, opts = {}) {
  const sources = (Array.isArray(entries) ? entries : []).map(normaliseLedgerEntry);
  const fetched = new Map();
  const dropped = [];
  const kept = [];
  for (const entry of sources) {
    if (!entry.url) {
      dropped.push({ block: entry.block, url: entry.url, reason: "no url" });
      continue;
    }
    if (!fetched.has(entry.url)) {
      fetched.set(entry.url, await fetchLedgerUrl(entry.url, opts));
    }
    const page = fetched.get(entry.url);
    if (page.refusal) {
      dropped.push({ block: entry.block, url: entry.url, reason: page.refusal });
      continue;
    }
    const excerpt = findExcerpt(page.body, entry.block);
    kept.push({
      ...entry,
      found: excerpt !== null,
      sha256: excerpt !== null ? sha256Hex(normaliseBlock(entry.block)) : "",
      excerpt: excerpt ?? "",
      status: page.status,
      body_sha256: sha256Hex(page.body),
    });
  }
  return { sources: kept, dropped };
}

// The mechanical half of an article turn: where to write and whether the turn
// authors or corrects. The correction names the files already in the directory so a
// retry edits them instead of paying for a fresh read of every source.
export function articleTurnInstruction({ isIteration } = {}) {
  if (isIteration) {
    return (
      "`article.md` and `sources.json` in this directory are the article from an earlier " +
      "turn in this session. Apply the request above to the article in place - change what " +
      "it names and keep the rest, re-reading only what it names - and write both files again."
    );
  }
  return (
    "Write the article to `article.md` in this directory and its source ledger to " +
    "`sources.json` here. Nothing is published from this turn; the caller fetches both files."
  );
}
