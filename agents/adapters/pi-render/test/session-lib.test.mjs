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
  stillArgs,
  expiredRunDirs,
  expiredTranscripts,
  VENDOR_ASSETS,
  DEFAULT_SESSION_WORKSPACE,
  DEFAULT_RETRY,
  DEFAULT_GATEWAY_STREAM_TIMEOUT_MS,
  agentSettings,
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
  // Sampled from the end: an entrance animation leaves the first frame empty.
  assert.ok(png.includes("-sseof"), "a still must not be taken from the first frame");
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

test("agentSettings writes the retry window Pi reads, and refuses one the gateway beats", () => {
  const settings = agentSettings();
  assert.equal(settings.httpIdleTimeoutMs, DEFAULT_RETRY.idleTimeoutMs);
  assert.deepEqual(settings.retry, {
    enabled: true,
    maxRetries: DEFAULT_RETRY.maxRetries,
    baseDelayMs: DEFAULT_RETRY.baseDelayMs,
    maxAgentDelayMs: DEFAULT_RETRY.maxAgentDelayMs,
  });

  // The window is what makes a stall survivable: the attempts it buys, each of which may
  // wait the idle timeout, must outlast the minutes an endpoint spends silent.
  assert.ok(settings.retry.maxRetries >= 1, "a single attempt is not a retry window");
  assert.ok(
    (settings.retry.maxRetries + 1) * settings.httpIdleTimeoutMs >= 10 * 60 * 1000,
    "the window is shorter than a ten-minute stall"
  );

  const overridden = agentSettings({ idleTimeoutMs: 500_000, maxRetries: 1, baseDelayMs: 1, maxAgentDelayMs: 2 });
  assert.equal(overridden.httpIdleTimeoutMs, 500_000);
  assert.equal(overridden.retry.maxRetries, 1);

  // An idle timeout at or below the gateway's streaming timeout would abandon an attempt
  // before the gateway could report its verdict, so the retry would never run.
  assert.throws(() => agentSettings({ idleTimeoutMs: DEFAULT_GATEWAY_STREAM_TIMEOUT_MS }), /must exceed/);
  assert.throws(() => agentSettings({ idleTimeoutMs: 1_000, gatewayStreamTimeoutMs: 120_000 }), /must exceed/);
});

test("this module depends on nothing but node builtins", async () => {
  // The CI job for this directory runs `node --test` with no `npm ci`, so anything
  // needing a dependency cannot live in a file these tests import: a bare import would
  // fail that job, and the failure would look like a broken test rather than a misplaced
  // dependency. The one dependency this directory had - the S3 client, for an upload the
  // platform cannot supply a credential for - is gone.
  const source = await readFile(join(here, "..", "session-lib.mjs"), "utf8");
  const imports = [...source.matchAll(/^import[^;]*from\s+"([^"]+)"/gm)].map((m) => m[1]);
  assert.ok(imports.length > 0, "no imports found; the pattern is stale");
  for (const spec of imports) {
    assert.ok(spec.startsWith("node:"), `${spec} is not a node builtin`);
  }
});


test("stillArgs screenshots an authored document at the declared frame", () => {
  const [svg] = stillArgs({ format: "svg", runDir: "/runs/x", width: 1280, height: 720 });
  assert.equal(svg.command, "chromium");
  assert.ok(svg.args.includes("--window-size=1280,720"));
  assert.ok(svg.args.some((a) => a.startsWith("--screenshot=/runs/x/")));
  assert.ok(svg.args.includes("file:///runs/x/out.svg"));
  assert.equal(svg.mime, "image/png");
  // A deck is authored as html, and its still is that page.
  const [deck] = stillArgs({ format: "html", runDir: "/runs/x", width: 1280, height: 720 });
  assert.ok(deck.args.includes("file:///runs/x/out.html"));
});

test("stillArgs samples a clip and always includes its final frame", () => {
  const jobs = stillArgs({ format: "mp4", runDir: "/runs/x", width: 1280, durationSeconds: 30 });
  assert.deepEqual(jobs.map((j) => j.output), ["review-1.jpg", "review-2.jpg", "review-3.jpg", "review-final.jpg"]);
  assert.ok(jobs.every((j) => j.command === "ffmpeg" && j.mime === "image/jpeg"));
  // The offsets are the declared duration's, and the last frame is seeked from the end.
  assert.ok(jobs[0].args.includes("7.5"), "a quarter of thirty seconds");
  assert.ok(jobs[3].args.includes("-sseof"), "the final frame is not a timestamp guess");
  // A clip whose duration is unknown still yields its final frame rather than nothing.
  const bare = stillArgs({ format: "gif", runDir: "/runs/x" });
  assert.equal(bare.length, 1);
  assert.equal(bare[0].output, "review-final.jpg");
});

test("stillArgs asks for no still when the artifact is one", () => {
  assert.deepEqual(stillArgs({ format: "png", runDir: "/runs/x", width: 1280 }), []);
});

test("the artifact route serves the stills beside the artifact, and nothing else", () => {
  const ws = "/tmp/aivideo";
  assert.ok(resolveArtifact(ws, "s", "out.svg"));
  assert.ok(resolveArtifact(ws, "s", "review-1.png"), "a document's still is served");
  assert.ok(resolveArtifact(ws, "s", "review-final.jpg"), "a clip's last frame is served");
  assert.equal(resolveArtifact(ws, "s", "review-1.html"), null, "only the stills, not any name");
  assert.equal(resolveArtifact(ws, "s", "prompt.txt"), null);
  assert.equal(contentTypeFor("review-final.jpg"), "image/jpeg");
  assert.equal(contentTypeFor("review-1.png"), "image/png");
});
