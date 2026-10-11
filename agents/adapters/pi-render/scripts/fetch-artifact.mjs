#!/usr/bin/env node
// Fetch a rendered artifact out of a pi-render session pod.
//
// Why this exists, rather than `kubectl cp`: both transfer paths truncate in this
// environment and do not always say so. A 2,664,994-byte out.mp4 came back at
// 2,262,523 bytes via `kubectl cp` (with a websocket error) and 1,797,116 bytes via
// a single `kubectl exec … base64`. A truncated video still looks like a file, so it
// is retrieved here in bounded chunks and the md5 is checked against the pod's own
// before the destination is written.
//
//   node agents/adapters/pi-render/scripts/fetch-artifact.mjs \
//     --session e2e-thread-1 --name out.mp4 --dest /tmp/out.mp4
//
// Exits non-zero, writing nothing, if the size or the hash does not match.

import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

// One `kubectl exec` call per chunk. Small enough that the stream never reaches the
// truncation point, large enough that a render is a handful of calls.
export const DEFAULT_CHUNK = 262144;
export const DEFAULT_NAMESPACE = "automation";
export const DEFAULT_WORKSPACE = "/tmp/aivideo";
export const DEFAULT_SESSION_CONTAINER = "harness";
const POD_SELECTOR = "app.kubernetes.io/name=harness-session";

// The byte ranges to read, in order: {skip, count} for each.
export function chunkPlan(size, chunk = DEFAULT_CHUNK) {
  if (!Number.isInteger(size) || size < 0) throw new Error(`size must be a non-negative integer, got ${size}`);
  if (!Number.isInteger(chunk) || chunk <= 0) throw new Error(`chunk must be a positive integer, got ${chunk}`);
  const plan = [];
  for (let skip = 0; skip < size; skip += chunk) {
    plan.push({ skip, count: Math.min(chunk, size - skip) });
  }
  return plan;
}

export function md5(buffer) {
  return createHash("md5").update(buffer).digest("hex");
}

// Read `size` bytes through `readChunk(skip, count) -> Buffer`, in order. A short
// or over-long chunk throws rather than being accepted, so a silently truncated
// transfer cannot be concatenated into a plausible-looking file.
export async function retrieve({ size, readChunk, chunk = DEFAULT_CHUNK, onChunk } = {}) {
  if (typeof size !== "number" || size <= 0) throw new Error("size is required");
  if (typeof readChunk !== "function") throw new Error("readChunk is required");
  const parts = [];
  let total = 0;
  for (const { skip, count } of chunkPlan(size, chunk)) {
    const buf = await readChunk(skip, count);
    if (!Buffer.isBuffer(buf)) throw new Error(`chunk at ${skip} did not return a Buffer`);
    if (buf.length !== count) throw new Error(`chunk at ${skip}: read ${buf.length} bytes, expected ${count}`);
    parts.push(buf);
    total += buf.length;
    onChunk?.(total, size);
  }
  return Buffer.concat(parts, total);
}

// --- kubectl plumbing (not exercised by the unit tests) ----------------------

function kubectl(args, { encoding = "utf8" } = {}) {
  const res = spawnSync("kubectl", args, { encoding, maxBuffer: 64 * 1024 * 1024 });
  if (res.error) throw res.error;
  if (res.status !== 0) {
    const err = String(res.stderr ?? "").trim();
    throw new Error(`kubectl ${args.join(" ")} exited ${res.status}: ${err.slice(0, 400)}`);
  }
  return res.stdout;
}

function sessionPod({ namespace, pod }) {
  if (pod) return pod;
  const name = kubectl([
    "-n", namespace, "get", "pods", "-l", POD_SELECTOR,
    "-o", "jsonpath={.items[0].metadata.name}",
  ]).trim();
  if (!name) throw new Error(`no session pod in ${namespace} matching ${POD_SELECTOR}`);
  return name;
}

function remote(exec, shell) {
  return kubectl(["-n", exec.namespace, "exec", exec.pod, "-c", exec.container, "--", "sh", "-c", shell]);
}

export function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    if (key === "--help" || key === "-h") return { help: true };
    if (!key.startsWith("--")) throw new Error(`unexpected argument ${key}`);
    const value = argv[++i];
    if (value === undefined) throw new Error(`${key} needs a value`);
    args[key.slice(2)] = value;
  }
  return args;
}

const USAGE = `Fetch a rendered artifact from the pi-render session pod, hash-verified.

  --session <id>      the session whose run directory holds the artifact (required)
  --name <file>       artifact name, e.g. out.mp4 (default: out.mp4)
  --dest <path>       where to write it (default: ./<session>-<name>)
  --namespace <ns>    default: ${DEFAULT_NAMESPACE}
  --pod <name>        skip pod discovery
  --container <name>  default: ${DEFAULT_SESSION_CONTAINER}
  --workspace <dir>   default: ${DEFAULT_WORKSPACE}
  --chunk <bytes>     default: ${DEFAULT_CHUNK}
`;

export async function main(argv) {
  const args = parseArgs(argv);
  if (args.help) {
    process.stdout.write(USAGE);
    return;
  }
  if (!args.session) {
    process.stderr.write(USAGE);
    throw new Error("--session is required");
  }
  const namespace = args.namespace ?? DEFAULT_NAMESPACE;
  const container = args.container ?? DEFAULT_SESSION_CONTAINER;
  const workspace = args.workspace ?? DEFAULT_WORKSPACE;
  const name = args.name ?? "out.mp4";
  const chunk = args.chunk ? Number(args.chunk) : DEFAULT_CHUNK;
  const dest = args.dest ?? `${args.session}-${name}`;
  const exec = { namespace, container, pod: sessionPod({ namespace, pod: args.pod }) };
  const path = `${workspace}/runs/${args.session}/${name}`;

  const size = Number(remote(exec, `wc -c < ${path}`).trim());
  if (!Number.isFinite(size) || size <= 0) throw new Error(`could not read a size for ${path}`);
  const want = remote(exec, `md5sum ${path}`).trim().split(/\s+/)[0];

  process.stderr.write(`${exec.pod}:${path}  ${size} bytes, md5 ${want}\n`);
  const buffer = await retrieve({
    size,
    chunk,
    readChunk: (skip, count) =>
      Buffer.from(
        remote(exec, `dd if=${path} bs=${chunk} skip=${skip / chunk} count=1 2>/dev/null | base64 -w0`).trim(),
        "base64"
      ),
    onChunk: (done, total) => process.stderr.write(`\r${done}/${total} bytes`),
  });
  process.stderr.write("\n");

  const got = md5(buffer);
  if (got !== want) throw new Error(`md5 mismatch: pod ${want}, fetched ${got} — nothing written`);
  mkdirSync(dirname(dest), { recursive: true });
  writeFileSync(dest, buffer);
  process.stdout.write(`${dest}  ${buffer.length} bytes  md5 ${got}\n`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  main(process.argv.slice(2)).catch((err) => {
    process.stderr.write(`fetch-artifact: ${err.message}\n`);
    process.exit(1);
  });
}
