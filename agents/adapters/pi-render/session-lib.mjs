// Pure helpers for the pi-render session server: request/artifact path safety and
// the output-format post-processing. Kept out of session-server.mjs so they can be
// unit-tested with `node --test` without starting the HTTP server.

import { basename, join, normalize, sep } from "node:path";

// The shape session-server.mjs accepts for session_id: a run identifier that is
// safe as a single path segment. `.` and `..` are excluded even though the
// character class would allow them — as a directory segment they escape the runs
// directory.
export const SESSION_ID_RE = /^(?!\.{1,2}$)[a-zA-Z0-9._-]{1,80}$/;

// A produced artifact name. Deliberately narrower than session_id: only the names
// this server writes are ever served.
const ARTIFACT_NAME_RE = /^out\.(mp4|gif|webp|png)$/;

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
    default:
      return null;
  }
}
