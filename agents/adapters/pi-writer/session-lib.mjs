// Pure helpers for the pi-writer session server: request/artifact path safety, Pi's
// retry settings, and the source ledger the server verifies after every turn. Kept out
// of session-server.mjs so they can be unit-tested with `node --test` without starting
// the HTTP server.

import { basename, join, normalize, sep } from "node:path";
import { stat } from "node:fs/promises";
import { createHash } from "node:crypto";

// The shape session-server.mjs accepts for session_id: a run identifier that is
// safe as a single path segment. `.` and `..` are excluded even though the
// character class would allow them — as a directory segment they escape the runs
// directory.
export const SESSION_ID_RE = /^(?!\.{1,2}$)[a-zA-Z0-9._-]{1,80}$/;

// The two files a turn writes, and the only names the artifact route serves. A name
// outside this list is refused, so the route stays a whitelist rather than a path a
// caller can steer.
export const ARTICLE_NAME = "article.md";
export const LEDGER_NAME = "sources.json";

// A session container mounts the session PVC at /tmp and does not mount /workspace
// (only the Job path does). The default workspace must therefore live under /tmp, or
// the first turn fails with "mkdir '/workspace/runs'".
export const DEFAULT_SESSION_WORKSPACE = "/tmp/pi-writer";

export function isValidSessionId(value) {
  return typeof value === "string" && SESSION_ID_RE.test(value);
}

export function safeSessionId(value) {
  return isValidSessionId(value) ? value : "default";
}

// <workspace>/runs/<session_id> — one directory per session so a retry continues in
// place and a fresh row is isolated.
export function runDir(workspace, sessionId) {
  return join(workspace, "runs", safeSessionId(sessionId));
}

// Resolve a fetch to an absolute path inside the run directory, or null when the
// name is not an artifact this server writes. `basename` plus a prefix check makes
// traversal (`..`, absolute paths, separators) resolve to null rather than escape.
export function resolveArtifact(workspace, sessionId, name) {
  if (!isValidSessionId(sessionId)) return null;
  if (typeof name !== "string" || !isArticleArtifact(name)) return null;
  if (basename(name) !== name) return null;
  const dir = runDir(workspace, sessionId);
  const full = normalize(join(dir, name));
  if (full !== join(dir, name)) return null;
  if (!full.startsWith(dir + sep)) return null;
  return full;
}

export function isArticleArtifact(name) {
  return name === ARTICLE_NAME || name === LEDGER_NAME;
}

export function contentTypeFor(name) {
  if (name === ARTICLE_NAME) return "text/markdown; charset=utf-8";
  if (name === LEDGER_NAME) return "application/json; charset=utf-8";
  return "application/octet-stream";
}

// Pi names a transcript `<ISO timestamp>_<session id>.jsonl`; the timestamp carries
// no underscore, so the id is everything after the first one. Returns null for a
// name this server did not write, so a foreign file is never swept.
export function sessionIdFromTranscript(name) {
  const match = /^[^_]+_(.+)\.jsonl$/.exec(String(name ?? ""));
  return match ? match[1] : null;
}

// Expired run directories: older than the cutoff, and never the session in flight.
export function expiredRunDirs(entries, { cutoffMs, keep } = {}) {
  return entries
    .filter((e) => Number.isFinite(e.mtimeMs) && e.mtimeMs < cutoffMs && e.name !== keep)
    .map((e) => e.name);
}

// Expired transcripts: older than the cutoff, not the session in flight, and only
// names this server wrote (an unattributable file is left alone).
export function expiredTranscripts(entries, { cutoffMs, keep } = {}) {
  return entries
    .filter((e) => {
      if (!Number.isFinite(e.mtimeMs) || e.mtimeMs >= cutoffMs) return false;
      const id = sessionIdFromTranscript(e.name);
      return id !== null && id !== keep;
    })
    .map((e) => e.name);
}

// The gateway's streaming timeout, and the writer's own settings. Pi reads these
// from `<agent-dir>/settings.json`, which the session server writes beside the
// models.json it already writes; without the file Pi runs on the vendor's defaults
// (idle timeout 300s, three retries) and a stalled call has no tuned window at all.
//
// The idle timeout is the client's patience for one HTTP response, and the gateway's
// `stream_timeout` is the same wait on the far side of the proxy. The client must be
// the more patient of the two, or it abandons an attempt before the gateway reports
// what happened. Measured on the render lane 2026-10-16: the gateway's 30s per-read
// timeout killed nine consecutive attempts.
export const DEFAULT_GATEWAY_STREAM_TIMEOUT_MS = 120_000;
export const DEFAULT_RETRY = {
  idleTimeoutMs: 240_000,
  maxRetries: 6,
  baseDelayMs: 5_000,
  maxAgentDelayMs: 60_000,
};

