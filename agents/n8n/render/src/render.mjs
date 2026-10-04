// Spawn the pinned HyperFrames CLI over a compiled composition and return the
// encoded bytes plus the file's real metadata (read back with ffprobe, so the
// service reports what it produced rather than what it asked for).

import { spawn } from "node:child_process";
import { mkdtemp, mkdir, writeFile, copyFile, readFile, rm } from "node:fs/promises";
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
  try {
    await writeFile(join(dir, "index.html"), html);
    await mkdir(join(dir, "vendor"), { recursive: true });
    await copyFile(join(PKG, "vendor", "gsap.min.js"), join(dir, "vendor", "gsap.min.js"));
    const out = join(dir, "out.mp4");
    await run(
      HYPERFRAMES,
      ["render", "-o", out, "-f", String(opt.fps), "-q", "looks", "--quiet"],
      { cwd: dir, timeoutMs: TIMEOUT_MS }
    );
    const buffer = await readFile(out);
    const meta = await probe(out);
    return { buffer, ...meta };
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}
