import { test } from "node:test";
import assert from "node:assert/strict";

process.env.RENDER_STORE_DIR = `${process.env.TMPDIR || "/tmp"}/hf-store-test-${process.pid}`;
const { saveAsset, readAsset, sweep } = await import("../src/store.mjs");

test("save returns a content-addressed id and a fetchable file", () => {
  const buf = Buffer.from("hello-mp4");
  const a = saveAsset(buf);
  assert.match(a.id, /^[0-9a-f]{32}$/);
  assert.equal(a.url, `/files/${a.id}.mp4`);
  assert.deepEqual(readAsset(a.id), buf);
});

test("the same bytes give the same id", () => {
  assert.equal(saveAsset(Buffer.from("x")).id, saveAsset(Buffer.from("x")).id);
});

test("an unknown id is null", () => {
  assert.equal(readAsset("0".repeat(32)), null);
});

test("a path-traversal id is rejected", () => {
  assert.equal(readAsset("../etc/passwd"), null);
});

test("sweep removes nothing fresh", () => {
  saveAsset(Buffer.from("fresh"));
  assert.equal(sweep(), 0);
});
