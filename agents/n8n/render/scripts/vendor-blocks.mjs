#!/usr/bin/env node
// Vendor HyperFrames catalog items into vendor/blocks/.
//
// HyperFrames' `add` installs a block by writing its file and recording a content
// hash in hyperframes.lock.json. We run it into a scratch project and copy the
// result here, rather than running it in place, for two reasons:
//
//   1. The lock file is keyed by output path, so running `add` repeatedly in this
//      directory accumulates stale entries pointing at paths that no longer
//      exist. A fresh scratch dir yields exactly the hashes for this run.
//   2. It keeps `.hyperframes-scratch/` out of the image (see .dockerignore) while
//      the vendored files and their recorded hash are committed.
//
// The hash is the point: it makes a re-vendor a reviewable diff instead of a
// silent overwrite, which is the whole reason a vendored copy is safe to carry.
//
// Usage:
//   node scripts/vendor-blocks.mjs                 # vendor everything in blocks.json
//   node scripts/vendor-blocks.mjs animated-bar-chart

import { execFileSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const PKG = join(HERE, "..");
const SCRATCH = join(PKG, ".hyperframes-scratch");
const DEST = join(PKG, "vendor", "blocks");
const LOCK = join(DEST, "lock.json");
const MANIFEST = join(PKG, "blocks.json");

const HF = join(PKG, "node_modules", ".bin", "hyperframes");

// The package version is the registry pin. Reading it means the vendored blocks
// and the HyperFrames that renders them can never disagree about a version.
const VERSION = JSON.parse(readFileSync(join(PKG, "package.json"), "utf8")).dependencies.hyperframes;

function manifest() {
  if (!existsSync(MANIFEST)) throw new Error(`missing ${MANIFEST}`);
  return JSON.parse(readFileSync(MANIFEST, "utf8"));
}

// The only remote reference a block is allowed to carry is GSAP, and only one we
// can satisfy locally. Anything else is a hard failure: a block that needs another
// remote asset cannot render offline and must not be committed.
const GSAP_CDN = /<script\s+src=["']https?:\/\/[^"']*gsap[^"']*["']\s*>\s*<\/script>/gi;
const ANY_REMOTE = /(src|href)=["']https?:\/\/[^"']+["']/gi;

function rewriteRemoteScripts(body) {
  const rewritten = [];
  const out = body.replace(GSAP_CDN, (match) => {
    rewritten.push(match);
    // Relative to the composition, which the renderer writes beside ./vendor/.
    return `<script src="./vendor/gsap.min.js"></script>`;
  });
  const remaining = out.match(ANY_REMOTE) || [];
  return { body: out, rewritten, remaining };
}

function vendor(name) {
  mkdirSync(SCRATCH, { recursive: true });
  // The scratch project's own config decides where `add` writes. Pointing both
  // paths at the same dir keeps the block file flat under vendor/blocks/.
  writeFileSync(
    join(SCRATCH, "hyperframes.json"),
    JSON.stringify(
      {
        registry: "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
        paths: { blocks: "vendor/blocks", components: "vendor/blocks" },
      },
      null,
      2
    )
  );

  const out = execFileSync(
    HF,
    ["add", name, "--no-clipboard", "--json"],
    { cwd: SCRATCH, encoding: "utf8", env: { ...process.env, HYPERFRAMES_SKIP_SKILLS: "1" } }
  );
  const result = JSON.parse(out.trim().split("\n").pop());
  if (!result.ok) throw new Error(`add ${name} failed: ${JSON.stringify(result)}`);

  const scratchLock = JSON.parse(readFileSync(join(SCRATCH, "hyperframes.lock.json"), "utf8"));
  const written = result.written.map((p) => p.replace(`${SCRATCH}/`, ""));
  const hash = scratchLock[written[0]];
  if (!hash) throw new Error(`no content hash recorded for ${written[0]}`);

  const destFile = join(DEST, `${name}.html`);
  cpSync(join(SCRATCH, written[0]), destFile);

  // A full block loads GSAP from a CDN (components do not). We render offline, so
  // rewrite that reference to the vendored copy. The patch is mechanical and the
  // upstream hash stays recorded, so a re-vendor shows the edit as a diff.
  const patched = rewriteRemoteScripts(readFileSync(destFile, "utf8"));
  writeFileSync(destFile, patched.body);
  if (patched.rewritten.length) {
    console.log(`${name}: rewrote ${patched.rewritten.length} CDN script ref(s) to vendor/gsap.min.js`);
  }
  if (patched.remaining.length) {
    throw new Error(
      `${name} still references a remote resource after rewrite (${patched.remaining.join(", ")}); ` +
        `vendor it or strip it before committing`
    );
  }

  console.log(`${name}: vendored from ${VERSION} (${hash.slice(0, 12)})`);
  return { name, hash, source: written[0], rewritten: patched.rewritten.length };
}

function main() {
  const wanted = process.argv.slice(2);
  const items = wanted.length ? wanted : manifest().blocks;
  if (!items.length) throw new Error("nothing to vendor: blocks.json lists no blocks");

  rmSync(SCRATCH, { recursive: true, force: true });
  // Rebuild from empty so the directory reflects the manifest exactly: a block
  // removed from blocks.json must not survive as a stale, unreferenced file that
  // the image still ships.
  rmSync(DEST, { recursive: true, force: true });
  mkdirSync(DEST, { recursive: true });

  const entries = {};
  for (const name of items) {
    const v = vendor(name);
    entries[v.name] = {
      hash: v.hash,
      hyperframes: VERSION,
      source: v.source,
      // Non-zero means we edited the block after vendoring (the CDN rewrite). A
      // re-vendor that changes this number is a change to how we patch upstream.
      rewrittenRefs: v.rewritten,
    };
  }

  // Rewritten wholesale so it describes this run exactly, never an accumulation.
  writeFileSync(LOCK, JSON.stringify({ hyperframes: VERSION, blocks: entries }, null, 2) + "\n");
  rmSync(SCRATCH, { recursive: true, force: true });
  console.log(`wrote ${Object.keys(entries).length} block(s) to vendor/blocks/ and ${LOCK}`);
}

main();
