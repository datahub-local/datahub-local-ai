// The render service HTTP surface.
//
//   GET  /healthz  -> liveness, never renders
//   POST /render   -> a content spec in, an MP4 out
//
// The endpoint is spec-only by construction: a request carrying markup or script
// is rejected before any composition is built, which is what keeps the trust
// boundary ("model output is data") true at the service edge.

import { createServer } from "node:http";
import { compose } from "./compose.mjs";
import { renderVideo } from "./render.mjs";
import { readAsset, saveAsset } from "./store.mjs";
import { SpecError } from "./spec.mjs";

const PORT = Number(process.env.PORT || 8080);
const MAX_BODY = Number(process.env.MAX_BODY_BYTES || 256 * 1024);
const MARKUP_KEYS = ["html", "markup", "composition", "script", "code", "css"];

function json(res, status, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(status, { "content-type": "application/json", "content-length": Buffer.byteLength(body) });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on("data", (c) => {
      size += c.length;
      if (size > MAX_BODY) {
        reject(new SpecError(`request body exceeds ${MAX_BODY} bytes`));
        req.destroy();
        return;
      }
      chunks.push(c);
    });
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

const server = createServer(async (req, res) => {
  if (req.method === "GET" && req.url === "/healthz") return json(res, 200, { status: "ok" });

  // The bounded form of a render, for a caller that cannot take the bytes inline
  // (the MCP tool). The id is the file's hash, so a fetch is content-addressed.
  const fileMatch = req.method === "GET" && req.url.match(/^\/files\/([0-9a-f]{32})\.mp4$/);
  if (fileMatch) {
    const buffer = readAsset(fileMatch[1]);
    if (!buffer) return json(res, 404, { error: "no such file" });
    res.writeHead(200, { "content-type": "video/mp4", "content-length": buffer.length });
    return res.end(buffer);
  }

  if (req.method !== "POST" || req.url !== "/render") return json(res, 404, { error: "not found" });

  let body;
  try {
    body = JSON.parse(await readBody(req));
  } catch (e) {
    return json(res, e instanceof SpecError ? 400 : 400, { error: `invalid request: ${e.message}` });
  }

  const present = MARKUP_KEYS.filter((k) => body && body[k] !== undefined);
  if (present.length) {
    return json(res, 400, {
      error: `caller-supplied markup is not accepted (${present.join(", ")}); send a content spec`,
    });
  }

  try {
    const wantsStore = Boolean(body && (body.store ?? (body.options && body.options.store)));
    const { html, opt } = compose(body.spec ?? body, body.options ?? body);
    const out = await renderVideo(html, opt);
    if (wantsStore) {
      const saved = saveAsset(out.buffer);
      return json(res, 200, {
        id: saved.id,
        url: saved.url,
        bytes: out.bytes || saved.bytes,
        durationMs: out.durationMs,
        frames: out.frames,
        width: out.width,
        height: out.height,
        fps: out.frameRate,
        codec: out.codec,
      });
    }
    res.writeHead(200, {
      "content-type": "video/mp4",
      "content-length": out.buffer.length,
      "x-hf-duration-ms": String(out.durationMs),
      "x-hf-frames": String(out.frames),
      "x-hf-width": String(out.width),
      "x-hf-height": String(out.height),
      "x-hf-fps": out.frameRate,
      "x-hf-codec": out.codec,
    });
    res.end(out.buffer);
  } catch (e) {
    const status = e instanceof SpecError ? 400 : 502;
    return json(res, status, { error: e.message });
  }
});

server.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`render service listening on :${PORT}`);
});
