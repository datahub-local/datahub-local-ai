// Content-addressed store for rendered files.
//
// The HTTP caller (n8n) gets the bytes inline; the MCP tool cannot, because the
// MCP runner clamps every answer to a few KB. So the store gives the tool a
// bounded handle instead: an id and a URL. The id is the file's own hash, so the
// same spec and version produce the same id and a re-render is a no-op write.
//
// Retention is a TTL sweep on write, not a cron: the store is a hand-off buffer
// between a render and a fetch, not an archive.

import { createHash } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { join } from "node:path";

const DIR = process.env.RENDER_STORE_DIR || "/tmp/render-store";
const TTL_MS = Number(process.env.RENDER_STORE_TTL_MS || 24 * 60 * 60 * 1000);
const ID_RE = /^[0-9a-f]{32}$/;

export function saveAsset(buffer) {
  mkdirSync(DIR, { recursive: true });
  const id = createHash("sha256").update(buffer).digest("hex").slice(0, 32);
  const file = join(DIR, `${id}.mp4`);
  if (!existsSync(file)) writeFileSync(file, buffer);
  sweep();
  return { id, url: `/files/${id}.mp4`, bytes: buffer.length };
}

export function readAsset(id) {
  if (!ID_RE.test(String(id))) return null;
  const file = join(DIR, `${id}.mp4`);
  return existsSync(file) ? readFileSync(file) : null;
}

export function sweep(now = Date.now()) {
  if (!existsSync(DIR)) return 0;
  let removed = 0;
  for (const name of readdirSync(DIR)) {
    try {
      if (now - statSync(join(DIR, name)).mtimeMs > TTL_MS) {
        unlinkSync(join(DIR, name));
        removed += 1;
      }
    } catch {
      // A concurrent sweep removing the same file is not an error.
    }
  }
  return removed;
}
