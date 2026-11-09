// The writer's ledger contract, tested without a network and without a model.
//
// The ledger is derived from the turn's transcript: the pod brokered every scrape, so the
// text the model received is the evidence, and a fence either appears in it or it does not.

import { test } from "node:test";
import assert from "node:assert/strict";
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
  findExcerpt,
  transcriptPages,
  deriveLedger,
  agentSettings,
  DEFAULT_COMPACTION,
  DEFAULT_CONTEXT_WINDOW,
  DEFAULT_MODEL_MAX_TOKENS,
  articleTurnInstruction,
  mcpConfig,
} from "../session-lib.mjs";

const hash = (text) => createHash("sha256").update(text, "utf8").digest("hex");

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

test("the settings compact a session at a share of the window", () => {
  const settings = agentSettings();
  assert.equal(settings.compaction.enabled, true);
  // 80% of 500000 triggers, so the reserve is the remaining 100000.
  // 80% triggers, but the reserve is floored at the gateway's output cap plus a margin:
  // 131072 + 16384 leaves less room than 20% of the window, and the cap is the truth.
  assert.equal(settings.compaction.reserveTokens, DEFAULT_MODEL_MAX_TOKENS + 16_384);
  assert.equal(settings.compaction.keepRecentTokens, 25_000);
  assert.equal(DEFAULT_COMPACTION.triggerPercent, 80);
  assert.equal(DEFAULT_MODEL_MAX_TOKENS, 131_072, "the gateway's max_output_tokens");
  assert.equal(DEFAULT_CONTEXT_WINDOW, 500_000, "the gateway serves 500000 input tokens");
});

test("the share follows the window, and the reserve keeps room for the answer", () => {
  const big = agentSettings({ contextWindow: 1_000_000 });
  assert.equal(big.compaction.reserveTokens, 200_000, "20% of a window wider than the cap wins");
  assert.equal(big.compaction.keepRecentTokens, 50_000);
  // A small window with a large output cap: the reserve is the cap plus the margin, not 20%.
  const small = agentSettings({ contextWindow: 100_000, maxTokens: 40_000 });
  assert.equal(small.compaction.reserveTokens, 40_000 + 16_384);
  assert.throws(() => agentSettings({ compactionTriggerPercent: 100 }), /between 0 and 100/);
  assert.throws(() => agentSettings({ compactionTriggerPercent: 0 }), /between 0 and 100/);
  assert.throws(() => agentSettings({ compactionKeepPercent: 90 }), /smaller than the trigger/);
});


// A transcript row pair, in the shape Pi writes: the call carries the URL, the result the
// text the model received.
const scrapeRows = (url, text, id = "call_1") => [
  { type: "message", message: { role: "assistant", content: [{ type: "toolCall", id, name: "mcp__firecrawl__firecrawl_scrape", arguments: { url, formats: ["markdown"] } }] } },
  { type: "message", message: { role: "toolResult", toolCallId: id, toolName: "mcp__firecrawl__firecrawl_scrape", content: [{ type: "text", text }], isError: false } },
];

test("a scrape pair becomes a page with its URL and the text the model saw", () => {
  const rows = [
    ...scrapeRows("https://github.com/o/r/blob/main/docs.md", "intro\n\napiVersion: v1\nkind: ConfigMap\n"),
    // A tool that is not a scrape is not a source: the ledger only cites pages it read.
    { type: "message", message: { role: "assistant", content: [{ type: "toolCall", id: "call_2", name: "mcp__github__search_code", arguments: { query: "x" } }] } },
    { type: "message", message: { role: "toolResult", toolCallId: "call_2", toolName: "mcp__github__search_code", content: [{ type: "text", text: "apiVersion: v1 kind: ConfigMap" }] } },
  ];
  const pages = transcriptPages(rows);
  assert.equal(pages.length, 1);
  assert.equal(pages[0].url, "https://github.com/o/r/blob/main/docs.md");
  assert.match(pages[0].text, /kind: ConfigMap/);
});

test("Firecrawl's JSON wrapper is unwrapped before matching", () => {
  const rows = scrapeRows(
    "https://raw.githubusercontent.com/o/r/main/x.yaml",
    JSON.stringify({ markdown: "apiVersion: v1\nkind: Secret" })
  );
  assert.equal(transcriptPages(rows)[0].text, "apiVersion: v1\nkind: Secret");
});

test("the truncated text the model saw is what a block is matched against", () => {
  // Pi prefixes a truncated result; text beyond the cut was never read, so a fence that only
  // exists past it must not verify.
  const seen = "Warning: truncated output (original token count: 900)\napiVersion: v1";
  const rows = scrapeRows("https://github.com/o/r/blob/main/x.yaml", seen);
  const article = "# T\n\n```yaml\napiVersion: v1\nkind: Pod\n```\n";
  const { sources, unquoted } = deriveLedger({ article, pages: transcriptPages(rows) });
  assert.deepEqual(sources, []);
  assert.deepEqual(unquoted, ["apiVersion: v1"]);
});