// The gateway's per-model `max_input_tokens`. LiteLLM serves 500000 for every
// `opencode-go/*` model, so Pi's own window and the compaction trigger both scale from this
// one number: a deployment on a smaller model overrides it with PI_WRITER_CONTEXT_WINDOW.
export const DEFAULT_CONTEXT_WINDOW = 500_000;

// The gateway's per-model output cap. LiteLLM serves `max_output_tokens: 131072` beside the
// 500000 input limit, so this is the number Pi's request may reserve, not a preference of
// ours; a deployment that wants a smaller answer sets PI_WRITER_MAX_TOKENS.
export const DEFAULT_MODEL_MAX_TOKENS = 131_072;

// Pi compacts a session only when it is about to overflow: its default reserve is 16k, so a
// session is not compacted until the window is nearly gone, and a long-lived row sends a
// request the gateway truncates to a single character.
//
// The trigger is a share of the window, not a token count, so a deployment that changes the
// model keeps it. At 80% of 500000 it is 400000: the 65536 output cap still fits, and so
// does the summariser's own request. The reserve is floored at the output cap plus a margin,
// because a small window with a large cap would otherwise leave no room to answer in.
export const DEFAULT_COMPACTION = {
  triggerPercent: 80,
  keepPercent: 5,
  minimumReserveTokens: 16_384,
};

// The object Pi reads as settings.json. Throws rather than writing a file whose idle
// timeout would kill an attempt before the gateway could report why it failed.
export function agentSettings({
  idleTimeoutMs = DEFAULT_RETRY.idleTimeoutMs,
  maxRetries = DEFAULT_RETRY.maxRetries,
  baseDelayMs = DEFAULT_RETRY.baseDelayMs,
  maxAgentDelayMs = DEFAULT_RETRY.maxAgentDelayMs,
  gatewayStreamTimeoutMs = DEFAULT_GATEWAY_STREAM_TIMEOUT_MS,
  contextWindow = DEFAULT_CONTEXT_WINDOW,
  maxTokens = DEFAULT_MODEL_MAX_TOKENS,
  compactionTriggerPercent = DEFAULT_COMPACTION.triggerPercent,
  compactionKeepPercent = DEFAULT_COMPACTION.keepPercent,
} = {}) {
  if (!(idleTimeoutMs > gatewayStreamTimeoutMs)) {
    throw new Error(
      `the writer's idle timeout (${idleTimeoutMs}ms) must exceed the gateway's streaming timeout (${gatewayStreamTimeoutMs}ms)`
    );
  }
  if (!(compactionTriggerPercent > 0) || compactionTriggerPercent >= 100) {
    throw new Error(`the compaction trigger (${compactionTriggerPercent}%) must be between 0 and 100`);
  }
  if (!(compactionKeepPercent >= 0) || compactionKeepPercent >= compactionTriggerPercent) {
    throw new Error(
      `the kept-recent share (${compactionKeepPercent}%) must be smaller than the trigger (${compactionTriggerPercent}%)`
    );
  }
  const reserveTokens = Math.max(
    DEFAULT_COMPACTION.minimumReserveTokens,
    Math.ceil((contextWindow * (100 - compactionTriggerPercent)) / 100),
    // The answer needs room too: the reserve is what the request must leave free.
    Number(maxTokens) + DEFAULT_COMPACTION.minimumReserveTokens
  );
  return {
    httpIdleTimeoutMs: idleTimeoutMs,
    // Stated rather than left to the vendor's default: a silent change to it would
    // turn the retry window off, which is the whole of this configuration.
    retry: { enabled: true, maxRetries, baseDelayMs, maxAgentDelayMs },
    // Pi's own compaction, forced on and tuned: the summary is what the next process
    // resumes from, so a long-lived row cannot keep re-sending its whole history.
    // Pi takes these in tokens, so the shares are resolved here.
    compaction: {
      enabled: true,
      reserveTokens,
      keepRecentTokens: Math.floor((contextWindow * compactionKeepPercent) / 100),
    },
  };
}

// The catalog's GitHub server exposes 45 tools including writes; a read-only lane
// declares only these. The server stays hidden, so the rest cannot be reached by name.
export const GITHUB_READ_TOOLS = [
  "search_code",
  "search_repositories",
  "get_file_contents",
  "list_branches",
  "list_commits",
  "list_tags",
];
export const FIRECRAWL_READ_TOOLS = ["firecrawl_search", "firecrawl_scrape", "firecrawl_map"];

