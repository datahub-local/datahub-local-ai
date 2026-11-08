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

// The object Pi reads as settings.json. Throws rather than writing a file whose idle
// timeout would kill an attempt before the gateway could report why it failed.
export function agentSettings({
  idleTimeoutMs = DEFAULT_RETRY.idleTimeoutMs,
  maxRetries = DEFAULT_RETRY.maxRetries,
  baseDelayMs = DEFAULT_RETRY.baseDelayMs,
  maxAgentDelayMs = DEFAULT_RETRY.maxAgentDelayMs,
  gatewayStreamTimeoutMs = DEFAULT_GATEWAY_STREAM_TIMEOUT_MS,
} = {}) {
  if (!(idleTimeoutMs > gatewayStreamTimeoutMs)) {
    throw new Error(
      `the writer's idle timeout (${idleTimeoutMs}ms) must exceed the gateway's streaming timeout (${gatewayStreamTimeoutMs}ms)`
    );
  }
  return {
    httpIdleTimeoutMs: idleTimeoutMs,
    // Stated rather than left to the vendor's default: a silent change to it would
    // turn the retry window off, which is the whole of this configuration.
    retry: { enabled: true, maxRetries, baseDelayMs, maxAgentDelayMs },
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

// ---------------------------------------------------------------------------
// What the server will fetch. The allowlist is the first gate and the address checks are
// the second. They read the URL's own host and never a DNS answer: a literal private
// address or a local name is refused here, while an allowlisted name that resolves
// privately is the residual SSRF shape the design records as a risk. Every redirect
// target is refused by the same check, so a public URL cannot hop to a literal one.

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

// Why this URL may not be fetched, or null when it may. Every reason is a phrase a
// log line and a test can name.
export function sourceUrlRefusal(value, { allowedHosts = [], requireHttps = true, allowLoopback = false } = {}) {
  let url;
  try {
    url = new URL(String(value ?? ""));
  } catch {
    return "not a URL";
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") return `scheme ${url.protocol} is not http or https`;
  if (requireHttps && url.protocol !== "https:") return "not https";
  if (url.username || url.password) return "carries credentials";
  const host = url.hostname.toLowerCase().replace(/^\[|\]$/g, "");
  const blocked = allowLoopback && isLoopbackHostname(host) ? false : isBlockedHostname(host);
  if (blocked) return `host ${host} is private or loopback`;
  if (!hostAllowed(host, allowedHosts)) return `host ${host} is not a declared source host`;
  return null;
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

export const DEFAULT_LEDGER_FETCH = {
  maxBytes: 2_000_000,
  maxRedirects: 3,
  timeoutMs: 15_000,
};

async function readCapped(res, maxBytes) {
  if (!res.body || typeof res.body.getReader !== "function") {
    const buf = Buffer.from(await res.arrayBuffer());
    return buf.subarray(0, maxBytes);
  }
  const reader = res.body.getReader();
  const chunks = [];
  let size = 0;
  while (size < maxBytes) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = Buffer.from(value);
    const room = maxBytes - size;
    chunks.push(chunk.subarray(0, room));
    size += Math.min(chunk.length, room);
    if (chunk.length > room) {
      try {
        await reader.cancel();
      } catch {
        // the body is already capped; cancelling best effort
      }
      break;
    }
  }
  return Buffer.concat(chunks);
}

// Fetch one URL with the policy's gates applied at the start and at every redirect.
// Returns `{body}` or `{refusal}`; a status is reported, never thrown, so the caller
// can name it in the drop reason.
async function fetchLedgerUrl(url, opts) {
  const {
    fetchUrl = fetch,
    allowedHosts = [],
    requireHttps = true,
    allowLoopback = false,
    maxBytes = DEFAULT_LEDGER_FETCH.maxBytes,
    maxRedirects = DEFAULT_LEDGER_FETCH.maxRedirects,
    timeoutMs = DEFAULT_LEDGER_FETCH.timeoutMs,
  } = opts;
  let current = String(url);
  for (let hop = 0; hop <= maxRedirects; hop += 1) {
    const refusal = sourceUrlRefusal(current, { allowedHosts, requireHttps, allowLoopback });
    if (refusal) return { refusal };
    const controller = new AbortController();
    // The budget covers the body, not only the headers: a page that sends a response
    // line and then dribbles would otherwise hold the serialized turn open until the
    // caller's own timeout.
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    let res;
    try {
      res = await fetchUrl(current, { signal: controller.signal, redirect: "manual" });
    } catch (err) {
      clearTimeout(timer);
      return { refusal: `did not answer: ${err?.message ?? err}` };
    }
    if (res.status >= 300 && res.status < 400) {
      clearTimeout(timer);
      const location = res.headers.get("location");
      if (!location) return { refusal: `redirect ${res.status} without a location` };
      current = new URL(location, current).toString();
      continue;
    }
    if (!res.ok) {
      clearTimeout(timer);
      return { refusal: `answered HTTP ${res.status}` };
    }
    try {
      const body = await readCapped(res, maxBytes);
      return { status: res.status, body: body.toString("utf8"), bodyBytes: body.length };
    } catch (err) {
      return { refusal: `did not answer: ${err?.message ?? err}` };
    } finally {
      clearTimeout(timer);
    }
  }
  return { refusal: `more than ${maxRedirects} redirects` };
}

// The MCP payload of a tool call, from a JSON body or an SSE stream. An SSE answer is
// what a streamable-http MCP server sends when it answers a POST, and a JSON body is
// what it sends when it does not: both reach here, and neither may be assumed.
export function mcpToolPayload(text, pageUrl = "") {
  const raw = String(text ?? "").trim();
  const candidates = [raw];
  if (raw.includes("data:")) {
    for (const event of raw.split(/\r?\n\r?\n/)) {
      const data = event
        .split(/\r?\n/)
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trim())
        .join("");
      if (data) candidates.push(data);
    }
  }
  for (const candidate of candidates) {
    try {
      const parsed = JSON.parse(candidate);
      if (parsed && (parsed.result || parsed.error)) return parsed;
    } catch {
      // not this one; the next candidate is a whole SSE frame's data
    }
  }
  throw new Error(`the scrape answer for ${pageUrl || "the page"} is not an MCP payload`);
}

// A scrape's text, whether the server returned markdown or the JSON body Firecrawl
// wraps it in. The markdown is what `findExcerpt` reads, so the wrapper has to go.
export function scrapeText(payload, pageUrl = "") {
  if (payload?.error) {
    const message = payload.error.message ?? JSON.stringify(payload.error);
    throw new Error(`the scrape failed for ${pageUrl || "the page"}: ${message}`);
  }
  const content = payload?.result?.content;
  const item = Array.isArray(content) ? content.find((entry) => typeof entry?.text === "string") : null;
  if (!item) throw new Error(`the scrape returned no text for ${pageUrl || "the page"}`);
  const text = item.text.trim();
  if (!text.startsWith("{") && !text.startsWith("[")) return text;
  try {
    const body = JSON.parse(text);
    if (typeof body?.markdown === "string") return body.markdown;
    if (typeof body?.data?.markdown === "string") return body.data.markdown;
  } catch {
    // a JSON-looking page body, not a wrapper: keep it as the page's own text
  }
  return text;
}

// A `reader` for `revalidateLedger` that scrapes through the Firecrawl MCP server.
// The pod's egress policy admits the model and the MCP servers and nothing else, so a
// direct fetch of the cited host would answer nothing; this is the one path out.
export function scrapeReader({ endpoint, fetchUrl = fetch, timeoutMs = 45_000 } = {}) {
  const url = String(endpoint ?? "").trim();
  if (!url) return null;
  let id = 0;
  return async function read(pageUrl) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetchUrl(url, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          accept: "application/json, text/event-stream",
        },
        body: JSON.stringify({
          jsonrpc: "2.0",
          id: (id += 1),
          method: "tools/call",
          params: {
            name: "firecrawl_scrape",
            arguments: { url: pageUrl, formats: ["markdown"], onlyMainContent: false },
          },
        }),
        signal: controller.signal,
      });
      if (!res.ok) return { refusal: `scrape server answered HTTP ${res.status}` };
      const payload = mcpToolPayload(await res.text(), pageUrl);
      return { status: 200, body: scrapeText(payload, pageUrl) };
    } catch (err) {
      return { refusal: `scrape did not answer: ${err?.message ?? err}` };
    } finally {
      clearTimeout(timer);
    }
  };
}