test("a block on a scraped page is ledgered with that page and nothing else", () => {
  const page = "# Docs\n\n```bash\nhelm upgrade --install probe ./chart\n```\n";
  const rows = scrapeRows("https://github.com/o/r/blob/main/README.md", page);
  const article = "# T\n\n```bash\nhelm upgrade --install probe ./chart\n```\n";
  const { sources, unquoted } = deriveLedger({ article, pages: transcriptPages(rows) });
  assert.deepEqual(unquoted, []);
  assert.equal(sources.length, 1);
  assert.equal(sources[0].url, "https://github.com/o/r/blob/main/README.md");
  assert.equal(sources[0].found, true);
  assert.equal(sources[0].validated, "none");
  assert.equal(sources[0].sha256, sha256Hex(normaliseBlock("helm upgrade --install probe ./chart")));
  // The gate reads the file this serialises.
  assert.match(serialiseLedger(sources), /README\.md/);
});

test("a heredoc no page carries is unquoted, and the first page that carries it wins", () => {
  const heredoc = "kubectl apply -f - <<EOF\napiVersion: v1\nkind: Namespace\nmetadata:\n  name: demo\nEOF";
  const withIt = scrapeRows("https://raw.githubusercontent.com/o/r/main/a.yaml", `x\n${heredoc}\ny`, "call_a");
  const alsoIt = scrapeRows("https://raw.githubusercontent.com/o/r/main/b.yaml", `x\n${heredoc}\ny`, "call_b");
  const invented = "kubectl patch sympoziumschedule sre-watchdog-schedule --type=merge -p '{}'";
  const article = `# T\n\n\`\`\`bash\n${heredoc}\n\`\`\`\n\n\`\`\`bash\n${invented}\n\`\`\`\n`;
  const { sources, unquoted } = deriveLedger({ article, pages: transcriptPages([...alsoIt, ...withIt]) });
  assert.equal(sources.length, 1);
  assert.equal(sources[0].url, "https://raw.githubusercontent.com/o/r/main/b.yaml", "the first scraped page wins");
  assert.equal(unquoted.length, 1);
  assert.match(unquoted[0], /kubectl patch sympoziumschedule/);
});

test("no scrape at all leaves every fence unquoted and no entry invented", () => {
  const article = "```bash\nkubectl get pods\n```\n";
  const { sources, unquoted } = deriveLedger({ article, pages: [] });
  assert.deepEqual(sources, []);
  assert.deepEqual(unquoted, ["kubectl get pods"]);
});

// A long page arrives with its middle removed and its full text spilled to a file. Reading that
// file is the same page, so a block that fell in the removed part still counts.
test("a read of the spilled scrape output is attributed to the page", () => {
  const rows = [
    { type: "message", message: { role: "assistant", content: [{ type: "toolCall", id: "call_s", name: "mcp__firecrawl__firecrawl_scrape", arguments: { url: "https://raw.githubusercontent.com/o/r/main/README.md" } }] } },
    {
      type: "message",
      message: {
        role: "toolResult",
        toolCallId: "call_s",
        toolName: "mcp__firecrawl__firecrawl_scrape",
        content: [{ type: "text", text: "head…middle truncated…tail" }],
        details: { fullOutputPath: "/tmp/pi-mcp-abc.txt" },
      },
    },
    { type: "message", message: { role: "assistant", content: [{ type: "toolCall", id: "call_r", name: "read", arguments: { path: "/tmp/pi-mcp-abc.txt", offset: 200 } }] } },
    { type: "message", message: { role: "toolResult", toolCallId: "call_r", toolName: "read", content: [{ type: "text", text: "apiVersion: v1\nkind: ConfigMap" }] } },
  ];
  const pages = transcriptPages(rows);
  assert.equal(pages.length, 2);
  assert.equal(pages[1].url, "https://raw.githubusercontent.com/o/r/main/README.md");
  const article = "```yaml\napiVersion: v1\nkind: ConfigMap\n```\n";
  const { sources } = deriveLedger({ article, pages });
  assert.equal(sources.length, 1);
  assert.equal(sources[0].url, "https://raw.githubusercontent.com/o/r/main/README.md");
});

// The structural half: an article shows a resource the docs describe, and the docs rarely
// print the exact YAML the article needs. A composed block is evidence when every name in it
// is on a page this run read; an invented name still fails, and now the reason names it.
const ENSEMBLES_PAGE = `# Ensembles

An Ensemble is a pack of Agents. The example below is called research-pipeline, with a lead
and an analyst. It is applied with \`kubectl apply -f ensemble.yaml\`.

apiVersion: sympozium.ai/v1alpha1
kind: Ensemble
metadata:
  name: research-pipeline
spec:
  workflowType: pipeline
  agentConfigs:
    - name: lead
      systemPrompt: "You are a lead."
    - name: analyst
      systemPrompt: "You are an analyst."
`;

