// Spawn the pinned HyperFrames CLI over a compiled composition and return the
// encoded bytes plus the file's real metadata (read back with ffprobe, so the
// service reports what it produced rather than what it asked for).

import { spawn } from "node:child_process";
import { mkdtemp, mkdir, writeFile, copyFile, cp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const PKG = join(HERE, "..");

const HYPERFRAMES = process.env.HYPERFRAMES_BIN || join(PKG, "node_modules", ".bin", "hyperframes");
const FFPROBE = process.env.FFPROBE_BIN || "ffprobe";
const TIMEOUT_MS = Number(process.env.RENDER_TIMEOUT_MS || 240000);

function run(cmd, args, { cwd, timeoutMs = 30000 } = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { cwd, stdio: ["ignore", "pipe", "pipe"] });
    let out = "";
    let err = "";
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      reject(new Error(`timed out after ${timeoutMs}ms`));
    }, timeoutMs);
    child.stdout.on("data", (d) => (out += d));
    child.stderr.on("data", (d) => (err += d));
    child.on("error", (e) => {
      clearTimeout(timer);
      reject(e);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      if (code === 0) resolve({ out, err });
      else reject(new Error(`${cmd} exited ${code}: ${(err || out).slice(-500)}`));
    });
  });
}

// One line per render, so an operator can see the service working without the log
// being a stream of browser chatter. Deliberately not the child's raw output: this
// service answers concurrent requests over HTTP, and dumping every render's stderr
// would bury the one line that matters. The child's output is still captured and
// still surfaced in full when a render fails, which is when it is worth reading.
function logRender(stage, detail) {
  process.stdout.write(`render ${stage}: ${detail}\n`);
}

async function probe(file) {
  const { out } = await run(FFPROBE, [
    "-v", "error",
    "-select_streams", "v:0",
    "-show_entries", "stream=width,height,nb_frames,avg_frame_rate,codec_name",
    "-show_entries", "format=duration,size",
    "-of", "json",
    file,
  ]);
  const j = JSON.parse(out);
  const s = (j.streams || [])[0] || {};
  const f = j.format || {};
  return {
    codec: s.codec_name || "h264",
    width: Number(s.width) || 0,
    height: Number(s.height) || 0,
    frames: Number(s.nb_frames) || 0,
    frameRate: s.avg_frame_rate || "",
    durationMs: Math.round((Number(f.duration) || 0) * 1000),
    bytes: Number(f.size) || 0,
  };
}

export async function renderVideo(html, opt) {
  const dir = await mkdtemp(join(tmpdir(), "hf-render-"));
  const started = Date.now();
  try {
    await writeFile(join(dir, "index.html"), html);
    await mkdir(join(dir, "vendor"), { recursive: true });
    await copyFile(join(PKG, "vendor", "gsap.min.js"), join(dir, "vendor", "gsap.min.js"));
    // A referenced block resolves its own relative assets against its location, so
    // the vendored blocks are copied in whole: a block beside ./vendor/ is what
    // makes the rewritten GSAP path in a full block resolve.
    await cp(join(PKG, "vendor", "blocks"), join(dir, "blocks"), { recursive: true });
    const out = join(dir, "out.mp4");
    logRender("start", `${opt.width}x${opt.height} ${opt.fps}fps ${opt.durationMs}ms`);
    await run(
      HYPERFRAMES,
      ["render", "-o", out, "-f", String(opt.fps), "-q", "looks", "--quiet"],
      { cwd: dir, timeoutMs: TIMEOUT_MS }
    );
    const buffer = await readFile(out);
    const meta = await probe(out);
    logRender(
      "done",
      `${meta.frames} frames ${meta.width}x${meta.height} ${meta.codec} ${buffer.length}B in ${Date.now() - started}ms`
    );
    return { buffer, ...meta };
  } catch (e) {
    // The failure line carries what the success line cannot: how long it burned
    // before giving up, which is what tells a timeout from an immediate error.
    logRender("failed", `after ${Date.now() - started}ms: ${e.message}`);
    throw e;
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}