// The mcp.json Pi reads from `<agent-dir>/mcp.json`. The URLs come from the deployment,
// never the image: a release name is a cluster fact, and the core admission policy injects
// the two variables into this pod. A variable that is unset omits that server, and the
// instruction names the catalog only when it is there. `direct` is deliberate: codemode is
// the default exposure and would put a third calling convention between the model and a
// handful of read tools the instruction names by name.
export function mcpConfig({ githubUrl = "", firecrawlUrl = "" } = {}) {
  const direct = (tools) => Object.fromEntries(tools.map((tool) => [tool, "direct"]));
  const servers = {};
  if (githubUrl) {
    servers.github = {
      url: githubUrl,
      exposure: "hidden",
      toolExposure: direct(GITHUB_READ_TOOLS),
      description: "Search GitHub repositories for code, examples and documentation",
    };
  }
  if (firecrawlUrl) {
    servers.firecrawl = {
      url: firecrawlUrl,
      exposure: "hidden",
      toolExposure: direct(FIRECRAWL_READ_TOOLS),
      description: "Search and read documentation pages on the web",
    };
  }
  return { mcpServers: servers };
}

// The hosts the fleet writes about. The image default is what a session runs with
// when the caller names none; the caller's list wins because it is a property of the
// row's subject, not of the code.
export const DEFAULT_ARTICLE_SOURCE_HOSTS = [
  "github.com",
  "raw.githubusercontent.com",
  "datahub-local.alvsanand.com",
];

