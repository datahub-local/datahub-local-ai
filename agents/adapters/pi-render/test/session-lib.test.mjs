import { test } from "node:test";
import assert from "node:assert/strict";
import { join } from "node:path";

import {
  safeSessionId,
  safeFormat,
  artifactName,
  runDir,
  resolveArtifact,
  contentTypeFor,
  transcodeArgs,
  DEFAULT_SESSION_WORKSPACE,
} from "../session-lib.mjs";

const WORKSPACE = "/tmp/aivideo";

test("the default workspace is under the session PVC mount, not /workspace", () => {
  // A live session mounts the PVC at /tmp and not /workspace; defaulting to
  // /workspace failed the first turn with "mkdir '/workspace/runs'".
  assert.ok(DEFAULT_SESSION_WORKSPACE.startsWith("/tmp/"));
  assert.notEqual(DEFAULT_SESSION_WORKSPACE, "/workspace");
});

test("safeSessionId accepts a path-safe id and rejects everything else", () => {
  assert.equal(safeSessionId("run_01.abc-XYZ"), "run_01.abc-XYZ");
  assert.equal(safeSessionId(".."), "default");
  assert.equal(safeSessionId("a/b"), "default");
  assert.equal(safeSessionId("a b"), "default");
  assert.equal(safeSessionId("x".repeat(81)), "default");
  assert.equal(safeSessionId(undefined), "default");
  assert.equal(safeSessionId(42), "default");
});

test("safeFormat keeps a known format and defaults an unknown one", () => {
  for (const f of ["mp4", "gif", "webp", "png"]) assert.equal(safeFormat(f), f);
  assert.equal(safeFormat("avi"), "mp4");
  assert.equal(safeFormat(undefined), "mp4");
});

test("artifactName follows the format", () => {
  assert.equal(artifactName("mp4"), "out.mp4");
  assert.equal(artifactName("gif"), "out.gif");
  assert.equal(artifactName("nonsense"), "out.mp4");
});

test("runDir is per session", () => {
  assert.equal(runDir(WORKSPACE, "a"), join(WORKSPACE, "runs", "a"));
  assert.equal(runDir(WORKSPACE, "b"), join(WORKSPACE, "runs", "b"));
  assert.notEqual(runDir(WORKSPACE, "a"), runDir(WORKSPACE, "b"));
});

test("resolveArtifact serves only this server's files inside the run directory", () => {
  assert.equal(resolveArtifact(WORKSPACE, "run1", "out.mp4"), join(WORKSPACE, "runs", "run1", "out.mp4"));
  assert.equal(resolveArtifact(WORKSPACE, "run1", "out.gif"), join(WORKSPACE, "runs", "run1", "out.gif"));
  // Traversal, unknown names and absolute paths resolve to null.
  assert.equal(resolveArtifact(WORKSPACE, "run1", "../out.mp4"), null);
  assert.equal(resolveArtifact(WORKSPACE, "run1", "out.txt"), null);
  assert.equal(resolveArtifact(WORKSPACE, "run1", "index.html"), null);
  assert.equal(resolveArtifact(WORKSPACE, "run1", "/etc/passwd"), null);
  assert.equal(resolveArtifact(WORKSPACE, "..", "out.mp4"), null);
  assert.equal(resolveArtifact(WORKSPACE, "run1", "sub/out.mp4"), null);
});

test("contentTypeFor matches the served artifact", () => {
  assert.equal(contentTypeFor("out.mp4"), "video/mp4");
  assert.equal(contentTypeFor("out.gif"), "image/gif");
  assert.equal(contentTypeFor("out.webp"), "image/webp");
  assert.equal(contentTypeFor("out.png"), "image/png");
});

test("transcodeArgs only runs ffmpeg when the format is not mp4", () => {
  assert.equal(transcodeArgs("mp4", {}), null);
  const gif = transcodeArgs("gif", { fps: 8, width: 1080 });
  const gifLine = gif.join(" ");
  assert.ok(gifLine.includes("palettegen") && gifLine.includes("paletteuse"));
  assert.ok(gifLine.includes("fps=8") && gifLine.includes("scale=1080:-2"));
  assert.equal(gif.at(-1), "out.gif");
  const webp = transcodeArgs("webp", {});
  assert.ok(webp.includes("libwebp"));
  assert.equal(webp.at(-1), "out.webp");
  const png = transcodeArgs("png", {});
  assert.ok(png.includes("-frames:v"));
  assert.equal(png.at(-1), "out.png");
});
