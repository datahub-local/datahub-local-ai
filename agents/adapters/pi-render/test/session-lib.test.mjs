import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  safeSessionId,
  safeFormat,
  artifactName,
  runDir,
  resolveArtifact,
  contentTypeFor,
  transcodeArgs,
  outputFps,
  stageVendorAssets,
  compositionMarker,
  turnInstruction,
  sessionIdFromTranscript,
  expiredRunDirs,
  expiredTranscripts,
  VENDOR_ASSETS,
  DEFAULT_SESSION_WORKSPACE,
  isUploadKeyAllowed,
  artifactUploads,
  UPLOAD_PREFIX,
} from "../session-lib.mjs";

const here = dirname(fileURLToPath(import.meta.url));

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
  for (const f of ["mp4", "gif", "webp", "png", "svg", "html"]) assert.equal(safeFormat(f), f);
  assert.equal(safeFormat("avi"), "mp4");
  assert.equal(safeFormat(undefined), "mp4");
});

test("artifactName follows the format", () => {
  assert.equal(artifactName("mp4"), "out.mp4");
  assert.equal(artifactName("gif"), "out.gif");
  assert.equal(artifactName("svg"), "out.svg");
  assert.equal(artifactName("html"), "out.html");
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
  assert.equal(resolveArtifact(WORKSPACE, "run1", "out.svg"), join(WORKSPACE, "runs", "run1", "out.svg"));
  assert.equal(resolveArtifact(WORKSPACE, "run1", "out.html"), join(WORKSPACE, "runs", "run1", "out.html"));
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
  assert.equal(contentTypeFor("out.html"), "text/html");
});

