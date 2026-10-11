import { test } from "node:test";
import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";

import { chunkPlan, md5, retrieve, parseArgs, DEFAULT_CHUNK } from "../scripts/fetch-artifact.mjs";

test("chunkPlan covers the file exactly, in order, with a short final chunk", () => {
  assert.deepEqual(chunkPlan(10, 4), [
    { skip: 0, count: 4 },
    { skip: 4, count: 4 },
    { skip: 8, count: 2 },
  ]);
  // An exact multiple must not add an empty trailing chunk.
  assert.deepEqual(chunkPlan(8, 4), [
    { skip: 0, count: 4 },
    { skip: 4, count: 4 },
  ]);
  assert.deepEqual(chunkPlan(3, 4), [{ skip: 0, count: 3 }]);
  assert.deepEqual(chunkPlan(0, 4), [], "an empty artifact has nothing to read");
});

test("chunkPlan rejects a size or chunk that cannot be read", () => {
  assert.throws(() => chunkPlan(-1, 4));
  assert.throws(() => chunkPlan(1.5, 4));
  assert.throws(() => chunkPlan(10, 0));
  assert.throws(() => chunkPlan(10, -4));
});

test("retrieve reassembles a payload byte-for-byte through readChunk", async () => {
  // The point of the script: a 2.6 MB artifact is pulled in bounded chunks and the
  // result must be identical to the source, so a truncated stream cannot pass.
  const source = randomBytes(DEFAULT_CHUNK * 2 + 1234);
  const seen = [];
  const out = await retrieve({
    size: source.length,
    chunk: DEFAULT_CHUNK,
    readChunk: async (skip, count) => {
      seen.push({ skip, count });
      return source.subarray(skip, skip + count);
    },
  });
  assert.equal(out.length, source.length);
  assert.equal(md5(out), md5(source));
  assert.deepEqual(seen, chunkPlan(source.length, DEFAULT_CHUNK));
});

test("retrieve refuses a short chunk instead of concatenating it", async () => {
  // A real truncation arrived as 2,262,523 bytes for a 2,664,994-byte file; that must
  // fail here rather than be written out as a plausible video.
  await assert.rejects(
    () => retrieve({ size: 100, chunk: 50, readChunk: async (skip, count) => Buffer.alloc(count - 1) }),
    /expected 50/
  );
});

test("retrieve refuses a short total and a non-Buffer chunk", async () => {
  await assert.rejects(() => retrieve({ size: 10, readChunk: async () => "not a buffer" }), /did not return a Buffer/);
  await assert.rejects(() => retrieve({ size: 0, readChunk: async () => Buffer.alloc(0) }), /size is required/);
  await assert.rejects(() => retrieve({ size: 10 }), /readChunk is required/);
});

test("parseArgs reads the documented flags and rejects a stray one", () => {
  assert.deepEqual(parseArgs(["--session", "s1", "--name", "out.gif", "--dest", "/tmp/x.gif"]), {
    session: "s1",
    name: "out.gif",
    dest: "/tmp/x.gif",
  });
  assert.deepEqual(parseArgs(["--help"]), { help: true });
  assert.throws(() => parseArgs(["session"]), /unexpected argument/);
  assert.throws(() => parseArgs(["--session"]), /needs a value/);
});
