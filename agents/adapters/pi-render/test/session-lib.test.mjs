import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

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
  signS3Request,
  amzDate,
  UPLOAD_PREFIX,
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

// --- S3 upload -------------------------------------------------------------------
//
// The signature is what lets the session server write the artifact itself, so that no
// workflow ever carries the bytes and `saveDataSuccessExecution` can be on. It is
// hand-rolled because n8n cannot sign (`Module 'crypto' is disallowed` in a Code node)
// and the adapter must not gain a dependency for sixty lines.

test("a key may only be written under the upload prefix", () => {
  assert.equal(UPLOAD_PREFIX, "visual-studio/");
  assert.ok(isUploadKeyAllowed("visual-studio/13356-animation.mp4"));
  assert.ok(isUploadKeyAllowed("visual-studio/nested/deck.html"));
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

test("signing refuses to run without a destination or a credential", () => {
  assert.match(signS3Request({}).error, /required/);
  assert.match(signS3Request({ url: "http://x/y", region: "homelab" }).error, /required/);
  assert.match(
    signS3Request({ url: "http://x/y", accessKey: "a", secretKey: "b" }).error,
    /required/,
  );
});

test("the canonical request is the one botocore builds for the same request", () => {
  // Independently produced by botocore's S3SigV4Auth (the same AWSRequest, with
  // X-Amz-Content-SHA256 set and a pinned timestamp) on 2026-10-14. A canonical
  // request that differs from the reference by one character still signs, and the
  // failure only appears as SignatureDoesNotMatch against a live endpoint.
  const signed = signS3Request({
    url: "http://localhost:3900/datahub-local-temp/visual-studio/probe.txt",
    body: Buffer.from("hello"),
    accessKey: "AKIDEXAMPLE",
    secretKey: "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",
    region: "homelab",
    now: "20261014T120000Z",
  });
  assert.equal(
    signed.canonicalRequest,
    "PUT\n" +
      "/datahub-local-temp/visual-studio/probe.txt\n" +
      "\n" +
      "host:localhost:3900\n" +
      "x-amz-content-sha256:2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824\n" +
      "x-amz-date:20261014T120000Z\n" +
      "\n" +
      "host;x-amz-content-sha256;x-amz-date\n" +
      "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
  );
  assert.equal(
    signed.stringToSign,
    "AWS4-HMAC-SHA256\n20261014T120000Z\n20261014/homelab/s3/aws4_request\n" +
      "630ef49748871a546f5355509dbe927fca0571d10ee9e2e5f33a1442c3bf91fd",
  );
});

test("the signature is the one Garage accepts", () => {
  // Pinned from this implementation, which was exercised live on 2026-10-14 against
  // Garage from a pod holding the S3 credential: the same headers returned
  // PUT 200, GET 200 with the exact body, DELETE 204. This is a regression guard on
  // the key derivation; the live PUT is the algorithm's real check.
  const signed = signS3Request({
    url: "http://localhost:3900/datahub-local-temp/visual-studio/probe.txt",
    body: Buffer.from("hello"),
    accessKey: "AKIDEXAMPLE",
    secretKey: "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",
    region: "homelab",
    now: "20261014T120000Z",
  });
  assert.equal(signed.signature, "1ed3fd3c79583d110e6b02a08d4e0ce2d01e7bffbd1f759e96e5b9d72c1499a5");
  assert.match(signed.headers.authorization, /^AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE\/20261014\/homelab\/s3\/aws4_request, /);
  assert.match(signed.headers.authorization, /SignedHeaders=host;x-amz-content-sha256;x-amz-date, Signature=/);
  assert.equal(signed.headers["x-amz-date"], "20261014T120000Z");
  assert.equal(signed.scope, "20261014/homelab/s3/aws4_request");
});

test("the signed host carries a non-default port", () => {
  // Garage's S3 endpoint is :3900, and the Host header is signed as sent. Signing
  // `hostname` instead of `host` would drop the port and fail against a live bucket.
  const signed = signS3Request({
    url: "http://datahub-local-core-data-garage.data.svc.cluster.local:3900/b/k",
    accessKey: "a",
    secretKey: "b",
    region: "homelab",
    now: "20261014T120000Z",
  });
  assert.match(signed.canonicalRequest, /host:datahub-local-core-data-garage\.data\.svc\.cluster\.local:3900/);
});

test("a fixed time signs the same bytes twice, and amzDate is the AWS shape", () => {
  const args = {
    url: "http://x:3900/b/k",
    accessKey: "a",
    secretKey: "b",
    region: "homelab",
    now: "20261014T120000Z",
  };
  assert.equal(signS3Request(args).signature, signS3Request(args).signature);
  assert.equal(amzDate("20261014T120000Z"), "20261014T120000Z");
  assert.equal(amzDate(new Date("2026-10-14T12:00:00.000Z")), "20261014T120000Z");
});