test("transcodeArgs only runs ffmpeg when the format is not mp4", () => {
  assert.equal(transcodeArgs("mp4", {}), null);
  assert.equal(transcodeArgs("svg", {}), null, "an SVG is authored directly, not transcoded");
  assert.equal(transcodeArgs("html", {}), null, "a deck is authored directly, not transcoded");
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

test("outputFps prefers frames/duration so a type is tunable from data", () => {
  assert.equal(outputFps({ frames: 24, durationSeconds: 18 }), 24 / 18);
  assert.equal(outputFps({ fps: 6 }), 6);
  assert.equal(outputFps({}), 8);
  // frames without a duration falls back to fps.
  assert.equal(outputFps({ frames: 24, fps: 5 }), 5);
});

test("a declared duration trims the input and sets the frame rate", () => {
  const gif = transcodeArgs("gif", { frames: 24, durationSeconds: 18, width: 1080 });
  const line = gif.join(" ");
  assert.ok(line.includes("-t 18"), "the input is trimmed to the declared duration");
  assert.ok(line.includes("fps=1.333"), "24 frames over 18s is 1.333 fps");
  assert.ok(line.includes("scale=1080:-2"));
});

test("stageVendorAssets copies the served GSAP into the run directory", async () => {
  // An absolute /opt path 404s at render time; the composition references a sibling,
  // so the asset must be staged next to it.
  assert.deepEqual(VENDOR_ASSETS, ["gsap.min.js"]);
  const vendor = await mkdtemp(join(tmpdir(), "pi-vendor-"));
  const run = await mkdtemp(join(tmpdir(), "pi-run-"));
  try {
    await writeFile(join(vendor, "gsap.min.js"), "/* gsap */");
    assert.deepEqual(await stageVendorAssets(run, vendor), ["gsap.min.js"]);
    assert.equal(await readFile(join(run, "gsap.min.js"), "utf8"), "/* gsap */");
    // A missing asset is best-effort, not fatal.
    assert.deepEqual(await stageVendorAssets(run, join(vendor, "nope")), []);
  } finally {
    await rm(vendor, { recursive: true, force: true });
    await rm(run, { recursive: true, force: true });
  }
});

test("compositionMarker follows the format's authored artifact", () => {
  // The marker is what decides author vs edit: a later turn in the same session is
  // an edit of whatever the first turn wrote.
  assert.equal(compositionMarker("mp4"), "index.html");
  assert.equal(compositionMarker("gif"), "index.html");
  assert.equal(compositionMarker("png"), "index.html");
  assert.equal(compositionMarker("svg"), "out.svg");
  assert.equal(compositionMarker("html"), "out.html");
  assert.equal(compositionMarker(undefined), "index.html");
});

test("turnInstruction names the existing composition only on an edit", () => {
  for (const format of ["mp4", "gif", "webp", "png"]) {
    const author = turnInstruction({ format, isIteration: false });
    const edit = turnInstruction({ format, isIteration: true });
    assert.ok(author.includes("Write the composition to `index.html`"), `${format}: author writes`);
    assert.ok(!author.includes("earlier turn"), `${format}: author does not claim prior work`);
    assert.ok(edit.includes("`index.html`") && edit.includes("earlier turn"), `${format}: edit names the composition`);
    assert.ok(edit.includes("in place") && edit.includes("re-render"), `${format}: edit keeps the rest`);
    assert.notEqual(author, edit);
  }
  const svgAuthor = turnInstruction({ format: "svg", isIteration: false });
  const svgEdit = turnInstruction({ format: "svg", isIteration: true });
  assert.ok(svgAuthor.includes("`out.svg`") && !svgAuthor.includes("earlier turn"));
  assert.ok(svgEdit.includes("`out.svg`") && svgEdit.includes("earlier turn"));
  assert.ok(svgEdit.includes("Do not write index.html"), "an SVG edit still refuses a composition");
  const deckAuthor = turnInstruction({ format: "html", isIteration: false });
  const deckEdit = turnInstruction({ format: "html", isIteration: true });
  assert.ok(deckAuthor.includes("`out.html`") && !deckAuthor.includes("earlier turn"));
  assert.ok(deckEdit.includes("`out.html`") && deckEdit.includes("earlier turn"));
  // A missing flag is an author turn, never an accidental edit.
  assert.equal(turnInstruction({ format: "mp4" }), turnInstruction({ format: "mp4", isIteration: false }));
});

test("sessionIdFromTranscript reads Pi's name and refuses a foreign one", () => {
  assert.equal(
    sessionIdFromTranscript("2026-10-05T17-59-46-584Z_diagram_agent-12128.jsonl"),
    "diagram_agent-12128"
  );
  assert.equal(sessionIdFromTranscript("2026-10-11T08-00-00-000Z_animation_linkedin-12948.jsonl"), "animation_linkedin-12948");
  assert.equal(sessionIdFromTranscript("notes.txt"), null);
  assert.equal(sessionIdFromTranscript("no-underscore.jsonl"), null);
  assert.equal(sessionIdFromTranscript(undefined), null);
});

test("expiredRunDirs sweeps only old directories and never the session in flight", () => {
  const cutoffMs = 1_000_000;
  const entries = [
    { name: "old", mtimeMs: cutoffMs - 1 },
    { name: "edge", mtimeMs: cutoffMs },
    { name: "recent", mtimeMs: cutoffMs + 1 },
    { name: "in-flight", mtimeMs: cutoffMs - 5000 },
    { name: "unstattable", mtimeMs: NaN },
  ];
  assert.deepEqual(expiredRunDirs(entries, { cutoffMs, keep: "in-flight" }), ["old"]);
  assert.deepEqual(expiredRunDirs(entries, { cutoffMs }), ["old", "in-flight"]);
});

test("expiredTranscripts sweeps only this server's old transcripts", () => {
  const cutoffMs = 1_000_000;
  const entries = [
    { name: "2026-10-05T00-00-00-000Z_old.jsonl", mtimeMs: cutoffMs - 1 },
    { name: "2026-10-11T00-00-00-000Z_recent.jsonl", mtimeMs: cutoffMs + 1 },
    { name: "2026-10-05T00-00-00-000Z_in-flight.jsonl", mtimeMs: cutoffMs - 1 },
    { name: "foreign.jsonl", mtimeMs: cutoffMs - 1 },
    { name: "notes.txt", mtimeMs: cutoffMs - 1 },
  ];
  assert.deepEqual(expiredTranscripts(entries, { cutoffMs, keep: "in-flight" }), [
    "2026-10-05T00-00-00-000Z_old.jsonl",
  ]);
});

// --- S3 upload policy ------------------------------------------------------------
//
// The session server writes the artifact itself, so no workflow carries the bytes and
// `saveDataSuccessExecution` can be on. The request is signed and sent by the AWS SDK
// in the server; what lives here is the policy that decides whether a destination may
// be written at all.

test("a key may only be written under the upload prefix", () => {
  assert.equal(UPLOAD_PREFIX, "visual-studio/");
  assert.ok(isUploadKeyAllowed("visual-studio/13356-animation.mp4"));
  assert.ok(isUploadKeyAllowed("visual-studio/13356-deck.mp4"));
  for (const bad of [
    "other-prefix/x.mp4",
    "visual-studio/",
    "",
    "visual-studio/../secret",
    "visual-studio/a//b.mp4",
    "visual-studio/a b.mp4",
    "visual-studiox/y.mp4",
    undefined,
    null,
  ]) {
    assert.equal(isUploadKeyAllowed(bad), false, `accepted ${String(bad)}`);
  }
});

test("a nested key is refused because the prune could never delete it", () => {
  // The prune lists `visual-studio/` with a '/' delimiter, so `visual-studio/nested/x`
  // comes back as a CommonPrefix and not as an object: the listing never names it and
  // the delete never reaches it. Allowing one would be a permanent object in a bucket
  // whose whole retention story is a two-day window.
  assert.equal(isUploadKeyAllowed("visual-studio/nested/deck.html"), false);
  assert.equal(isUploadKeyAllowed("visual-studio/a/b/c.mp4"), false);
});

test("this module depends on nothing but node builtins", async () => {
  // The CI job for this directory runs `node --test` with no `npm ci`, which is why the
  // S3 request is signed and sent in session-server.mjs rather than here: the SDK is a
  // dependency, and anything that needs one cannot live in a file these tests import.
  // A bare import would fail that job, and the failure would look like a broken test
  // rather than a misplaced dependency.
  const source = await readFile(join(here, "..", "session-lib.mjs"), "utf8");
  const imports = [...source.matchAll(/^import[^;]*from\s+"([^"]+)"/gm)].map((m) => m[1]);
  assert.ok(imports.length > 0, "no imports found; the pattern is stale");
  for (const spec of imports) {
    assert.ok(spec.startsWith("node:"), `${spec} is not a node builtin`);
  }
});

test("a turn uploads what it produced to the destinations it was given", () => {
  const video = artifactUploads({ format: "mp4", key: "visual-studio/13356-animation.mp4" });
  assert.deepEqual(video.uploads, [
    { file: "out.mp4", key: "visual-studio/13356-animation.mp4", contentType: "video/mp4" },
  ]);
  // A deck is two files from one turn: the HTML and the video it rendered.
  const deck = artifactUploads({
    format: "html",
    key: "visual-studio/13356-deck.html",
    pairedKey: "visual-studio/13356-deck.mp4",
  });
  assert.deepEqual(deck.uploads.map((u) => u.file), ["out.html", "out.mp4"]);
  assert.equal(deck.uploads[1].contentType, "video/mp4");
  // A caller that names no destination stores nothing and is answered as before.
  assert.deepEqual(artifactUploads({ format: "mp4" }).uploads, []);
  assert.deepEqual(artifactUploads({}).uploads, []);
});

test("a destination outside the prefix is refused, not uploaded", () => {
  // The key arrives from the request and this process holds a live credential, so a
  // key that is not under the prefix is an error rather than something to write.
  const bad = artifactUploads({ format: "mp4", key: "other-bucket/evil.mp4" });
  assert.match(bad.error, /refusing to write/);
  assert.equal(bad.uploads, undefined);
  const nested = artifactUploads({ format: "mp4", key: "visual-studio/nested/x.mp4" });
  assert.match(nested.error, /refusing to write/);
  // The paired destination is checked too, not just the primary one.
  const paired = artifactUploads({
    format: "html",
    key: "visual-studio/ok.html",
    pairedKey: "elsewhere/evil.mp4",
  });
  assert.match(paired.error, /refusing to write/);
});
