// The writer's ledger contract, tested without a network and without a model.
//
// The ledger is the part the model does not own: these tests pin the policy the server
// applies to every URL it is asked to verify, and the matching rule a fence has to pass.

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { createHash } from "node:crypto";

import {
  ARTICLE_NAME,
  LEDGER_NAME,
  parseSourceHosts,
  fillSourceHosts,
  fillTemplate,
  DEFAULT_ARTICLE_SOURCE_HOSTS,
  normaliseBlock,
  extractFencedBlocks,
  parseLedger,
  serialiseLedger,
  sha256Hex,
  sourceUrlRefusal,
  findExcerpt,
  revalidateLedger,
  scrapeReader,
  articleTurnInstruction,
  mcpConfig,
} from "../session-lib.mjs";

const hash = (text) => createHash("sha256").update(text, "utf8").digest("hex");

// One local page server stands in for every source. Loopback is allowed only by the
// tests' own policy (`allowLoopback: true`), which is exactly the difference between
// this and production: the production call names neither.
let server;
let base;

before(async () => {
  server = http.createServer((req, res) => {
    if (req.url === "/page") {
      // The same manifest the article fences, at another indentation: the docs render it
      // this way and a line-level comparison would call it a different block.
      res.writeHead(200, { "content-type": "text/plain; charset=utf-8" });
      res.end("intro\n\napiVersion: v1\nkind:    ConfigMap\nmetadata:\n  name: probe\n\noutro\n");
      return;
    }
    if (req.url === "/without") {
      res.writeHead(200, { "content-type": "text/plain" });
      res.end("this page carries no manifest at all");
      return;
    }
    if (req.url === "/redirect-private") {
      res.writeHead(302, { location: "http://169.254.169.254/latest/meta-data/" });
      res.end();
      return;
    }
    if (req.url === "/slow") {
      // Headers arrive, the body never ends: the per-URL budget has to cover the read.
      res.writeHead(200, { "content-type": "text/plain" });
      res.write("apiVersion: v1");
      return;
    }
    if (req.url === "/huge") {
      res.writeHead(200, { "content-type": "text/plain" });
      res.write("a".repeat(2000));
      // The fence sits beyond the cap, so finding it would mean the cap did not apply.
      res.end("apiVersion: v1 kind: ConfigMap metadata: name: late");
      return;
    }
    res.writeHead(404, { "content-type": "text/plain" });
    res.end("missing");
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});

after(async () => {
  await new Promise((resolve) => server.close(resolve));
});

const localPolicy = (opts = {}) => ({
  fetchUrl: fetch,
  allowedHosts: ["127.0.0.1"],
  requireHttps: false,
  allowLoopback: true,
  ...opts,
});

test("the contract names the two files the turn writes", () => {
  assert.equal(ARTICLE_NAME, "article.md");
  assert.equal(LEDGER_NAME, "sources.json");
});

test("the source hosts default to the fleet's own pages, and the caller's list wins", () => {
  assert.deepEqual(DEFAULT_ARTICLE_SOURCE_HOSTS, [
    "github.com",
    "raw.githubusercontent.com",
    "datahub-local.alvsanand.com",
  ]);
  assert.deepEqual(parseSourceHosts(""), DEFAULT_ARTICLE_SOURCE_HOSTS);
  assert.deepEqual(parseSourceHosts("GitHub.com, https://raw.githubusercontent.com/x/y"), [
    "github.com",
    "raw.githubusercontent.com",
  ]);
  assert.equal(fillSourceHosts("read {{ ARTICLE_SOURCE_HOSTS }}", ["a.example"]), "read a.example");
});

test("a placeholder with no value is left visible", () => {
  // Left visible on purpose: an unknown `{{ NAME }}` is a prompt bug the turn should
  // report, and filling it with "" would hide the bug inside the drafted article.
  assert.equal(fillTemplate("a {{ KNOWN }} b {{ NOT_A_FIELD }}", { KNOWN: "x" }), "a x b {{ NOT_A_FIELD }}");
  assert.equal(fillTemplate("budget {{ MAX_WORDS }}", { MAX_WORDS: "" }), "budget ");
});

test("a fenced block is the fence's body and nothing else", () => {
  const markdown = "# T\n\n```bash\nhelm upgrade --install probe ./chart\n```\n\nprose\n";
  assert.deepEqual(extractFencedBlocks(markdown), [
    { lang: "bash", block: "helm upgrade --install probe ./chart" },
  ]);
  // An unterminated fence is prose that was cut off, not half a manifest.
  assert.deepEqual(extractFencedBlocks("```yaml\napiVersion: v1\n"), []);
});

test("a block matches its page with whitespace collapsed, not line by line", () => {
  const block = "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: probe";
  assert.ok(findExcerpt("intro apiVersion: v1 kind:    ConfigMap metadata: name: probe outro", block));
  assert.equal(findExcerpt("apiVersion: v1 kind: Secret", block), null);
  assert.equal(normaliseBlock("a\n  b\t c "), "a b c");
});

test("the ledger accepts both shapes and rewrites them as the object", () => {
  const entry = { block: "kubectl get pods", url: "https://github.com/x", validated: "dry-run" };
  assert.deepEqual(parseLedger(JSON.stringify([entry])), [{ ...entry, validation_error: "" }]);
  assert.deepEqual(parseLedger(JSON.stringify({ sources: [entry] })), [
    { ...entry, validation_error: "" },
  ]);
  assert.equal(parseLedger(JSON.stringify({ sources: [{ ...entry, validated: "yes" }] }))[0].validated, "none");
  assert.throws(() => parseLedger("{}"), /no sources array/);
  assert.match(serialiseLedger([entry]), /"sources": \[/);
});

test("the ledger's match is the page's own text, and a whitespace difference still matches", async () => {
  const block = "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: probe";
  const { sources, dropped } = await revalidateLedger([{ block, url: `${base}/page` }], localPolicy());
  assert.deepEqual(dropped, []);
  assert.equal(sources.length, 1);
  assert.equal(sources[0].found, true);
  assert.equal(sources[0].status, 200);
  assert.equal(sources[0].sha256, sha256Hex(normaliseBlock(block)));
  assert.equal(
    sources[0].body_sha256,
    hash("intro\n\napiVersion: v1\nkind:    ConfigMap\nmetadata:\n  name: probe\n\noutro\n")
  );
  assert.ok(sources[0].excerpt.includes("kind:    ConfigMap"), "the excerpt is the page's text");
});

test("a page that does not carry the block keeps the entry as found: false", async () => {
  // The URL answered, so the entry is not about a missing page: it is about a line the
  // article claims the page says. The gate rejects it; the server does not delete it.
  const { sources, dropped } = await revalidateLedger(
    [{ block: "helm install probe ./chart", url: `${base}/without` }],
    localPolicy()
  );
  assert.deepEqual(dropped, []);
  assert.equal(sources[0].found, false);
  assert.equal(sources[0].excerpt, "");
  assert.equal(sources[0].sha256, "");
});

test("an entry whose URL does not answer is dropped, with the status named", async () => {
  const { sources, dropped } = await revalidateLedger(
    [{ block: "helm install probe ./chart", url: `${base}/missing` }],
    localPolicy()
  );
  assert.deepEqual(sources, []);
  assert.equal(dropped.length, 1);
  assert.match(dropped[0].reason, /HTTP 404/);
});

test("an entry with no URL is dropped rather than matched against nothing", async () => {
  const { sources, dropped } = await revalidateLedger([{ block: "helm install probe" }], localPolicy());
  assert.deepEqual(sources, []);
  assert.equal(dropped[0].reason, "no url");
});

test("the fetch refuses http, credentials, loopback, link-local and private addresses", () => {
  const allow = { allowedHosts: ["github.com", "10.0.0.1", "169.254.169.254", "localhost"] };
  assert.equal(sourceUrlRefusal("http://github.com/x", allow), "not https");
  assert.equal(sourceUrlRefusal("https://user:pass@github.com/x", allow), "carries credentials");
  assert.match(sourceUrlRefusal("https://10.0.0.1/x", allow), /private or loopback/);
  assert.match(sourceUrlRefusal("https://169.254.169.254/latest/meta-data/", allow), /private or loopback/);
  assert.match(sourceUrlRefusal("https://localhost/x", allow), /private or loopback/);
  assert.match(sourceUrlRefusal("https://example.com/x", allow), /not a declared source host/);
  assert.equal(sourceUrlRefusal("https://github.com/x", allow), null);
  // The address checks are about literals, and neither they nor the redirect check resolve a
  // name: an allowlisted host that resolves privately is the residual risk recorded in design D10.
  assert.match(sourceUrlRefusal("file:///etc/passwd", allow), /not http or https/);
  // The loopback exemption a test needs does not reach a link-local address.
  const loopback = { allowedHosts: ["127.0.0.1", "169.254.169.254"], allowLoopback: true, requireHttps: false };
  assert.equal(sourceUrlRefusal("http://127.0.0.1/x", loopback), null);
  assert.match(sourceUrlRefusal("http://169.254.169.254/x", loopback), /private or loopback/);
});

test("a redirect to a private address is refused before it is followed", async () => {
  const { sources, dropped } = await revalidateLedger(
    [{ block: "apiVersion: v1", url: `${base}/redirect-private` }],
    localPolicy()
  );
  assert.deepEqual(sources, []);
  assert.match(dropped[0].reason, /private or loopback/);
});

test("the per-URL timeout covers the body, not only the headers", async () => {
  // A page that sends a response line and then dribbles would otherwise hold the
  // serialized turn open until the caller's own timeout.
  const { sources, dropped } = await revalidateLedger(
    [{ block: "apiVersion: v1", url: `${base}/slow` }],
    localPolicy({ timeoutMs: 150 })
  );
  assert.deepEqual(sources, []);
  assert.match(dropped[0].reason, /did not answer/);
});

test("a body is capped, so a page cannot hide a fence beyond the cap", async () => {
  const block = "apiVersion: v1 kind: ConfigMap metadata: name: late";
  const capped = await revalidateLedger([{ block, url: `${base}/huge` }], localPolicy({ maxBytes: 500 }));
  assert.equal(capped.sources[0].found, false, "the fetch read past its cap");
  const whole = await revalidateLedger([{ block, url: `${base}/huge` }], localPolicy({ maxBytes: 10_000 }));
  assert.equal(whole.sources[0].found, true, "the same page carries the fence below the cap");
});

test("the catalog config declares the read tools and hides the rest", () => {
  const { mcpServers } = mcpConfig({
    githubUrl: "http://github.invalid/mcp",
    firecrawlUrl: "http://firecrawl.invalid/mcp",
  });
  assert.equal(mcpServers.github.url, "http://github.invalid/mcp");
  assert.equal(mcpServers.github.exposure, "hidden");
  assert.equal(mcpServers.github.toolExposure.search_code, "direct");
  // The catalog's server carries write tools; a drafting turn may not reach them.
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

test("a turn says whether it authors or corrects", () => {
  assert.ok(articleTurnInstruction({ isIteration: false }).includes("Write the article to `article.md`"));
  assert.ok(articleTurnInstruction({ isIteration: false }).includes("`sources.json`"));
  const correction = articleTurnInstruction({ isIteration: true });
  assert.ok(correction.includes("earlier"));
  assert.ok(correction.includes("in place"));
  assert.ok(correction.includes("re-reading only what it names"));
});

// The pod has no internet egress: the only reader that leaves it is the Firecrawl MCP
// server, so a session there verifies its ledger through that server. These pin the two
// halves -- the call the reader makes, and the fact that it does not replace the policy.
const stubScrape = (body, { status = 200 } = {}) => {
  const calls = [];
  const fetchUrl = async (url, init) => {
    calls.push({ url, init });
    return new Response(body, { status });
  };
  return { fetchUrl, calls };
};

test("the scrape reader calls firecrawl_scrape and unwraps an SSE answer", async () => {
  const answer = {
    jsonrpc: "2.0",
    id: 1,
    result: { content: [{ type: "text", text: "```bash\nhelm install probe ./chart\n```" }] },
  };
  const { fetchUrl, calls } = stubScrape(`event: message\ndata: ${JSON.stringify(answer)}\n\n`);
  const read = scrapeReader({ endpoint: "http://firecrawl.invalid/mcp", fetchUrl });
  const page = await read("https://github.com/o/r/blob/main/README.md");
  assert.equal(page.refusal, undefined);
  assert.match(page.body, /helm install probe/);
  const sent = JSON.parse(calls[0].init.body);
  assert.equal(calls[0].url, "http://firecrawl.invalid/mcp");
  assert.equal(sent.method, "tools/call");
  assert.equal(sent.params.name, "firecrawl_scrape");
  assert.equal(sent.params.arguments.url, "https://github.com/o/r/blob/main/README.md");
});

test("the scrape reader unwraps the JSON body Firecrawl wraps its markdown in", async () => {
  const answer = {
    jsonrpc: "2.0",
    id: 1,
    result: {
      content: [{ type: "text", text: JSON.stringify({ markdown: "apiVersion: v1\nkind: ConfigMap" }) }],
    },
  };
  const { fetchUrl } = stubScrape(JSON.stringify(answer));
  const page = await scrapeReader({ endpoint: "http://firecrawl.invalid/mcp", fetchUrl })(
    "https://github.com/o/r/raw/main/x.yaml"
  );
  assert.equal(page.body, "apiVersion: v1\nkind: ConfigMap");
});

test("a scrape that answers an error is a refusal naming it", async () => {
  const answer = { jsonrpc: "2.0", id: 1, error: { code: -32000, message: "scrape timed out" } };
  const { fetchUrl } = stubScrape(JSON.stringify(answer));
  const page = await scrapeReader({ endpoint: "http://firecrawl.invalid/mcp", fetchUrl })(
    "https://github.com/o/r"
  );
  assert.match(page.refusal, /scrape timed out/);
});

test("a scrape server that answers nothing usable is a refusal, not an empty page", async () => {
  const { fetchUrl } = stubScrape("not a payload");
  const page = await scrapeReader({ endpoint: "http://firecrawl.invalid/mcp", fetchUrl })(
    "https://github.com/o/r"
  );
  assert.match(page.refusal, /not an MCP payload/);
  const down = await scrapeReader({ endpoint: "http://firecrawl.invalid/mcp", fetchUrl: stubScrape("", { status: 503 }).fetchUrl })(
    "https://github.com/o/r"
  );
  assert.match(down.refusal, /HTTP 503/);
  assert.equal(scrapeReader({ endpoint: "" }), null);
});

test("a reader verifies the block through the scrape server", async () => {
  const scraped = "intro\n\napiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: probe\n";
  const seen = [];
  const reader = async (url) => {
    seen.push(url);
    return { status: 200, body: scraped };
  };
  const { sources, dropped } = await revalidateLedger(
    [{ block: "apiVersion: v1\nkind: ConfigMap", url: "https://github.com/o/r/blob/main/x.yaml" }],
    { allowedHosts: ["github.com"], reader }
  );
  assert.deepEqual(dropped, []);
  assert.equal(sources[0].found, true);
  assert.deepEqual(seen, ["https://github.com/o/r/blob/main/x.yaml"]);
});

test("a reader does not bypass the source-host policy", async () => {
  let read = false;
  const reader = async () => {
    read = true;
    return { status: 200, body: "apiVersion: v1" };
  };
  const { sources, dropped } = await revalidateLedger(
    [{ block: "apiVersion: v1", url: "https://elsewhere.example/x" }],
    { allowedHosts: ["github.com"], reader }
  );
  assert.equal(read, false, "an off-list host was scraped");
  assert.deepEqual(sources, []);
  assert.match(dropped[0].reason, /not a declared source host/);
});