test("a composed block whose names are all on a page is derived, with that page", () => {
  const rows = scrapeRows("https://raw.githubusercontent.com/o/r/main/docs/concepts/ensembles.md", ENSEMBLES_PAGE);
  const composed = [
    "apiVersion: sympozium.ai/v1alpha1",
    "kind: Ensemble",
    "metadata:",
    "  name: research-pipeline",
    "spec:",
    "  workflowType: pipeline",
    "  agentConfigs:",
    "    - name: analyst",
    "      systemPrompt: \"You are an analyst.\"",
  ].join("\n");
  const article = `# T\n\n\`\`\`yaml\n${composed}\n\`\`\`\n`;
  const { sources, unquoted } = deriveLedger({ article, pages: transcriptPages(rows) });
  assert.deepEqual(unquoted, []);
  assert.equal(sources.length, 1);
  assert.equal(sources[0].mode, "derived", "not a byte copy, so it is verified by its names");
  assert.match(sources[0].url, /docs\/concepts\/ensembles\.md/);
  assert.equal(sources[0].found, true);
  assert.equal(sources[0].excerpt, "");
});

test("a composed block naming an object no page carries is rejected, and the reason names it", () => {
  const rows = scrapeRows("https://raw.githubusercontent.com/o/r/main/docs/concepts/ensembles.md", ENSEMBLES_PAGE);
  const composed = "apiVersion: sympozium.ai/v1alpha1\nkind: Ensemble\nmetadata:\n  name: my-first-agent-heartbeat\nspec:\n  workflowType: pipeline\n";
  const article = `# T\n\n\`\`\`yaml\n${composed}\n\`\`\`\n`;
  const { sources, unquoted, unquotedBlocks } = deriveLedger({ article, pages: transcriptPages(rows) });
  assert.deepEqual(sources, []);
  assert.equal(unquoted.length, 1);
  assert.match(unquotedBlocks[0].reason, /my-first-agent-heartbeat/);
});

test("a YAML block with a line that is not a field is rejected as malformed", () => {
  const rows = scrapeRows("https://raw.githubusercontent.com/o/r/main/docs.md", "kind: Ensemble\nname: lead\n");
  const article = "# T\n\n```yaml\nkind: Ensemble\nname: lead\nthis line is not a field\n```\n";
  const { sources, unquotedBlocks } = deriveLedger({ article, pages: transcriptPages(rows) });
  assert.deepEqual(sources, []);
  assert.match(unquotedBlocks[0].reason, /unparsed line/);
});

test("a composed command whose flags and names are documented is derived", () => {
  const page = "Create the secret with `kubectl create secret generic my-openai-key --from-literal=OPENAI_API_KEY=sk-test`.";
  const rows = scrapeRows("https://raw.githubusercontent.com/o/r/main/docs/getting-started.md", page);
  const article = "# T\n\n```bash\nkubectl create secret generic my-openai-key \\\n  --from-literal=OPENAI_API_KEY=sk-test\n```\n";
  const { sources, unquoted } = deriveLedger({ article, pages: transcriptPages(rows) });
  assert.deepEqual(unquoted, []);
  assert.equal(sources[0].mode, "derived");
});

test("a byte-for-byte copy stays quoted and keeps its excerpt", () => {
  const page = "# Docs\n\n```bash\nhelm upgrade --install probe ./chart\n```\n";
  const rows = scrapeRows("https://raw.githubusercontent.com/o/r/main/README.md", page);
  const article = "# T\n\n```bash\nhelm upgrade --install probe ./chart\n```\n";
  const { sources } = deriveLedger({ article, pages: transcriptPages(rows) });
  assert.equal(sources[0].mode, "quoted");
  assert.equal(sources[0].excerpt, "helm upgrade --install probe ./chart");
});

test("the ledger round-trips the mode the gate reads", () => {
  const page = ENSEMBLES_PAGE;
  const rows = scrapeRows("https://raw.githubusercontent.com/o/r/main/docs/concepts/ensembles.md", page);
  const article = "# T\n\n```yaml\napiVersion: sympozium.ai/v1alpha1\nkind: Ensemble\nmetadata:\n  name: research-pipeline\nspec:\n  workflowType: pipeline\n  agentConfigs:\n    - name: analyst\n```\n";
  const { sources } = deriveLedger({ article, pages: transcriptPages(rows) });
  const parsed = parseLedger(serialiseLedger(sources));
  assert.equal(parsed[0].mode, "derived");
});
