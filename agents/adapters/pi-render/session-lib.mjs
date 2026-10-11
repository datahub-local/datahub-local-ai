// Pure helpers for the pi-render session server: request/artifact path safety and
// the output-format post-processing. Kept out of session-server.mjs so they can be
// unit-tested with `node --test` without starting the HTTP server.

import { basename, join, normalize, sep } from "node:path";
import { copyFile } from "node:fs/promises";

// The shape session-server.mjs accepts for session_id: a run identifier that is
// safe as a single path segment. `.` and `..` are excluded even though the
// character class would allow them — as a directory segment they escape the runs
// directory.
export const SESSION_ID_RE = /^(?!\.{1,2}$)[a-zA-Z0-9._-]{1,80}$/;

// A produced artifact name. Deliberately narrower than session_id: only the names
// this server writes are ever served.
const ARTIFACT_NAME_RE = /^out\.(mp4|gif|webp|png|svg|html)$/;

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
  if (typeof name !== "string" || !ARTIFACT_NAME_RE.test(name)) return null;
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

function trimNumber(n) {
  return String(Math.round(n * 1000) / 1000);
}

// The ffmpeg argument list that turns the engine's out.mp4 into the requested
// format inside runDir. Returns null when no transcode is needed (mp4). A declared
// duration trims the input to that length, so the frame count is what the type
// budget says it is even if the agent's render ran long.
export function transcodeArgs(format, { fps, width, frames, durationSeconds } = {}) {
  const rate = outputFps({ frames, durationSeconds, fps });
  const filters = [`fps=${trimNumber(rate)}`];
  if (Number.isFinite(width) && width > 0) filters.push(`scale=${width}:-2:flags=lanczos`);
  const trim = Number.isFinite(durationSeconds) && durationSeconds > 0 ? ["-t", trimNumber(durationSeconds)] : [];
  switch (safeFormat(format)) {
    case "mp4":
      return null;
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
      return ["-y", "-i", "out.mp4", "-frames:v", "1", "out.png"];
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
