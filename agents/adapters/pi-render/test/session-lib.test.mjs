import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

import {
  safeSessionId,
  safeFormat,
  artifactName,
  runDir,
  resolveArtifact,
  contentTypeFor,
  transcodeArgs,
  needsConformance,
  conformanceNote,
  outputFps,
  stageRunAssets,
  compositionMarker,
  turnInstruction,
  sessionIdFromTranscript,
  stillArgs,
  sheetArgs,
  settledFrameSeek,
  captureStill,
  expiredRunDirs,
  expiredTranscripts,
  parseCheckReport,
  parseMotionSignals,
  stillTimesFor,
  connectorGeometry,
  connectorsVerification,
  checkArgs,
  MOTION_FILTER,
  CHECK_FINDING_CAP,
  VENDOR_ASSETS,
  RUNTIME_ASSETS,
  DEFAULT_SESSION_WORKSPACE,
  DEFAULT_RETRY,
  DEFAULT_GATEWAY_STREAM_TIMEOUT_MS,
  agentSettings,
  mcpConfig,
} from "../session-lib.mjs";

const here = dirname(fileURLToPath(import.meta.url));

const WORKSPACE = "/tmp/aivideo";

test("the catalog config declares the read tools and hides the rest", () => {
  const { mcpServers } = mcpConfig({
    githubUrl: "http://github.invalid/mcp",
    firecrawlUrl: "http://firecrawl.invalid/mcp",
  });
  assert.equal(mcpServers.github.url, "http://github.invalid/mcp");
  assert.equal(mcpServers.github.exposure, "hidden");
  assert.equal(mcpServers.github.toolExposure.search_code, "direct");
  // The catalog's server carries write tools; an authoring turn may not reach them.
  for (const write of ["create_or_update_file", "push_files", "create_pull_request", "issue_write"]) {
    assert.equal(mcpServers.github.toolExposure[write], undefined, `${write} is exposed`);
  }
  assert.deepEqual(Object.keys(mcpServers.firecrawl.toolExposure).sort(), [
    "firecrawl_map",
    "firecrawl_scrape",
    "firecrawl_search",
  ]);
  // The image carries no address: a deployment that sets neither variable has no catalog.
  assert.deepEqual(mcpConfig().mcpServers, {});
  assert.deepEqual(mcpConfig({ firecrawlUrl: "http://firecrawl.invalid/mcp" }).mcpServers.github, undefined);
});

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

