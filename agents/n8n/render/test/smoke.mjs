#!/usr/bin/env node
// Container smoke test for the render service.
//
// Run it against a *live* service: the CI job builds and starts the image, then
// invokes this file. It is deliberately not named `*.test.mjs` so that
// `npm test` / `node --test test/` stays offline and needs no Chrome or FFmpeg.
//
// The expected values are literal on purpose. The service reports duration and
// frame count read back from the produced file with ffprobe (not echoed from the
// request), so changing fixture.json's `motion.durationMs` without updating
// EXPECT here changes the frame count the service reports and fails this test.
// That is the point: the assertion must not be derived from the fixture.
//
// Env:
//   RENDER_URL        live service base URL (default http://127.0.0.1:8080)
//   RENDER_CONTAINER  optional docker container name; when set, the downloaded
//                     bytes are re-read with the image's own ffprobe, so the
//                     check does not depend on the host having FFmpeg.

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";

const BASE = (process.env.RENDER_URL || "http://127.0.0.1:8080").replace(/\/$/, "");
const CONTAINER = process.env.RENDER_CONTAINER || "";

// Each case pairs a fixture with the metadata its own spec declares. The expected
// values are literal on purpose: the service reports duration and frame count read
// back from the produced file with ffprobe, so changing a fixture's duration
// without updating its case here changes what the service reports and fails.
//
// The block case is what proves a vendored catalog block renders in the image at
// all: if the vendored file were missing or its variables unreachable, the render
// would fall back or fail rather than match these numbers.
const CASES = [
  {
    name: "layout",
    file: "./fixture.json",
    expect: { durationMs: 1000, frames: 12, width: 480, height: 600, fps: "12/1", codec: "h264" },
  },
  {
    name: "catalog-block",
    file: "./fixture-block.json",
    // 540x675 is requested, but the block declares its own 1920x1080 root and the
    // renderer reconciles the two, yielding 676 for a 540-wide 4:5 request. The
    // literal is the observed output, so a change to how dimensions reconcile is
    // a visible failure rather than a silent drift.
    expect: { durationMs: 2000, frames: 60, width: 540, height: 676, fps: "30/1", codec: "h264" },
  },
];

const fail = (msg) => {
  console.error(`FAIL: ${msg}`);
  process.exitCode = 1;
};
const ok = (msg) => console.log(`ok: ${msg}`);

async function runCase(c) {
  const fixture = JSON.parse(readFileSync(new URL(c.file, import.meta.url), "utf8"));
  const res = await fetch(`${BASE}/render`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(fixture),
  });
  if (res.status !== 200) throw new Error(`[${c.name}] /render returned ${res.status}: ${await res.text()}`);

  const type = res.headers.get("content-type") || "";
  if (!type.startsWith("video/mp4")) fail(`[${c.name}] content-type is "${type}", expected video/mp4`);

  const body = Buffer.from(await res.arrayBuffer());
  if (body.length < 1024) fail(`[${c.name}] MP4 is only ${body.length} bytes`);
  if (body.subarray(4, 8).toString("latin1") !== "ftyp") fail(`[${c.name}] response body is not an MP4 (no ftyp box)`);

  const got = {
    durationMs: Number(res.headers.get("x-hf-duration-ms")),
    frames: Number(res.headers.get("x-hf-frames")),
    width: Number(res.headers.get("x-hf-width")),
    height: Number(res.headers.get("x-hf-height")),
    fps: res.headers.get("x-hf-fps"),
    codec: res.headers.get("x-hf-codec"),
  };
  for (const [k, want] of Object.entries(c.expect)) {
    if (got[k] !== want) fail(`[${c.name}] ${k}: got ${got[k]}, expected ${want} (fixture changed without updating the case?)`);
  }
  if (!process.exitCode) {
    ok(`[${c.name}] rendered ${got.frames} frames, ${got.durationMs}ms, ${got.width}x${got.height}, ${got.codec}, ${body.length} bytes`);
  }

  // Independent read of the actual bytes, using the image's own ffprobe.
  // `docker cp` refuses a container whose rootfs is read-only, so stream the
  // bytes into its writable /tmp tmpfs over `docker exec -i` instead.
  if (CONTAINER) {
    execFileSync("docker", ["exec", "-i", CONTAINER, "sh", "-c", `cat > /tmp/smoke-${c.name}.mp4`], { input: body });
    const out = execFileSync(
      "docker",
      [
        "exec", CONTAINER, "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=nb_frames,width,height",
        "-of", "default=noprint_wrappers=1",
        `/tmp/smoke-${c.name}.mp4`,
      ],
      { encoding: "utf8" }
    );
    const probe = Object.fromEntries(out.trim().split("\n").map((line) => line.split("=")));
    if (Number(probe.nb_frames) !== c.expect.frames) fail(`[${c.name}] ffprobe frames: got ${probe.nb_frames}, expected ${c.expect.frames}`);
    if (Number(probe.width) !== c.expect.width) fail(`[${c.name}] ffprobe width: got ${probe.width}, expected ${c.expect.width}`);
    if (Number(probe.height) !== c.expect.height) fail(`[${c.name}] ffprobe height: got ${probe.height}, expected ${c.expect.height}`);
    if (!process.exitCode) ok(`[${c.name}] ffprobe on the downloaded bytes agrees`);
  }
}

async function main() {
  const health = await fetch(`${BASE}/healthz`);
  if (!health.ok) throw new Error(`/healthz returned ${health.status}`);
  ok("/healthz");

  for (const c of CASES) await runCase(c);

  if (process.exitCode) process.exit(process.exitCode);
  console.log("smoke test passed");
}

main().catch((e) => {
  console.error(`FAIL: ${e.message}`);
  process.exit(1);
});