// Verify a ledger against the pages it cites. An entry whose URL does not answer is
// dropped: the server, not the model, decides whether a source exists. A URL that
// answers but does not carry the block keeps its entry with `found: false`, which the
// n8n gate rejects with the block and the URL in the reason -- the two failures are
// different findings and only one of them is about the URL.
//
// `reader` replaces the direct fetch when the pod has no internet egress: the only
// process that leaves it is the Firecrawl MCP server, so a session there verifies
// through that server (see `scrapeReader`). The URL policy runs either way, on the
// citation, before anything is read.
export async function revalidateLedger(entries, opts = {}) {
  const sources = (Array.isArray(entries) ? entries : []).map(normaliseLedgerEntry);
  const fetched = new Map();
  const dropped = [];
  const kept = [];
  for (const entry of sources) {
    if (!entry.url) {
      dropped.push({ block: entry.block, url: entry.url, reason: "no url" });
      continue;
    }
    if (!fetched.has(entry.url)) {
      const refusal = opts.reader
        ? sourceUrlRefusal(entry.url, opts)
        : null;
      fetched.set(
        entry.url,
        refusal ? { refusal } : opts.reader ? await opts.reader(entry.url) : await fetchLedgerUrl(entry.url, opts)
      );
    }
    const page = fetched.get(entry.url);
    if (page.refusal) {
      dropped.push({ block: entry.block, url: entry.url, reason: page.refusal });
      continue;
    }
    const excerpt = findExcerpt(page.body, entry.block);
    kept.push({
      ...entry,
      found: excerpt !== null,
      sha256: excerpt !== null ? sha256Hex(normaliseBlock(entry.block)) : "",
      excerpt: excerpt ?? "",
      status: page.status,
      body_sha256: sha256Hex(page.body),
    });
  }
  return { sources: kept, dropped };
}

// The H1 and the body of an article. A model may wrap its answer in `<article>`, and a
// turn may have written the file directly; both shapes become the same pair. The body is
// everything after the first H1 line, because the row stores the title separately and
// counts the body against the budget.
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
      "`article.md` and `sources.json` in this directory are the article from an earlier " +
      "turn in this session. Apply the request above to the article in place - change what " +
      "it names and keep the rest, re-reading only what it names - and write both files again."
    );
  }
  return (
    "Write the article to `article.md` in this directory and its source ledger to " +
    "`sources.json` here. Nothing is published from this turn; the caller fetches both files."
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