export function parseSourceHosts(value, fallback = DEFAULT_ARTICLE_SOURCE_HOSTS) {
  const list = Array.isArray(value) ? value : String(value ?? "").split(/[,\s]+/);
  const hosts = list
    .map((host) => String(host).trim().toLowerCase())
    .filter(Boolean)
    .map((host) => host.replace(/^https?:\/\//, "").replace(/\/.*$/, ""));
  return hosts.length ? [...new Set(hosts)] : [...fallback];
}

// The allowlist as the agent reads it, substituted into the instruction. The proxy,
// not this line, is what enforces it.
export function fillSourceHosts(text, hosts = DEFAULT_ARTICLE_SOURCE_HOSTS) {
  return String(text ?? "").replaceAll("{{ ARTICLE_SOURCE_HOSTS }}", hosts.join(", "));
}

// The drafting brief is rendered here, from the adapter's own prompt files, so the caller
// sends the entry's fields and never the prompt. An unknown placeholder is left visible:
// it is a prompt bug the turn should report, not a value to invent.
export function fillTemplate(text, vars = {}) {
  return String(text ?? "").replace(/{{\s*([A-Za-z0-9_]+)\s*}}/g, (match, name) =>
    Object.prototype.hasOwnProperty.call(vars, name) ? String(vars[name] ?? "") : match
  );
}

// A fenced block's identity is its text with every whitespace run collapsed: the
// docs render the same YAML with other indentation and other blank lines, and a
// line-level match would accept `apiVersion: v1` as evidence for a whole manifest.
export function normaliseBlock(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim();
}

export function sha256Hex(value) {
  return createHash("sha256").update(String(value ?? ""), "utf8").digest("hex");
}

// Every fenced block in a Markdown body, with its info string. An unterminated fence
// is not a block: it is prose that was cut off, and the article gate rejects it as
// such rather than treating half a manifest as quoted.
export function extractFencedBlocks(markdown) {
  const blocks = [];
  const re = /^[ \t]*```([^\n`]*)\n([\s\S]*?)^[ \t]*```[ \t]*$/gm;
  let match;
  while ((match = re.exec(String(markdown ?? ""))) !== null) {
    const block = match[2].replace(/\n$/, "");
    if (block.trim()) blocks.push({ lang: match[1].trim(), block });
  }
  return blocks;
}

// The ledger's shape, in one place. A session may write either `{sources: [...]}` or
// a bare array; the server always rewrites it as the object, which is what n8n and
// the sheet column read. Unknown fields are kept so a server rewrite does not drop a
// field a later reader added.
export function normaliseLedgerEntry(entry) {
  const e = entry && typeof entry === "object" ? entry : {};
  const validated = String(e.validated ?? "none").trim().toLowerCase();
  return {
    ...e,
    block: String(e.block ?? ""),
    url: String(e.url ?? "").trim(),
    validated: validated === "dry-run" ? "dry-run" : "none",
    validation_error: String(e.validation_error ?? ""),
  };
}

export function parseLedger(text) {
  let data;
  try {
    data = typeof text === "string" ? JSON.parse(text) : text;
  } catch (err) {
    throw new Error(`sources.json is not valid JSON: ${err?.message ?? err}`);
  }
  const list = Array.isArray(data) ? data : data && Array.isArray(data.sources) ? data.sources : null;
  if (!list) throw new Error("sources.json carries no sources array");
  return list.map(normaliseLedgerEntry).filter((entry) => entry.block.trim() !== "");
}

export function serialiseLedger(sources) {
  return `${JSON.stringify({ sources: sources.map(normaliseLedgerEntry) }, null, 2)}\n`;
}

// The proxy applies the same host policy the source allowlist states: it reads a CONNECT
// target, so the host checks are its whole decision. Kept here because the ledger no longer
// fetches anything, and the proxy still has to answer.
const PRIVATE_V4 = [
  [/^0\./, 8],
  [/^10\./, 8],
  [/^100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\./, 10],
  [/^127\./, 8],
  [/^169\.254\./, 16],
  [/^172\.(1[6-9]|2[0-9]|3[01])\./, 12],
  [/^192\.168\./, 16],
];

function isPrivateIPv4(host) {
  const parts = host.split(".");
  if (parts.length !== 4 || parts.some((p) => !/^\d{1,3}$/.test(p) || Number(p) > 255)) return false;
  return PRIVATE_V4.some(([re]) => re.test(host));
}

function isPrivateIPv6(host) {
  const h = host.toLowerCase();
  if (h.includes(".")) {
    // An IPv4-mapped or IPv4-embedded form: the trailing dotted quad is the address.
    const tail = h.slice(h.lastIndexOf(":") + 1);
    if (isPrivateIPv4(tail)) return true;
  }
  if (h === "::1" || h === "::") return true;
  if (/^fe[89ab]/.test(h)) return true; // link-local fe80::/10
  if (/^f[cd]/.test(h)) return true; // unique local fc00::/7
  return false;
}

export function isBlockedHostname(value) {
  const host = String(value ?? "").trim().toLowerCase().replace(/^\[|\]$/g, "").replace(/\.$/, "");
  if (!host) return true;
  if (host === "localhost" || host.endsWith(".localhost")) return true;
  return isPrivateIPv4(host) || isPrivateIPv6(host);
}

// Only the loopback exemption from the address policy, for the one caller that must reach
// a stub on its own machine. It does not extend to link-local or private ranges: an
// allowed loopback is not a reason to let a redirect reach 169.254.169.254.
export function isLoopbackHostname(value) {
  const host = String(value ?? "").trim().toLowerCase().replace(/^\[|\]$/g, "");
  if (host === "localhost" || host.endsWith(".localhost")) return true;
  if (host === "::1") return true;
  return /^127\./.test(host);
}

export function hostAllowed(host, allowedHosts = []) {
  const name = String(host ?? "").trim().toLowerCase();
  return allowedHosts.some((allowed) => {
    const a = String(allowed).trim().toLowerCase();
    return a !== "" && (name === a || name.endsWith(`.${a}`));
  });
}

// The page's text for a block, found as a contiguous run of the block's tokens
// with any whitespace between them. Returns null when the page does not carry it.
export function findExcerpt(body, block) {
  const tokens = normaliseBlock(block).split(" ").filter(Boolean);
  if (!tokens.length) return null;
  const escape = (token) => token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(tokens.map(escape).join("\\s+"));
  const match = re.exec(String(body ?? ""));
  return match ? match[0] : null;
}

// One entry per fenced block, from the pages this turn actually scraped. The transcript is
// the evidence the server already holds: the pod brokered the request and received the text,
// so a block that appears in it was read, and one that does not was not.
//
// What the model saw is what counts, truncation prefix included: a fence that only exists
// further down the page was never read and must not verify.
export function transcriptPages(rows) {
  const calls = new Map();
  const spill = new Map();
  const pages = [];
  for (const row of Array.isArray(rows) ? rows : []) {
    const message = row && row.type === "message" ? row.message : null;
    if (!message || !Array.isArray(message.content)) continue;
    if (message.role === "assistant") {
      for (const part of message.content) {
        if (part && part.type === "toolCall" && part.id) {
          calls.set(part.id, { name: part.name, args: part.arguments || {} });
        }
      }
      continue;
    }
    if (message.role !== "toolResult") continue;
    const call = calls.get(message.toolCallId);
    const toolName = String(message.toolName || call?.name || "");
    const text = message.content
      .filter((part) => part && part.type === "text" && typeof part.text === "string")
      .map((part) => part.text)
      .join("\n");
    if (!text.trim()) continue;
    // A scrape is a page. A long one arrives with its middle removed and its full text spilled
    // to a file, so a later `read` of that file is the same page, not a different source.
    if (/firecrawl_scrape$/.test(toolName)) {
      const url = String(call?.args?.url || "").trim();
      if (!url) continue;
      const spilled = String(message.details?.fullOutputPath || "").trim();
      if (spilled) spill.set(spilled, url);
      pages.push({ url, text: unwrapScrapeText(text) });
      continue;
    }
    if (toolName === "read" || /(^|__)read$/.test(toolName)) {
      const url = spill.get(String(call?.args?.path || "").trim());
      if (url) pages.push({ url, text });
    }
  }
  return pages;
}

// Firecrawl answers markdown directly or wraps it in `{"markdown": ...}` depending on the
// server version; both reach the transcript, and the wrapper is not part of the page.
function unwrapScrapeText(text) {
  const raw = String(text ?? "");
  const braced = raw.indexOf("{");
  const start = raw.startsWith("{") ? 0 : braced > -1 && /^[^{]*\{\s*"markdown"/.test(raw) ? braced : -1;
  if (start < 0) return raw;
  try {
    const body = JSON.parse(raw.slice(start));
    if (typeof body?.markdown === "string") return body.markdown;
    if (typeof body?.data?.markdown === "string") return body.data.markdown;
  } catch {
    // not a wrapper: the page's own text, which may contain braces
  }
  return raw;
}

export function deriveLedger({ article, pages } = {}) {
  const scraped = (Array.isArray(pages) ? pages : []).filter((page) => page && page.url && page.text);
  const sources = [];
  const unquoted = [];
  for (const fenced of extractFencedBlocks(String(article ?? ""))) {
    const key = normaliseBlock(fenced.block);
    if (!key) continue;
    const page = scraped.find((candidate) => findExcerpt(candidate.text, fenced.block) !== null);
    if (!page) {
      unquoted.push(fenced.block.split("\n")[0].trim().slice(0, 120));
      continue;
    }
    const excerpt = findExcerpt(page.text, fenced.block);
    sources.push({
      block: fenced.block,
      url: page.url,
      validated: "none",
      validation_error: "",
      found: true,
      sha256: sha256Hex(key),
      excerpt,
      status: 200,
      body_sha256: sha256Hex(page.text),
    });
  }
  return { sources, unquoted };
}

export function splitArticle(markdown) {
  const raw = String(markdown || "");
  const block = /<article>([\s\S]*?)<\/article>/.exec(raw);
  const inner = (block ? block[1] : raw).trim();
  const head = /^#\s+(.+?)\s*$/;
  let title = "";
  const body = [];
  for (const line of inner.split("\n")) {
    if (!title && body.length === 0 && head.test(line.trim())) {
      title = line.trim().replace(head, "$1");
      continue;
    }
    body.push(line);
  }
  return { title, text: body.join("\n").trim() };
}

// A marker is an instruction to the publishing step, not prose the reader counts.
export function articleWordCount(text) {
  return String(text || "")
    .replace(/<!--[\s\S]*?-->/g, " ")
    .split(/\s+/)
    .filter(Boolean).length;
}

// A model cannot count words, so a draft a little over the budget is the budget met.
// Integer arithmetic, because 1200 * 1.1 is 1320.0000000000002 in a double. The graph's
// `parse_article` and `check_improved_draft` hold the same rule in code; a margin change
// edits all three.
export function articleWordLimit(maxWords) {
  const max = Number(maxWords);
  if (!Number.isFinite(max) || max <= 0) return 0;
  return Math.ceil((max * 11) / 10);
}

// The mechanical half of a turn: where to write and whether the turn authors or
// corrects. The correction names the files already in the directory so a retry edits
// them instead of paying for a fresh read of every source.
export function articleTurnInstruction({ isIteration } = {}) {
  if (isIteration) {
    return (
      "`article.md` in this directory is the article from an earlier turn in this session. " +
      "Apply the request above to it in place - change what it names and keep the rest, " +
      "re-reading only what it names - and write it again. The server writes `sources.json`."
    );
  }
  return (
    "Write the article to `article.md` in this directory. The server writes `sources.json` " +
    "from the pages you scrape, so every fenced block has to appear verbatim on one of them. " +
    "Nothing is published from this turn; the caller fetches both files."
  );
}

// Whether a file exists, used to decide that a session already holds an article.
export async function exists(path) {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
}