test("transcodeArgs runs ffmpeg for a format change, and for a container that differs", () => {
  // A request that declared nothing has nothing to conform to, so an mp4 is served as the
  // engine rendered it.
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

test("an mp4 already in the declared container is not encoded twice", () => {
  const declared = { width: 1280, height: 720, frames: 360, durationSeconds: 12 };
  assert.equal(transcodeArgs("mp4", { ...declared, actual: { width: 1280, height: 720, durationSeconds: 12, fps: 30 } }), null);
  // One frame short at 30fps is the same clip; half a second is not.
  assert.equal(
    transcodeArgs("mp4", { ...declared, actual: { width: 1280, height: 720, durationSeconds: 11.98, fps: 30 } }),
    null
  );
  assert.notEqual(
    transcodeArgs("mp4", { ...declared, actual: { width: 1280, height: 720, durationSeconds: 11.5, fps: 30 } }),
    null
  );
});

test("an mp4 whose container disagrees is conformed, and never over its own input", () => {
  // Measured shape: a 16:9 / 12s type rendered at 1080x1350 for 3s.
  const declared = { width: 1280, height: 720, frames: 360, durationSeconds: 12 };
  const args = transcodeArgs("mp4", { ...declared, actual: { width: 1080, height: 1350, durationSeconds: 3, fps: 30 } });
  const line = args.join(" ");
  assert.ok(line.includes("scale=1280:720:force_original_aspect_ratio=increase"), line);
  assert.ok(line.includes("crop=1280:720"), line);
  assert.ok(line.includes("-t 12"), "a longer render is trimmed to the declared length");
  assert.ok(line.includes("fps=30"), "the declared frame count over the declared length");
  assert.equal(args.at(-1), "out.conformed.mp4", "ffmpeg cannot write the file it is reading");
  assert.ok(args.includes("-i") && args[args.indexOf("-i") + 1] === "out.mp4");
});

test("a render whose container cannot be read is conformed rather than trusted", () => {
  const declared = { width: 1280, height: 720, frames: 360, durationSeconds: 12 };
  assert.ok(needsConformance(declared, null));
  assert.ok(needsConformance(declared, { width: 0, height: 0, durationSeconds: 0, fps: 0 }));
  assert.ok(!needsConformance({}, null), "nothing declared, nothing to conform to");
  assert.ok(!needsConformance(declared, { width: 1280, height: 720, durationSeconds: 12, fps: 30 }));
});

test("conformanceNote names the frame served, the frame authored, and a short render", () => {
  const declared = { width: 1280, height: 720, frames: 360, durationSeconds: 12 };
  const cropped = conformanceNote({
    opts: declared,
    actual: { width: 1080, height: 1350, durationSeconds: 3, fps: 30 },
    conformed: true,
  });
  assert.deepEqual(cropped, {
    frame: "1280x720",
    authored: "1080x1350",
    fit: "crop",
    durationSeconds: 12,
    authoredSeconds: 3,
    short: true,
    reason: "",
  });
  const clean = conformanceNote({ opts: declared, actual: { width: 1280, height: 720, durationSeconds: 12, fps: 30 } });
  assert.equal(clean.fit, "none");
  assert.equal(clean.short, false);
  const scaled = conformanceNote({
    opts: declared,
    actual: { width: 2560, height: 1440, durationSeconds: 12, fps: 30 },
    conformed: true,
  });
  assert.equal(scaled.fit, "scale", "the same aspect scaled is not a crop");
  const blind = conformanceNote({ opts: declared, actual: null });
  assert.equal(blind.fit, "unknown");
  assert.equal(blind.authored, "");
  assert.ok(blind.reason, "an unreadable render says why it is unknown");
});

test("a still is conformed to the declared frame like any other artifact", () => {
  const png = transcodeArgs("png", { width: 1280, height: 670 });
  assert.ok(png.join(" ").includes("crop=1280:670"), "the card ships the declared frame");
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

test("stageRunAssets copies the served GSAP and connector helper into the run directory", async () => {
  // An absolute /opt path 404s at render time; the composition references a sibling,
  // so each asset must be staged next to it. GSAP is third-party (vendor/), the
  // connector helper is ours (runtime/), and they are staged from separate sources.
  assert.deepEqual(VENDOR_ASSETS, ["gsap.min.js"]);
  assert.deepEqual(RUNTIME_ASSETS, ["connectors.js"]);
  const vendor = await mkdtemp(join(tmpdir(), "pi-vendor-"));
  const runtime = await mkdtemp(join(tmpdir(), "pi-runtime-"));
  const run = await mkdtemp(join(tmpdir(), "pi-run-"));
  try {
    await writeFile(join(vendor, "gsap.min.js"), "/* gsap */");
    await writeFile(join(runtime, "connectors.js"), "/* connectors */");
    assert.deepEqual(await stageRunAssets(run, vendor, runtime), ["gsap.min.js", "connectors.js"]);
    assert.equal(await readFile(join(run, "gsap.min.js"), "utf8"), "/* gsap */");
    assert.equal(await readFile(join(run, "connectors.js"), "utf8"), "/* connectors */");
    // A missing asset is best-effort, not fatal.
    assert.deepEqual(await stageRunAssets(run, join(vendor, "nope"), join(runtime, "nope")), []);
  } finally {
    await rm(vendor, { recursive: true, force: true });
    await rm(runtime, { recursive: true, force: true });
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


test("stillArgs screenshots an animated document after its entrances run", () => {
  // Chromium screenshots at t=0 otherwise, and the first live review spent a fix cycle on an
  // empty frame: "no diagram content is visible" (execution 13770, 2026-10-17). Measured
  // against a page whose content appears after 3 s: 3,886 bytes at t=0, 8,011 with the budget.
  const shots = stillArgs({ format: "svg", runDir: "/runs/x", width: 1280, height: 720, durationSeconds: 12 });
  assert.deepEqual(shots.map((j) => j.output), ["review-1.png", "review-2.png", "review-3.png", "review-4.png"]);
  assert.deepEqual(
    shots.map((j) => j.args.find((a) => a.startsWith("--virtual-time-budget="))),
    ["--virtual-time-budget=3000", "--virtual-time-budget=6000", "--virtual-time-budget=9000", "--virtual-time-budget=12000"]
  );
  const [svg] = shots;
  assert.equal(svg.command, "chromium");
  assert.ok(svg.args.includes("--window-size=1280,720"));
  assert.ok(svg.args.includes("file:///runs/x/out.svg"));
  assert.equal(svg.mime, "image/png");
  // A deck's page is not a timeline: one settled shot is what there is to see.
  const deck = stillArgs({ format: "html", runDir: "/runs/x", width: 1280, height: 720, durationSeconds: 30 });
  assert.equal(deck.length, 1);
  assert.ok(deck[0].args.includes("file:///runs/x/out.html"));
  assert.ok(deck[0].args.includes("--virtual-time-budget=30000"));
  // An unknown duration still settles rather than capturing t=0.
  assert.ok(stillArgs({ format: "svg", runDir: "/runs/x" })[3].args.includes("--virtual-time-budget=3000"));
});

test("stillArgs samples a clip and always includes its final frame", () => {
  const jobs = stillArgs({ format: "mp4", runDir: "/runs/x", width: 1280, durationSeconds: 30 });
  assert.deepEqual(
    jobs.map((j) => j.output),
    ["review-1.jpg", "review-2.jpg", "review-3.jpg", "review-4.jpg", "review-5.jpg", "review-6.jpg", "review-7.jpg", "review-8.jpg", "review-final.jpg"]
  );
  assert.ok(jobs.every((j) => j.command === "ffmpeg" && j.mime === "image/jpeg"));
  // The offsets are the declared duration's, about three seconds apart so every scene of a
  // 30 s clip is seen, and the last frame is seeked from the end. The first sample is the
  // opening scene, where a clip is briefed to name its subject: a quarter of thirty seconds
  // (7.5) skipped it, so the first still lands at 2.4.
  assert.ok(jobs[0].args.includes("2.4"), "the first tenth of thirty seconds reaches the opening");
  assert.ok(jobs[8].args.includes("-sseof"), "the final frame is not a timestamp guess");
  // A clip whose duration is unknown still yields its final frame rather than nothing.
  const bare = stillArgs({ format: "gif", runDir: "/runs/x" });
  assert.equal(bare.length, 1);
  assert.equal(bare[0].output, "review-final.jpg");
});

test("stillArgs samples a clip at the scene times it is given", () => {
  const jobs = stillArgs({ format: "mp4", runDir: "/runs/x", durationSeconds: 12, fps: 30, times: [1.5, 6.25] });
  assert.deepEqual(jobs.map((j) => j.output), ["review-1.jpg", "review-2.jpg", "review-final.jpg"]);
  assert.equal(jobs[0].args[jobs[0].args.indexOf("-ss") + 1], "1.5");
  assert.equal(jobs[1].args[jobs[1].args.indexOf("-ss") + 1], "6.25");
  // Every clip keeps its settled frame whatever the sample times are.
  assert.ok(jobs.at(-1).args.includes("-sseof"));
});

test("stillArgs asks for no still when the artifact is one", () => {
  assert.deepEqual(stillArgs({ format: "png", runDir: "/runs/x", width: 1280 }), []);
});

test("the contact sheet tiles one frame per second into one image", () => {
  // 30 s: a 6x5 sheet at 213 px tiles -- one image covering every second instead of 8-12
  // stills that sample it.
  const thirty = sheetArgs({ runDir: "/runs/x", durationSeconds: 30 });
  assert.equal(thirty.command, "ffmpeg");
  assert.equal(thirty.output, "review-sheet.jpg");
  assert.equal(thirty.mime, "image/jpeg");
  assert.deepEqual(thirty.args, [
    "-y",
    "-i",
    "out.mp4",
    "-vf",
    "fps=1,scale=213:-2,tile=6x5:padding=2:margin=2",
    "-frames:v",
    "1",
    "/runs/x/review-sheet.jpg",
  ]);

  // 12 s is the 4x3 sheet the pod verified against `sketch-16955`.
  const twelve = sheetArgs({ runDir: "/runs/x/", durationSeconds: 12 });
  assert.ok(twelve.args.includes("fps=1,scale=320:-2,tile=4x3:padding=2:margin=2"), twelve.args.join(" "));
  assert.equal(twelve.args.at(-1), "/runs/x/review-sheet.jpg", "a trailing slash is not doubled");

  // A one-second clip is one tile, and a duration nobody reported still makes a sheet.
  const one = sheetArgs({ runDir: "/runs/x", durationSeconds: 1 });
  assert.ok(one.args.includes("fps=1,scale=1280:-2,tile=1x1:padding=2:margin=2"));
  assert.ok(sheetArgs({ runDir: "/runs/x" }).args.includes("fps=1,scale=1280:-2,tile=1x1:padding=2:margin=2"));

  // A narrow declared frame still gets tiles wide enough to see.
  const narrow = sheetArgs({ runDir: "/runs/x", durationSeconds: 30, width: 640 });
  assert.ok(narrow.args.includes("fps=1,scale=120:-2,tile=6x5:padding=2:margin=2"), narrow.args.join(" "));
});

test("the settled-frame seek reaches a frame at the clip's own rate", () => {
  // ffmpeg's `-sseof` shorter than one frame interval exits 0 and writes nothing: on the
  // 8 fps artifact this pipeline derives from 24 frames over 3 s, -0.1 wrote no file while
  // -0.125 wrote the frame (measured 2026-10-17, run 13785).
  assert.equal(settledFrameSeek(8), 0.125);
  assert.ok(settledFrameSeek(30) >= 1 / 30, "a high rate seeks at least one interval");
  assert.ok(settledFrameSeek(2) >= 0.5);
  // A rate below 1 fps gets a whole interval too, not a fraction of one.
  assert.ok(settledFrameSeek(0.5) >= 2);
  // A rate nobody reported falls back rather than seeking 0 -- which reaches no frame.
  assert.equal(settledFrameSeek(0), 0.5);
  assert.equal(settledFrameSeek(undefined), 0.5);
  assert.equal(settledFrameSeek(NaN), 0.5);
  assert.equal(settledFrameSeek(-1), 0.5);
});

test("stillArgs seeks the settled frame by the frame interval, and falls back when the rate is unknown", () => {
  const offset = (job) => job.args[job.args.indexOf("-sseof") + 1];
  const slow = stillArgs({ format: "mp4", runDir: "/runs/x", durationSeconds: 3, fps: 8 });
  assert.equal(offset(slow.at(-1)), "-0.125", "one frame at 8 fps is 0.125 s");
  const fast = stillArgs({ format: "mp4", runDir: "/runs/x", durationSeconds: 12, fps: 30 });
  assert.ok(Number(offset(fast.at(-1)).slice(1)) >= 1 / 30);
  // A caller that reports no rate still gets a settled frame rather than a zero seek.
  const bare = stillArgs({ format: "gif", runDir: "/runs/x" });
  assert.equal(offset(bare[0]), "-0.5");
});

test("a capture that wrote nothing is not a still, and an earlier file at that name is cleared", async () => {
  const run = await mkdtemp(join(tmpdir(), "pi-still-"));
  try {
    // The previous turn's frame is on disk under the name this turn will use.
    await writeFile(join(run, "review-final.jpg"), "the previous turn's frame");
    // The measured shape: ffmpeg exits 0 and writes nothing for a sub-frame seek.
    const made = await captureStill({ dir: run, output: "review-final.jpg", run: async () => {} });
    assert.equal(made, false, "a capture that wrote no bytes is not a still");
    await assert.rejects(readFile(join(run, "review-final.jpg")), "the earlier turn's frame must not stand in");

    // A capture that wrote bytes is a still.
    const ok = await captureStill({
      dir: run,
      output: "review-1.jpg",
      run: async () => { await writeFile(join(run, "review-1.jpg"), "frame"); },
    });
    assert.equal(ok, true);
    // A capture that could not run, and one that wrote an empty file, are both not stills.
    assert.equal(await captureStill({ dir: run, output: "review-2.jpg", run: async () => { throw new Error("ffmpeg exited 1"); } }), false);
    assert.equal(await captureStill({ dir: run, output: "review-3.jpg", run: async () => { await writeFile(join(run, "review-3.jpg"), ""); } }), false);
  } finally {
    await rm(run, { recursive: true, force: true });
  }
});

test("the artifact route serves the stills beside the artifact, and nothing else", () => {
  const ws = "/tmp/aivideo";
  assert.ok(resolveArtifact(ws, "s", "out.svg"));
  assert.ok(resolveArtifact(ws, "s", "review-1.png"), "a document's still is served");
  assert.ok(resolveArtifact(ws, "s", "review-final.jpg"), "a clip's last frame is served");
  assert.ok(resolveArtifact(ws, "s", "review-sheet.jpg"), "a clip's contact sheet is served");
  assert.equal(resolveArtifact(ws, "s", "review-1.html"), null, "only the stills, not any name");
  assert.equal(resolveArtifact(ws, "s", "prompt.txt"), null);
  assert.equal(contentTypeFor("review-final.jpg"), "image/jpeg");
  assert.equal(contentTypeFor("review-sheet.jpg"), "image/jpeg");
  assert.equal(contentTypeFor("review-1.png"), "image/png");
});

// ---------------------------------------------------------------------------
// The deterministic gate: report and detector parsing, scene-aware stills, connector
// geometry and the DOM the helper leaves. All pure; the processes are the server's.

const CHECK_ENVELOPE = {
  ok: false,
  snapshots: [],
  lint: {
    findings: [
      { code: "overlap", severity: "error", selector: "#d-lake", message: "the panel overlaps the lake", dataId: "d-lake", time: 12.4, bbox: [10, 20, 300, 120] },
    ],
  },
  runtime: { findings: [] },
  layout: {
    findings: [{ code: "line_unread", severity: "warning", selector: "#copy", message: "a line falls below the floor" }],
  },
  motion: { findings: [] },
  contrast: { findings: [] },
  craft: { findings: [{ code: "dead_stretch", severity: "info", message: "a dead stretch of 2 s" }] },
  audio: { findings: [] },
  hdr: { findings: [] },
};

test("the check report is flattened, ranked and capped", () => {
  const report = parseCheckReport(JSON.stringify(CHECK_ENVELOPE));
  assert.equal(report.ran, true);
  assert.equal(report.ok, false);
  assert.equal(report.reason, "");
  assert.deepEqual(report.counts, { error: 1, warning: 1, info: 1 });
  assert.deepEqual(report.findings.map((f) => [f.severity, f.code]), [
    ["error", "overlap"],
    ["warning", "line_unread"],
    ["info", "dead_stretch"],
  ]);
  // The identity a ledger entry needs: which section, which element, which data id, at what time.
  assert.equal(report.findings[0].section, "lint");
  assert.equal(report.findings[0].selector, "#d-lake");
  assert.equal(report.findings[0].dataId, "d-lake");
  assert.equal(report.findings[0].time, 12.4);
  assert.equal(report.findings[0].fixHint, "");
  // An array bbox normalizes to the object shape every consumer reads.
  assert.deepEqual(report.findings[0].bbox, { x: 10, y: 20, w: 300, h: 120 });
  assert.equal(report.findings[1].dataId, "");
  assert.equal(report.findings[1].section, "layout");
  // A pathological report cannot bloat the execution record: 25 findings, errors first, and
  // the counts still say how many there were.
  const flood = {
    ok: false,
    lint: { findings: Array.from({ length: 40 }, (_, i) => ({ code: `e${i}`, severity: "error", selector: `#e${i}` })) },
    craft: { findings: [{ code: "note", severity: "info" }] },
  };
  const capped = parseCheckReport(JSON.stringify(flood));
  assert.equal(capped.findings.length, CHECK_FINDING_CAP);
  assert.equal(capped.counts.error, 40);
  assert.equal(capped.counts.info, 1);
  assert.ok(capped.findings.every((f) => f.severity === "error"), "warnings and info are dropped before errors");

  // A section that a release renames or drops contributes nothing rather than failing.
  const partial = parseCheckReport(JSON.stringify({ ok: true, lint: [], motion: null }));
  assert.deepEqual(partial, { ran: true, ok: true, reason: "", counts: { error: 0, warning: 0, info: 0 }, findings: [] });

  // A banner before the envelope does not hide it.
  assert.equal(parseCheckReport(`checking...\n${JSON.stringify(CHECK_ENVELOPE)}`).counts.error, 1);
});

test("an unreadable check report is not a clean result", () => {
  for (const body of ["", "not json", "{} {}", null]) {
    const report = parseCheckReport(body);
    assert.equal(report.ran, false, `${JSON.stringify(body)} parsed as a run`);
    assert.equal(report.ok, false);
    assert.equal(report.reason, "the check report could not be read");
    assert.deepEqual(report.counts, { error: 0, warning: 0, info: 0 });
    assert.deepEqual(report.findings, []);
  }
});

test("a real check envelope parses to the ledger's finding shape", async () => {
  // Copied from a live `hyperframes 0.9.1` run: bbox is an object there, the section carries
  // its own counts, and the element identity is in `dataAttributes` rather than `dataId`.
  const envelope = JSON.parse(await readFile(join(here, "fixtures", "check-report.json"), "utf8"));
  const report = parseCheckReport(JSON.stringify(envelope));
  assert.equal(report.ran, true);
  assert.equal(report.ok, false);
  assert.deepEqual(report.counts, { error: 1, warning: 1, info: 1 });
  assert.deepEqual(report.findings.map((f) => [f.section, f.severity, f.code]), [
    ["lint", "error", "container_overflow"],
    ["layout", "warning", "overlap"],
    ["craft", "info", "first_frame_empty"],
  ]);

  const [error, warning, info] = report.findings;
  // An array bbox (this one) and an object bbox (the next) reach the same shape.
  assert.deepEqual(error.bbox, { x: 40, y: 120, w: 900, h: 640 });
  assert.deepEqual(warning.bbox, { x: 10, y: 20, w: 300, h: 120 });
  assert.deepEqual(info.bbox, { x: 0, y: 0, w: 1280, h: 720 });
  assert.equal(error.fixHint, "drop a row or shrink the card's row height");
  assert.equal(warning.fixHint, "move the label inside the panel");
  assert.equal(info.fixHint, "", "a finding without a hint says so rather than inventing one");
  // The data-* identity: `id` when the attributes carry one, the capped JSON otherwise.
  assert.equal(warning.dataId, "d-lake");
  assert.match(info.dataId, /"scene":"05"/);
  assert.equal(error.dataId, "");
  // An element with no data-* at all has no identity; `"{}"` would be a fake one.
  const bare = parseCheckReport(JSON.stringify({ ok: true, lint: { findings: [{ code: "x", severity: "info", dataAttributes: {} }] } }));
  assert.equal(bare.findings[0].dataId, "");
  assert.equal(error.time, 1.4);
  assert.equal(warning.time, 12.4);

  // The same envelope three times over is capped at 25, errors first.
  const flood = {
    ok: false,
    lint: { findings: Array.from({ length: 10 }, () => envelope.lint.findings[0]) },
    layout: { findings: Array.from({ length: 10 }, () => envelope.layout.findings[0]) },
    craft: { findings: Array.from({ length: 10 }, () => envelope.craft.findings[0]) },
  };
  const capped = parseCheckReport(JSON.stringify(flood));
  assert.equal(capped.findings.length, CHECK_FINDING_CAP);
  assert.ok(capped.findings.slice(0, 10).every((f) => f.severity === "error"), "errors are not first");
  assert.ok(capped.findings.slice(10, 20).every((f) => f.severity === "warning"), "warnings follow the errors");
  assert.equal(capped.findings[24].severity, "info");
  assert.equal(capped.counts.error, 10);
});

test("the motion filter does not call the brand's dark surface black", () => {
  // Measured: `lips-60` reported seven black spans at pix_th=0.10 (0-0.47 s, 4.3-5.27 s, ...)
  // and `lips-j5n6da` likewise; both report zero at 0.02, and a synthetic 1 s true-black clip
  // still reports black_start:0 black_end:1. The threshold is the gate or a false alarm.
  assert.equal(MOTION_FILTER, "freezedetect=n=0.003:d=0.5,blackdetect=d=0.1:pix_th=0.02:pic_th=0.99");
  assert.ok(MOTION_FILTER.includes("blackdetect=d=0.1:pix_th=0.02:pic_th=0.99"));
  assert.ok(!MOTION_FILTER.includes("0.10"), "the false-positive threshold is back");
  assert.ok(!MOTION_FILTER.includes("pix_th=0.1:"), "the false-positive threshold is back");
});

test("the check invocation only names flags the pinned engine has", () => {
  // Live 0.9.1: `--no-cache` is parsed as `--cache` ("Unknown flag: --cache", exit 2) and
  // `--budget` does not exist, so either one makes every gate report `ran: false`.
  const args = checkArgs("/runs/x");
  assert.deepEqual(args, ["check", "/runs/x", "--json", "--at-transitions", "--timeout=45000"]);
  assert.ok(!args.some((a) => a.includes("--no-cache")), "the check still passes --no-cache");
  assert.ok(!args.some((a) => a.includes("--budget")), "the check still passes --budget");
  // The engine's render-ready wait defaults to 10 s; a 30 s composition needs longer.
  assert.ok(args.includes("--timeout=45000"));
});

// The measured line shapes: the detectors prefix their own filter name, scdet prefixes none.
const MOTION_STDERR = [
  "[freezedetect @ 0x55d0] lavfi.freezedetect.freeze_start: 1.5",
  "[freezedetect @ 0x55d0] lavfi.freezedetect.freeze_duration: 2.5",
  "[freezedetect @ 0x55d0] lavfi.freezedetect.freeze_end: 4",
  "[blackdetect @ 0x55d0] lavfi.blackdetect.black_start: 0",
  "[blackdetect @ 0x55d0] lavfi.blackdetect.black_end: 0.5",
  "[scdet @ 0x55d0] lavfi.scd.time: 3.6",
  "[scdet @ 0x55d0] lavfi.scd.time: 8.4",
].join("\n");

test("the detector stderr becomes freeze, black, cuts and scenes", () => {
  const signals = parseMotionSignals(MOTION_STDERR, 12);
  assert.deepEqual(signals.freeze, [{ start: 1.5, end: 4 }]);
  assert.deepEqual(signals.black, [{ start: 0, end: 0.5 }]);
  assert.deepEqual(signals.cuts, [3.6, 8.4]);
  assert.deepEqual(signals.scenes, [
    { start: 0, end: 3.6 },
    { start: 3.6, end: 8.4 },
    { start: 8.4, end: 12 },
  ]);
  assert.equal(signals.scenesSeen, 3);

  // The plain key, an unterminated span (a clip that ends frozen), and cuts on adjacent
  // frames as one cut.
  const plain = parseMotionSignals(
    ["freeze_start: 9", "lavfi.scd.time: 2.00", "lavfi.scd.time: 2.05", "lavfi.scd.time: 2.30"].join("\n"),
    12
  );
  assert.deepEqual(plain.freeze, [{ start: 9, end: 12 }]);
  assert.deepEqual(plain.cuts, [2, 2.3]);
  assert.equal(plain.scenesSeen, 3);

  // Empty stderr is an empty result, not an error.
  assert.deepEqual(parseMotionSignals("", 30), { freeze: [], black: [], cuts: [], scenes: [], scenesSeen: 0 });
  assert.deepEqual(parseMotionSignals(undefined), { freeze: [], black: [], cuts: [], scenes: [], scenesSeen: 0 });
});

function sevenScenes() {
  // Seven two-second scenes with a cut every two seconds.
  return {
    cuts: [2, 4, 6, 8, 10, 12],
    scenes: Array.from({ length: 7 }, (_, i) => ({ start: i * 2, end: i * 2 + 2 })),
    freeze: [],
    black: [],
    scenesSeen: 7,
  };
}

test("one still per detected scene, and the cut frames when there is room", () => {
  const { times, scenesCovered } = stillTimesFor(sevenScenes(), 14, { fps: 30 });
  assert.equal(scenesCovered, 7);
  assert.ok(times.length <= 12, `the cap is 12 stills, got ${times.length}`);
  for (let i = 0; i < 7; i += 1) {
    const midpoint = i * 2 + 1;
    assert.ok(times.includes(midpoint), `scene ${i} has no midpoint still: ${JSON.stringify(times)}`);
  }
  // The straddles sit either side of a cut, not on it.
  assert.ok(times.some((t) => t !== Math.round(t)), "a straddle frame is within a frame of a cut");
  assert.ok(times.every((t, i) => i === 0 || t > times[i - 1]), "times are unique and sorted");
});

test("a clip with no detected cut falls back to a dense uniform grid", () => {
  // 17510 is one continuous animation: no hard cut, and scdet logs nothing. Eight fixed
  // offsets over thirty seconds left most of the render unseen, so the fallback is about one
  // still per 2.5 s.
  const noCuts = { cuts: [], scenes: [], freeze: [], black: [], scenesSeen: 0 };
  const thirty = stillTimesFor(noCuts, 30, { max: 12 });
  assert.equal(thirty.times.length, 12);
  assert.equal(thirty.scenesCovered, 0);
  assert.deepEqual(thirty.times, [1.25, 3.75, 6.25, 8.75, 11.25, 13.75, 16.25, 18.75, 21.25, 23.75, 26.25, 28.75]);
  // Every gap is one 2.5 s step rather than the old ~3.4 s spread over eight samples.
  for (let i = 1; i < thirty.times.length; i += 1) {
    assert.ok(Math.abs(thirty.times[i] - thirty.times[i - 1] - 2.5) < 1e-9, `gap ${i} is not 2.5 s`);
  }
  // The floor of eight stills holds on a short clip; the cap holds on a long one.
  assert.equal(stillTimesFor(noCuts, 12, { max: 12 }).times.length, 8);
  assert.equal(stillTimesFor(noCuts, 60, { max: 12 }).times.length, 12);
  assert.equal(stillTimesFor(noCuts, 60, { max: 12 }).scenesCovered, 0);
  // Without a duration there is nothing to scale, so there is nothing to sample.
  assert.deepEqual(stillTimesFor({ cuts: [], scenes: [] }, 0), { times: [], scenesCovered: 0 });
});

test("a render with more scenes than the cap keeps the midpoints evenly", () => {
  const scenes = Array.from({ length: 20 }, (_, i) => ({ start: i, end: i + 1 }));
  const cuts = Array.from({ length: 19 }, (_, i) => i + 1);
  const { times, scenesCovered } = stillTimesFor({ cuts, scenes, freeze: [], black: [] }, 20, { fps: 30 });
  assert.equal(times.length, 12);
  assert.equal(scenesCovered, 12);
  // Evenly, not the first twelve: both ends of the clip are covered.
  assert.ok(times[0] <= 2, `the first still is ${times[0]}`);
  assert.ok(times.at(-1) >= 18, `the last still is ${times.at(-1)}`);
  assert.ok(times.every((t, i) => i === 0 || t > times[i - 1]));
});

test("a connector leaves the facing edge of each box and stops at the head", () => {
  const from = { x: 400, y: 200, w: 100, h: 60 };
  const right = connectorGeometry({ from, to: { x: 700, y: 210, w: 100, h: 40 } }, { from: "db", to: "kafka" });
  assert.equal(right.ok, true);
  assert.deepEqual([right.x1, right.y1, right.x2, right.y2], [508, 230, 678, 230]);
  assert.equal(right.head.points.split(" ").length, 3, "the head is a triangle");
  assert.equal(right.head.points.split(" ")[0], "692,230", "the tip is on the target's edge");

  const left = connectorGeometry({ from, to: { x: 100, y: 210, w: 100, h: 40 } }, {});
  assert.deepEqual([left.x1, left.y1, left.x2, left.y2], [392, 230, 222, 230]);

  const down = connectorGeometry({ from, to: { x: 420, y: 500, w: 60, h: 60 } }, {});
  assert.deepEqual([down.x1, down.y1, down.x2, down.y2], [450, 268, 450, 478]);

  const up = connectorGeometry({ from, to: { x: 420, y: 0, w: 60, h: 60 } }, {});
  assert.deepEqual([up.x1, up.y1, up.x2, up.y2], [450, 192, 450, 82]);

  // No head: the line reaches the target's edge and there is no triangle.
  const bare = connectorGeometry({ from, to: { x: 700, y: 210, w: 100, h: 40 } }, { head: false });
  assert.equal(bare.head, null);
  assert.equal(bare.x2, 692);
});

test("a connector with a missing or overlapping box is refused, not drawn", () => {
  const from = { x: 0, y: 0, w: 100, h: 100 };
  const missing = connectorGeometry({ from }, { from: "db", to: "kafka" });
  assert.equal(missing.ok, false);
  assert.match(missing.reason, /kafka/);
  assert.equal(connectorGeometry({ to: from }, {}).ok, false);
  assert.equal(connectorGeometry({}, {}).ok, false);
  assert.equal(connectorGeometry({ from, to: { x: 50, y: 50, w: 100, h: 100 } }, {}).ok, false);
});

test("connector verification reads the helper's status and drawn lines", () => {
  const ok = connectorsVerification(
    '<html data-hf-connectors="ok"><svg><line data-connector="a"/><polygon data-connector-head="a"/><line data-connector="b"/></svg></html>',
    [{ id: "a" }, { id: "b" }]
  );
  assert.deepEqual(ok, { declared: 2, drawn: 2, errors: [] });

  const failed = connectorsVerification(
    '<html data-hf-connectors="error:b,c"><svg><line data-connector="a"/></svg></html>',
    [{ id: "a" }, { id: "b" }, { id: "c" }]
  );
  assert.equal(failed.declared, 3);
  assert.equal(failed.drawn, 1);
  assert.deepEqual(failed.errors.map((e) => e.id), ["b", "c"]);

  // The helper never ran: 17510's "nine connectors never drew" as one record.
  const absent = connectorsVerification("<html><body></body></html>", [{ id: "a" }]);
  assert.deepEqual(absent, { declared: 1, drawn: 0, errors: [{ id: "*", reason: "the connector helper did not run" }] });
  assert.deepEqual(connectorsVerification("<html></html>", []), { declared: 0, drawn: 0, errors: [] });
});

test("the runtime helper's geometry matches the library's and survives a missing element", async () => {
  const source = await readFile(join(here, "..", "runtime", "connectors.js"), "utf8");
  // `color` is what the composition's computed style reports; omitting it removes
  // getComputedStyle entirely, which is the no-style fallback.
  const makeHarness = ({ color } = {}) => {
    const appended = [];
    const created = [];
    const composition = { getBoundingClientRect: () => ({ left: 0, top: 0, width: 640, height: 360 }) };
    const boxes = {
      db: { left: 20, top: 100, width: 100, height: 40 },
      target: { left: 400, top: 100, width: 100, height: 40 },
    };
    const doc = {
      body: { appendChild: (el) => appended.push(el) },
      documentElement: { dataset: {} },
      querySelector: (selector) => (selector === "[data-composition-id]" ? composition : null),
      getElementById: (id) => (boxes[id] ? { getBoundingClientRect: () => boxes[id] } : null),
      createElementNS: () => {
        const el = {
          style: {},
          attrs: {},
          children: [],
          setAttribute(name, value) {
            el.attrs[name] = String(value);
          },
          appendChild(child) {
            el.children.push(child);
          },
          getBoundingClientRect: () => ({ left: 0, top: 0, width: 0, height: 0 }),
        };
        created.push(el);
        return el;
      },
    };
    const sandbox = {
      document: doc,
      console,
      ...(color === undefined
        ? {}
        : { getComputedStyle: (element) => ({ color: element === composition ? color : "", zIndex: "" }) }),
    };
    vm.createContext(sandbox);
    vm.runInContext(source, sandbox, { filename: "connectors.js" });
    return { sandbox, doc, created, appended, HFConnectors: sandbox.HFConnectors };
  };

  const { sandbox, doc, created, appended, HFConnectors } = makeHarness({ color: "rgb(250, 250, 250)" });
  assert.equal(typeof HFConnectors.draw, "function");

  // The browser copy and the Node copy are one formula: the dump is checked by one, the unit
  // test by the other, and drift between them would make the two disagree about a render.
  const rects = { from: { x: 400, y: 200, w: 100, h: 60 }, to: { x: 700, y: 210, w: 100, h: 40 } };
  // A vm object has another realm's prototype, so the comparison is over the data.
  const plain = (value) => JSON.parse(JSON.stringify(value));
  assert.deepEqual(plain(HFConnectors._geometry(rects, { head: true })), connectorGeometry(rects, { head: true }));
  const vertical = { from: { x: 10, y: 10, w: 20, h: 20 }, to: { x: 10, y: 100, w: 20, h: 20 } };
  assert.deepEqual(plain(HFConnectors._geometry(vertical, {})), connectorGeometry(vertical, {}));
  const overlap = { from: rects.from, to: { x: 450, y: 220, w: 100, h: 60 } };
  assert.equal(HFConnectors._geometry(overlap, {}).ok, false);
  assert.equal(connectorGeometry(overlap, {}).ok, false);

  // The overlay lives outside the composition, so the ink must come from the composition's own
  // colour; `currentColor` there is the page's default (black) and would vanish on a dark scheme.
  const drawn = HFConnectors.draw([{ id: "db-target", from: "db", to: "target" }], {});
  assert.equal(drawn.ok, true);
  assert.equal(drawn.drawn, 1);
  const line = created.find((el) => el.attrs["data-connector"] === "db-target");
  const head = created.find((el) => el.attrs["data-connector-head"] === "db-target");
  assert.equal(line.attrs.stroke, "rgb(250, 250, 250)");
  assert.equal(head.attrs.fill, "rgb(250, 250, 250)");
  assert.equal(doc.documentElement.dataset.hfConnectors, "ok");
  // An explicit stroke still wins over the composition's colour.
  HFConnectors.draw([{ id: "custom", from: "db", to: "target" }], { stroke: "#f5f5f5" });
  assert.equal(created.find((el) => el.attrs["data-connector"] === "custom").attrs.stroke, "#f5f5f5");

  // No computed style at all: `currentColor` is the fallback, as before this change.
  const bare = makeHarness();
  bare.HFConnectors.draw([{ id: "bare", from: "db", to: "target" }], {});
  assert.equal(bare.created.find((el) => el.attrs["data-connector"] === "bare").attrs.stroke, "currentColor");

  // A declaration whose element is not in the page is recorded and the call returns: the
  // composer's script must not die with the arrow.
  const result = HFConnectors.draw([{ id: "f-w3", from: "#db", to: "kafka" }], {});
  assert.equal(result.ok, false);
  assert.equal(result.drawn, 0);
  assert.deepEqual(Array.from(result.errors, (e) => e.id), ["f-w3"]);
  assert.equal(doc.documentElement.dataset.hfConnectors, "error:f-w3");
  assert.equal(sandbox.__hfConnectors.ok, false);
  assert.equal(sandbox.__hfConnectors.drawn, 0);
  assert.equal(sandbox.__hfConnectors.errors[0].id, "f-w3");
  assert.equal(appended.length, 3, "the overlay is appended before the declarations are walked");
});
