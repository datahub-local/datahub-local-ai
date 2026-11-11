#!/usr/bin/env node
// The v1alpha2 session endpoint for the Pi writer adapter.
//
// Two lanes share this server. The article lane is the original job: given a brief, fetch the
// pages it cites and draft `article.md` plus the `sources.json` ledger that says where each
// fenced block was read. The post lane is one short post: the source text arrives on the brief,
// the turn has no tools, and `draft` and `review` are the only tasks it serves.
//
// A `HarnessSession` runs this as a long-lived Deployment, so Pi keeps its state across turns
// and the caller's retry continues the same directory instead of paying for every source again.
//
// Derived from the maintained Pi adapter's session-server.mjs, which is the reference
// for this contract. The deltas are the article lane's own:
//
//   * `--no-tools` is dropped, so Pi can fetch pages and validate a manifest.
//   * `--no-skills` stays: no skill is installed in this image, and one found in the
//     run directory or HOME would compete with the instruction file.
//   * the tools reach the network only through the loopback proxy below, because an
//     allowlist in an instruction is not enforcement.
//   * after the turn the server refetches every ledgered URL and rewrites the ledger
//     with what it saw, so the model is never the authority on whether a source exists.
//
// Everything else — the contract check, the credential checks, the provider config,
// the bounded body and output, serialized turns, SSE framing, client disconnect
// cancellation — is upstream's shape, so the platform sees the behaviour it expects.

import http from "node:http";
import net from "node:net";
import { createReadStream } from "node:fs";
import { mkdir, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { join } from "node:path";

import {
  safeSessionId,
  runDir as resolveRunDir,
  resolveArtifact,
  contentTypeFor,
  expiredRunDirs,
  expiredTranscripts,
  exists,
  DEFAULT_SESSION_WORKSPACE,
  DEFAULT_RETRY,
  DEFAULT_COMPACTION,
  DEFAULT_CONTEXT_WINDOW,
  DEFAULT_MODEL_MAX_TOKENS,
  agentSettings,
  mcpConfig,
  parseSourceHosts,
  hostAllowed,
  isBlockedHostname,
  fillSourceHosts,
  fillTemplate,
  parseLedger,
  serialiseLedger,
  deriveLedger,
  transcriptPages,
  extractFencedBlocks,
  normaliseBlock,
  articleTurnInstruction,
  splitArticle,
  articleWordCount,
  articleWordLimit,
  chooseDirectives,
  ARTICLE_NAME,
  LEDGER_NAME,
  POST_DIRECTIVES_NAME,
} from "./session-lib.mjs";

const port = Number(process.env.SYMPOZIUM_SESSION_PORT || "8080");
const maxBody = 1_048_576;
const maxOutput = 2_000_000;
// The session PVC is mounted at /tmp, so Pi's transcript survives a pod restart.
const sessionDir = "/tmp/pi-sessions";
const promptDir = process.env.PI_WRITER_PROMPT_DIR || "/opt/pi-writer/prompts";
const instructionFile = "writing.md";
const proxyPort = Number(process.env.PI_WRITER_PROXY_PORT || "8081");
// A session container mounts the session PVC at /tmp and does **not** mount
// /workspace (only the Job path does), so the workspace must default under the PVC.
// The caller can still override it.
const workDir = process.env.SYMPOZIUM_WORKSPACE || DEFAULT_SESSION_WORKSPACE;
// The window Pi sizes its requests against. LiteLLM serves 500000 input tokens for the
// writer's model; the compaction trigger is a share of it, so only this moves with the model.
const contextWindow = Number(process.env.PI_WRITER_CONTEXT_WINDOW || DEFAULT_CONTEXT_WINDOW);
const maxTokens = Number(process.env.PI_WRITER_MAX_TOKENS || DEFAULT_MODEL_MAX_TOKENS);

// Session state is durable, so it has to expire: an abandoned row would otherwise
// keep its run directory and Pi transcript forever, and the PVC would fill. The
// default matches the article sheet's own retention window so a run's row and its
// files expire together. 0 (or a non-number) disables the sweep.
const retentionDays = Number(process.env.PI_WRITER_SESSION_TTL_DAYS ?? "7");
const sweepIntervalMs = 60 * 60 * 1000;

async function listEntries(dir) {
  try {
    const names = await readdir(dir);
    const entries = await Promise.all(
      names.map(async (name) => {
        try {
          const info = await stat(join(dir, name));
          return { name, mtimeMs: info.mtimeMs };
        } catch {
          return null;
        }
      })
    );
    return entries.filter(Boolean);
  } catch {
    return [];
  }
}

// Best-effort: a failed unlink is logged and the turn carries on. `keep` is the
// session in flight, which must never be swept under its own turn.
let lastSweep = Date.now();
async function sweepSessions(keep) {
  if (!Number.isFinite(retentionDays) || retentionDays <= 0) return;
  const cutoffMs = Date.now() - retentionDays * 24 * 60 * 60 * 1000;
  try {
    for (const name of expiredRunDirs(await listEntries(join(workDir, "runs")), { cutoffMs, keep })) {
      await rm(join(workDir, "runs", name), { recursive: true, force: true });
      console.log(`sympozium pi writer session: swept expired session ${name}`);
    }
    for (const name of expiredTranscripts(await listEntries(sessionDir), { cutoffMs, keep })) {
      await rm(join(sessionDir, name), { force: true });
      console.log(`sympozium pi writer session: swept expired transcript ${name}`);
    }
    lastSweep = Date.now();
  } catch (err) {
    console.error(`sympozium pi writer session: sweep failed: ${err?.message ?? err}`);
  }
}

async function sweepIfDue(keep) {
  if (Date.now() - lastSweep < sweepIntervalMs) return;
  await sweepSessions(keep);
}

function fail(message) {
  console.error(`sympozium pi writer session: ${message}`);
  process.exit(1);
}

for (const name of ["MODEL_NAME", "MODEL_BASE_URL", "OPENAI_API_KEY"]) {
  if (!process.env[name]) fail(`${name} is required`);
}
if (process.env.SYMPOZIUM_HARNESS_CONTRACT_VERSION !== "v1alpha2") {
  fail("unsupported harness contract");
}

await mkdir(`${process.env.HOME}/.pi/agent`, { recursive: true });
await mkdir(sessionDir, { recursive: true });
await mkdir(workDir, { recursive: true });

// Reclaim anything already past the window before serving the first turn.
await sweepSessions(undefined);

await writeFile(
  `${process.env.HOME}/.pi/agent/models.json`,
  JSON.stringify({
    providers: {
      sympozium: {
        baseUrl: process.env.MODEL_BASE_URL,
        api: "openai-completions",
        apiKey: "$OPENAI_API_KEY",
        compat: { supportsDeveloperRole: false, supportsReasoningEffort: true },
        models: [
          {
            id: process.env.MODEL_NAME,
            reasoning: true,
            input: ["text"],
            contextWindow: contextWindow,
            // The gateway's reasoning is billed as output and, left on, this model
            // spends every token it is given thinking and returns no content at all.
            // Pi only sends `reasoning_effort` for a non-off thinking level, so the
            // session runs at `minimal`, which this map turns into the `none` the
            // gateway honours. Both numbers are overridable so they can move without
            // a rebuild.
            // `minimal` is the default for a reason: at `none` this model writes prose instead of
            // reasoning until the cap. The other levels are mapped so PI_WRITER_THINKING can move
            // it deliberately rather than Pi sending no effort at all.
            thinkingLevelMap: { minimal: "none", low: "low", medium: "medium", high: "high" },
            maxTokens,
          },
        ],
      },
    },
  })
);

// The catalog servers that answer "what does this project do, and how is it written?":
// GitHub for the repository and its examples, Firecrawl for the documentation site.
// Pi reads this file beside models.json. The addresses are the deployment's, injected as
// env; the image carries no cluster names, and an unset variable leaves that server out.
await writeFile(
  `${process.env.HOME}/.pi/agent/mcp.json`,
  JSON.stringify(
    mcpConfig({
      githubUrl: process.env.SYMPOZIUM_GITHUB_MCP_URL ?? "",
      firecrawlUrl: process.env.SYMPOZIUM_FIRECRAWL_MCP_URL ?? "",
    })
  )
);

// The ledger is derived from the transcript, so the one thing worth printing at boot is
// whether the reads it depends on are configured at all: with no Firecrawl endpoint the
// turn cannot scrape and every fence comes back unquoted.
console.log(
  `sympozium pi writer session: ledger derived from scrapes ${
    process.env.SYMPOZIUM_FIRECRAWL_MCP_URL ? "through the Firecrawl MCP server" : "(no Firecrawl endpoint set: no block can be quoted)"
  }`
);

// Pi's retry, idle-timeout and compaction settings, which Pi reads from the same agent
// directory. Without this file the writer runs on the vendor's defaults, where a stream that
// stalls for longer than the gateway's per-read timeout ends the attempt with no window left
// to retry in, and a session is not compacted until the context window is nearly gone.
const compactionPercent = Number(
  process.env.PI_WRITER_COMPACT_AT_PERCENT || DEFAULT_COMPACTION.triggerPercent
);
const settings = agentSettings({
  idleTimeoutMs: Number(process.env.PI_WRITER_HTTP_IDLE_MS || DEFAULT_RETRY.idleTimeoutMs),
  maxRetries: Number(process.env.PI_WRITER_RETRY_MAX || DEFAULT_RETRY.maxRetries),
  baseDelayMs: Number(process.env.PI_WRITER_RETRY_BASE_MS || DEFAULT_RETRY.baseDelayMs),
  maxAgentDelayMs: Number(process.env.PI_WRITER_RETRY_MAX_DELAY_MS || DEFAULT_RETRY.maxAgentDelayMs),
  contextWindow,
  maxTokens,
  compactionTriggerPercent: compactionPercent,
  compactionKeepPercent: Number(
    process.env.PI_WRITER_COMPACT_KEEP_PERCENT || DEFAULT_COMPACTION.keepPercent
  ),
});
await writeFile(`${process.env.HOME}/.pi/agent/settings.json`, JSON.stringify(settings));

// A session that outgrows the window answers one character and looks successful from the
// outside, so the trigger is printed with the window it has to fit inside. Both numbers come
// from the settings Pi was actually given, not from the environment a second time.
console.log(
  `sympozium pi writer session: compacting at ${contextWindow - settings.compaction.reserveTokens} tokens (${compactionPercent}%) of a ${contextWindow} window, keeping ${settings.compaction.keepRecentTokens} recent`
);

async function writingMethod() {
  const path = join(promptDir, instructionFile);
  try {
    return await readFile(path, "utf8");
  } catch {
    // A missing prompt is loud on the first turn rather than fatal at startup:
    // the session still comes up and the error names the path.
    return `The writing instruction file is missing at ${path}. Report that rather than improvising.`;
  }
}

// The drafting prompt is the adapter's, not the caller's: the request carries the entry's
// fields and these files decide how they read. A missing file fails the turn by name
// rather than drafting from half an instruction.
async function readPrompt(name) {
  const path = join(promptDir, name);
  try {
    return await readFile(path, "utf8");
  } catch {
    throw new Error(`the prompt ${name} is missing at ${path}`);
  }
}

async function articlePrompt(brief) {
  const [system, task, structures, audiences] = await Promise.all([
    readPrompt("article_writer_system.md"),
    readPrompt("article_task.md"),
    readPrompt("article_structures.md"),
    readPrompt("article_audiences.md"),
  ]);
  const entry = brief && typeof brief === "object" ? brief : {};
  const text = fillTemplate(task, {
    TOPIC: entry.topic ?? "",
    DESCRIPTION: entry.description ?? "",
    URL: entry.url ?? "",
    MAX_WORDS: entry.max_words ?? "",
    MAX_FIGURES: entry.max_figures ?? "",
    ASSET_TYPES: entry.asset_types ?? "",
    AUDIENCE: entry.audience ?? "NONE",
    AUDIENCES: audiences,
    EXTRA_PROMPT: entry.extra_prompt ?? "",
    CONTENT: entry.content ?? "",
    FEEDBACK: entry.feedback ?? "",
    PREVIOUS_DRAFT: entry.previous_draft ?? "",
    STRUCTURES: structures,
  });
  return `${system}\n\n---\n\n${text}`;
}

// The writer owns every model turn in the article lane. A request names the turn it
// wants and the entry's fields; the prompts and the rules that render them stay here.
const TASKS = new Set(["draft", "review", "audit", "aspects", "improve"]);

function taskOf(request) {
  const task = String(request.task || "draft");
  if (!TASKS.has(task)) throw new Error(`unknown task ${task}`);
  return task;
}

// An absent lane is the article lane, so every caller that predates the post lane keeps its
// behaviour. The post lane has only the two turns it needs: it drafts and it gates.
const LANES = new Set(["article", "post"]);

function laneOf(request) {
  const lane = String(request.lane || "article");
  if (!LANES.has(lane)) throw new Error(`unknown lane ${lane}`);
  return lane;
}

function emptyArticle() {
  return { title: "", text: "" };
}

// The draft of record travels with a review, an aspect pass or an improve turn. n8n
// resolves it (the converged draft, the creator's answer, or the stored row), so the
// turn reviews exactly what the caller decided, not whatever the session still holds
// from an earlier round.
function articleFrom(request) {
  const value = request.article && typeof request.article === "object" ? request.article : {};
  return {
    title: String(value.title ?? "").trim(),
    text: String(value.text ?? value.body ?? "").trim(),
  };
}

async function readArticle(dir) {
  let raw;
  try {
    raw = await readFile(join(dir, ARTICLE_NAME), "utf8");
  } catch {
    return emptyArticle();
  }
  return splitArticle(raw);
}

async function writeArticle(dir, article) {
  const text = String(article.text || "").trim();
  if (!text) throw new Error("an article turn needs article.text");
  const title = String(article.title || "").trim();
  await writeFile(join(dir, ARTICLE_NAME), `${title ? `# ${title}\n\n` : ""}${text}\n`);
  return { title, text };
}

async function resolveArticle(request, dir) {
  const article = articleFrom(request);
  if (article.text) return writeArticle(dir, article);
  const stored = await readArticle(dir);
  if (stored.text) return stored;
  throw new Error("the request carries no article and the session has none to review");
}

async function readStructures() {
  return readPrompt("article_structures.md");
}

async function readAudiences() {
  return readPrompt("article_audiences.md");
}

async function reviewPrompt({ brief, article }) {
  // The gate enforces a budget. Without one the rendered limit is zero, which rejects
  // every draft, so name the missing field rather than fail a draft on a gate that could
  // not run.
  const maxWords = Number(brief.max_words);
  if (!Number.isFinite(maxWords) || maxWords <= 0) {
    throw new Error("a review needs brief.max_words: the gate enforces the budget");
  }
  const [system, review, audiences] = await Promise.all([
    readPrompt("article_writer_system.md"),
    readPrompt("article_review.md"),
    readAudiences(),
  ]);
  return fillTemplate(review, {
    TITLE: article.title,
    TEXT: article.text,
    WORD_COUNT: articleWordCount(article.text),
    MAX_WORDS: maxWords,
    WORD_LIMIT: articleWordLimit(maxWords),
    AUDIENCE: brief.audience ?? "NONE",
    AUDIENCES: audiences,
    TOPIC: brief.topic ?? "",
    DESCRIPTION: brief.description ?? "",
    URL: brief.url ?? "",
    ASSET_TYPES: brief.asset_types ?? "",
    EXTRA_PROMPT: brief.extra_prompt ?? "",
    FEEDBACK: brief.feedback ?? "",
    RULES: system,
    CONTENT: brief.content ?? "",
  });
}

// The audit is the review that can look: same session and directory as the draft, tools on, and
// the derived ledger already on disk. The verdict shape stays the review's so the caller keeps its
// switch, and the findings ride along in the explanation so the writer's retry carries them.
async function auditPrompt({ brief, article, unquoted = [], pages = [], sessionFile = "" }) {
  const maxWords = Number(brief.max_words);
  if (!Number.isFinite(maxWords) || maxWords <= 0) {
    throw new Error("an audit needs brief.max_words: the gate enforces the budget");
  }
  const [system, audit, audiences] = await Promise.all([
    readPrompt("article_writer_system.md"),
    readPrompt("article_audit.md"),
    readAudiences(),
  ]);
  return fillTemplate(audit, {
    TITLE: article.title,
    TEXT: article.text,
    WORD_COUNT: articleWordCount(article.text),
    MAX_WORDS: maxWords,
    WORD_LIMIT: articleWordLimit(maxWords),
    AUDIENCE: brief.audience ?? "NONE",
    AUDIENCES: audiences,
    TOPIC: brief.topic ?? "",
    DESCRIPTION: brief.description ?? "",
    URL: brief.url ?? "",
    ASSET_TYPES: brief.asset_types ?? "",
    EXTRA_PROMPT: brief.extra_prompt ?? "",
    FEEDBACK: brief.feedback ?? "",
    RULES: system,
    CONTENT: brief.content ?? "",
    SESSION_FILE: sessionFile || "unavailable",
    // The gate's own findings, not the auditor's: a block listed here cannot publish, and the
    // audit's job is to name the concrete fix (the page to quote, or prose) rather than repeat
    // the first line back to the writer.
    UNQUOTED: unquoted.length
      ? unquoted
          .map(
            (entry, index) =>
              `${index + 1}. starts \`${entry.firstLine}\`:\n\n\`\`\`\n${String(entry.block).slice(0, 1600)}\n\`\`\``
          )
          .join("\n\n")
      : "none",
    PAGES: pages.length ? pages.map((url) => `- ${url}`).join("\n") : "none",
  });
}

// The registry is the single list of aspects. A missing, unparsable or empty registry
// fails the turn loudly: without its definitions the pass must not run on nothing.
async function loadAspects() {
  const raw = await readPrompt("article_aspects.json");
  let data;
  try {
    data = JSON.parse(raw);
  } catch (err) {
    throw new Error(`article_aspects.json is not valid JSON: ${err?.message ?? err}`);
  }
  const aspects = (Array.isArray(data.aspects) ? data.aspects : [])
    .map((aspect) => ({
      id: String((aspect && aspect.id) || "").trim(),
      prompt: String((aspect && aspect.prompt) || "").trim(),
      focus: String((aspect && aspect.focus) || "").trim(),
    }))
    .filter((aspect) => aspect.id && aspect.prompt);
  if (!aspects.length) throw new Error("article_aspects.json lists no usable aspect");
  return aspects;
}

async function aspectPrompt(aspect, { brief, article }) {
  const [template, audiences, structures] = await Promise.all([
    readPrompt(aspect.prompt),
    readAudiences(),
    readStructures(),
  ]);
  return fillTemplate(template, {
    TITLE: article.title,
    DRAFT: article.text,
    TOPIC: brief.topic ?? "",
    DESCRIPTION: brief.description ?? "",
    AUDIENCE: brief.audience ?? "NONE",
    AUDIENCES: audiences,
    STRUCTURES: structures,
  });
}

async function improvePrompt({ brief, article, findings, problem, hosts }) {
  const [template, audiences, structures] = await Promise.all([
    readPrompt("article_improver.md"),
    readAudiences(),
    readStructures(),
  ]);
  return fillTemplate(template, {
    TITLE: article.title,
    DRAFT: article.text,
    FINDINGS: String(findings || "none"),
    FEEDBACK: brief.feedback ?? "",
    PROBLEM: String(problem || ""),
    AUDIENCE: brief.audience ?? "NONE",
    AUDIENCES: audiences,
    STRUCTURES: structures,
    MAX_WORDS: brief.max_words ?? "",
    ASSET_TYPES: brief.asset_types ?? "",
    HOSTS: Array.isArray(hosts) && hosts.length ? hosts.join(", ") : "none declared",
  });
}

// ---------------------------------------------------------------------------
// The post lane.
//
// Its two turns share the session and the directory with the article lane, but none of its
// artifacts: the source text arrives on the brief, no page is fetched, and the answer is the
// post itself. The prompts and the variety draw live here, so the rule pair the drafter and
// the gate both read has one copy.

function postWordRange(brief) {
  const value = brief && typeof brief === "object" ? brief : {};
  const min = Number(value.min_words) > 0 ? Number(value.min_words) : 150;
  const max = Number(value.max_words) > 0 ? Number(value.max_words) : 200;
  return { min, max };
}

async function postPrompts(brief) {
  const { min, max } = postWordRange(brief);
  const url = brief && typeof brief === "object" ? String(brief.url ?? "") : "";
  const [system, post, review, rules, aiSpeak] = await Promise.all([
    readPrompt("linkedin_post_system.md"),
    readPrompt("linkedin_post.md"),
    readPrompt("linkedin_post_review.md"),
    readPrompt("linkedin_post_rules.md"),
    readPrompt("ai_speak.md"),
  ]);
  return {
    system,
    post,
    review,
    rules: fillTemplate(rules, { MIN_WORDS: min, MAX_WORDS: max, AI_SPEAK: aiSpeak, URL: url }),
  };
}

async function postDraftPrompt({ brief, directives }) {
  const { system, post, rules } = await postPrompts(brief);
  const text = fillTemplate(post, {
    RULES: rules,
    EXTRA_PROMPT: brief.extra_prompt ?? "",
    CONTENT: brief.content ?? "",
    VARIETY_DIRECTIVES: directives,
    FEEDBACK: brief.feedback ?? "",
    PREVIOUS_POST: brief.previous_post ?? "",
  });
  return `${system}\n\n---\n\n${text}`;
}

async function postReviewPrompt({ brief, text, directives }) {
  const { review, rules } = await postPrompts(brief);
  return fillTemplate(review, {
    RULES: rules,
    EXTRA_PROMPT: brief.extra_prompt ?? "",
    VARIETY_DIRECTIVES: directives,
    FEEDBACK: brief.feedback ?? "",
    URL: brief.url ?? "",
    TEXT: text,
  });
}

async function readPostDirectives(dir) {
  try {
    const stored = JSON.parse(await readFile(join(dir, POST_DIRECTIVES_NAME), "utf8"));
    if (stored && typeof stored.directives === "string" && stored.directives.trim()) return stored;
  } catch {
    // A missing or unreadable file is a fresh draw, not a failed turn.
  }
  return null;
}

// One set per post: drawn before the first draft, kept in the run directory, and read back
// by the gate so it judges the shape the drafter was given. A swept session draws again.
async function resolvePostDirectives(dir, brief) {
  const stored = await readPostDirectives(dir);
  if (stored) return stored;
  const chosen = chooseDirectives({
    variety: await readPrompt("linkedin_variety.md"),
    hook: brief.hook,
    hookOpening: brief.hook_opening,
    minWords: brief.min_words,
    maxWords: brief.max_words,
  });
  await writeFile(join(dir, POST_DIRECTIVES_NAME), `${JSON.stringify(chosen, null, 2)}\n`);
  return chosen;
}

// The draft answers inside one `<output>` block and the gate answers the verdict and its
// explanation. Both are rebuilt here so the caller reads the same tags it read from the model
// node, whatever wrapper the turn used.
function postDraftAnswer(response) {
  const raw = String(response ?? "").trim();
  const block = /<output>([\s\S]*?)<\/output>/.exec(raw);
  const text = (block ? block[1] : raw).trim();
  if (!text) throw new Error("the post turn returned no text");
  return `<output>${text}</output>`;
}

function postReviewAnswer(response) {
  const verdict = parseReview(response);
  return `<output>${verdict.pass}</output><explanation>${verdict.explanation}</explanation>`;
}

function parseReview(text) {
  const answer = String(text || "");
  const read = (tag) => {
    if (!answer.includes(`<${tag}>`) || !answer.includes(`</${tag}>`)) return "";
    return answer.split(`<${tag}>`)[1].split(`</${tag}>`)[0].trim();
  };
  const output = read("output").toLowerCase();
  const explanation = read("explanation").replace(/\s+/g, " ").trim();
  return { pass: output === "true", explanation };
}

function parseFindings(text) {
  const answer = String(text || "");
  const found = /<findings>([\s\S]*?)<\/findings>/.exec(answer);
  const body = (found ? found[1] : "").trim();
  if (!body || /^none\b/i.test(body)) return { text: "", count: 0 };
  const count = body.split("\n").filter((line) => /^\s*\d+[.)]/.test(line)).length || 1;
  return { text: body, count };
}

// A ledger summary for the improve prompt's source block: the first line of each block
// and the page it came from, never the whole page.
function ledgerSummary(entries) {
  const firstLine = (value) =>
    String(value || "").split("\n").map((line) => line.trim()).filter(Boolean)[0] || "a fenced block";
  return (
    entries
      .filter((entry) => entry && String(entry.block || "").trim())
      .map((entry) => `- ${firstLine(entry.block)} (${String(entry.url || "").trim() || "no url"})`)
      .join("\n") || "none"
  );
}

async function ledgerCounts(dir) {
  try {
    const entries = parseLedger(await readFile(join(dir, LEDGER_NAME), "utf8"));
    const article = await readFile(join(dir, ARTICLE_NAME), "utf8");
    const named = new Set(entries.map((entry) => normaliseBlock(entry.block)));
    const unquoted = extractFencedBlocks(article)
      .filter((fenced) => !named.has(normaliseBlock(fenced.block)))
      .map((fenced) => fenced.block.split("\n")[0].trim().slice(0, 120));
    return {
      sources: entries.length,
      quoted: entries.filter((entry) => entry.found === true).length,
      unquoted,
      dropped: [],
      error: "",
    };
  } catch {
    return { sources: 0, quoted: 0, unquoted: [], dropped: [], error: "the session has no readable sources.json" };
  }
}

async function articleAnswer(dir, ledger) {
  const [article, counts] = await Promise.all([readArticle(dir), ledgerCounts(dir)]);
  return {
    name: ARTICLE_NAME,
    ledger: LEDGER_NAME,
    title: article.title,
    text: article.text,
    word_count: articleWordCount(article.text),
    ...(ledger || counts),
  };
}

function readJSON(req) {
  return new Promise((resolve, reject) => {
    let size = 0;
    let body = "";
    req.setEncoding("utf8");
    req.on("data", (chunk) => {
      size += Buffer.byteLength(chunk);
      if (size > maxBody) {
        reject(new Error("request body exceeds 1 MiB"));
        req.destroy();
        return;
      }
      body += chunk;
    });
    req.on("end", () => {
      try {
        resolve(JSON.parse(body));
      } catch {
        reject(new Error("request must be valid JSON"));
      }
    });
    req.on("error", reject);
  });
}

function promptFrom(messages) {
  if (!Array.isArray(messages)) throw new Error("messages is required");
  const users = messages.filter((m) => m && m.role === "user" && typeof m.content === "string");
  if (!users.length) throw new Error("messages must contain a user message");
  return users.at(-1).content;
}

// The failure the caller reads. Pi reports a stalled call in one word from its own
// stream plumbing, so the endpoint is named here: without it an exhausted retry
// window and a bad brief are the same string in the run record.
function piFailure(code, stderr) {
  const detail = stderr
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .at(-1);
  const endpoint = process.env.MODEL_BASE_URL ?? "the model endpoint";
  return new Error(`Pi exited ${code} calling ${endpoint}${detail ? `: ${detail.slice(-800)}` : ""}`);
}

// Pi emits its response on stdout; forwarding each chunk keeps `stream: true`
// genuine rather than a UI replaying a finished answer.
function runPi(prompt, sessionID, onOutput, signal, cwd = workDir, options = {}) {
  return new Promise((resolve, reject) => {
    const args = [
      "--print",
      "--no-prompt-templates",
      // Tools stay enabled: fetching the cited pages with the proxy's allowlist and
      // rendering a manifest are the job. Discovery is off: no skills or extensions
      // are installed anywhere this pod can see.
      "--no-skills",
      // Discovery stays off, but MCP is a built-in extension and `--no-extensions` would
      // take it with the rest: only the catalog client is loaded back.
      "--no-extensions",
      "-e",
      "builtin:mcp",
      // A review or an edit gets the draft in its prompt and answers in its response. No
      // tools means it cannot fetch a page again, which is the point: those turns may not
      // research, and the model is not asked to write a file the server can write itself.
      ...(options.noTools ? ["--no-tools"] : []),
      "--provider",
      "sympozium",
      "--model",
      process.env.MODEL_NAME,
      // The level is only a key into the model's thinkingLevelMap, which turns it
      // into `reasoning_effort: none`; without a non-off level Pi sends no effort
      // and the model reasons until it hits the token cap and returns nothing.
      "--thinking",
      process.env.PI_WRITER_THINKING || "minimal",
      "--session-id",
      sessionID,
      "--session-dir",
      sessionDir,
      prompt,
    ];
    // The turn's own tooling needs to know which session it is: `check-article` resolves the
    // transcript from these to prove a block against what the run actually read, and the
    // auditor greps the same file for a claim it has to settle.
    const child = spawn("pi", args, {
      cwd,
      env: {
        ...process.env,
        PI_WRITER_SESSION_ID: sessionID,
        PI_WRITER_SESSION_DIR: sessionDir,
        // Per turn, because the run directory outlives a budget edit: a retry must read the
        // row's current limit, and `check-article` is the count the writer is held to.
        ...(Number(options.budget) > 0 ? { PI_WRITER_MAX_WORDS: String(options.budget) } : {}),
        ...(options.sessionFile ? { PI_WRITER_SESSION_FILE: options.sessionFile } : {}),
      },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let output = "";
    let stderr = "";
    let exceeded = false;
    let cancelled = false;
    const cancel = () => {
      cancelled = true;
      child.kill("SIGTERM");
    };
    if (signal?.aborted) cancel();
    else signal?.addEventListener("abort", cancel, { once: true });
    const collect = (chunk, outputStream) => {
      if (output.length + stderr.length + chunk.length > maxOutput) {
        exceeded = true;
        child.kill("SIGTERM");
        return;
      }
      if (outputStream) {
        output += chunk;
        onOutput?.(chunk);
      } else {
        stderr += chunk;
      }
    };
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk) => collect(chunk, true));
    child.stderr.on("data", (chunk) => collect(chunk, false));
    child.on("error", reject);
    child.on("close", (code) => {
      signal?.removeEventListener("abort", cancel);
      if (cancelled) return reject(new Error("request cancelled"));
      if (exceeded) return reject(new Error("adapter output exceeded 2 MB"));
      if (code !== 0) return reject(piFailure(code, stderr));
      if (!output.trim()) return reject(new Error("Pi returned an empty response"));
      resolve(output.trim());
    });
  });
}

function writeSSE(res, value) {
  if (!res.writableEnded) res.write(`data: ${JSON.stringify(value)}\n\n`);
}

// One turn at a time per session: Pi's session file is a shared resource and concurrent
// turns against it interleave. Two rows are different sessions with different files and
// directories, so they must not queue behind each other — a row that waits out another row's
// twenty-minute turn is what outlived the caller's deadline and lost its draft.
const sessionQueues = new Map();
function serializeTurn(sessionID, run) {
  const previous = sessionQueues.get(sessionID) ?? Promise.resolve();
  const next = previous.catch(() => undefined).then(run);
  sessionQueues.set(sessionID, next);
  next
    .catch(() => undefined)
    .finally(() => {
      if (sessionQueues.get(sessionID) === next) sessionQueues.delete(sessionID);
    });
  return next;
}

// ---------------------------------------------------------------------------
// The source allowlist proxy.
//
// An instruction is not enforcement, and the CNI here is not FQDN-aware, so the
// allowlist lives in front of the tools: `curl` in a bash tool honours
// `HTTPS_PROXY`, and anything off the list answers 403 here with the host logged.
// The list is per turn because the caller names the hosts, and more than one row may be
// in flight: the proxy admits only hosts every active turn declared, so a turn that names
// fewer hosts can never be widened by a neighbour that names more.
const turnHosts = new Set();

function allowHosts(hosts) {
  const key = JSON.stringify(Array.isArray(hosts) ? hosts : []);
  turnHosts.add(key);
  return () => turnHosts.delete(key);
}

function activeHosts() {
  if (!turnHosts.size) return null;
  return [...turnHosts]
    .map((key) => JSON.parse(key))
    .reduce((allowed, hosts) => allowed.filter((host) => hosts.includes(host)));
}

function proxyRefusal(host, { protocol = "https:", port = "443" } = {}) {
  const articleHosts = activeHosts();
  if (!articleHosts) return "no turn is fetching";
  // The instruction says https on 443, and the server's own ledger fetch enforces the same.
  // A proxy that forwarded plain http or another port would be a wider gate than the one
  // the ledger is verified against.
  if (protocol !== "https:") return "not https";
  if (String(port) !== "443") return `port ${port} is not 443`;
  // The same address policy as the server's own fetch: a caller that declares a private
  // or loopback host does not make it reachable, or the two gates disagree on what may
  // be read.
  if (isBlockedHostname(host)) return `host ${host} is private or loopback`;
  if (!hostAllowed(host, articleHosts)) return `host ${host} is not a declared source host`;
  return null;
}

function splitHostPort(value) {
  const text = String(value || "");
  if (text.startsWith("[")) {
    const end = text.indexOf("]");
    return [text.slice(1, end), text.slice(end + 2)];
  }
  const colon = text.lastIndexOf(":");
  return colon < 0 ? [text, "443"] : [text.slice(0, colon), text.slice(colon + 1)];
}

function refuseThroughProxy(host, reason, res) {
  console.log(`sympozium pi writer session: refused ${host} through the source proxy: ${reason}`);
  if (res && !res.headersSent) {
    res.writeHead(403, { "content-type": "text/plain" }).end(`blocked source host: ${host}`);
  }
}

const proxyServer = http.createServer((req, res) => {
  let target;
  try {
    target = new URL(req.url?.startsWith("http") ? req.url : `http://${req.headers.host}${req.url}`);
  } catch {
    res.writeHead(400).end();
    return;
  }
  const refusal = proxyRefusal(target.hostname, {
    protocol: target.protocol,
    port: target.port || (target.protocol === "https:" ? "443" : "80"),
  });
  if (refusal) {
    refuseThroughProxy(target.hostname, refusal, res);
    return;
  }
  const upstream = http.request(
    {
      protocol: target.protocol,
      hostname: target.hostname,
      port: target.port || 80,
      path: `${target.pathname}${target.search}`,
      method: req.method,
      headers: { ...req.headers, host: target.host },
    },
    (answer) => {
      res.writeHead(answer.statusCode || 502, answer.headers);
      answer.pipe(res);
    }
  );
  upstream.on("error", (err) => {
    if (!res.headersSent) res.writeHead(502);
    res.end(String(err?.message ?? err));
  });
  req.pipe(upstream);
});

proxyServer.on("connect", (req, socket, head) => {
  const [host, port] = splitHostPort(req.url);
  const refusal = proxyRefusal(host, { protocol: "https:", port });
  if (refusal) {
    console.log(`sympozium pi writer session: refused ${host} through the source proxy: ${refusal}`);
    // A client that gave up already is normal: an unhandled write error on this socket would
    // take the whole session server down with it, and the refusal is the answer either way.
    socket.on("error", () => {});
    socket.end("HTTP/1.1 403 Forbidden\r\n\r\n");
    return;
  }
  const upstream = net.connect(Number(port) || 443, host, () => {
    socket.write("HTTP/1.1 200 Connection Established\r\n\r\n");
    upstream.write(head);
    upstream.pipe(socket);
    socket.pipe(upstream);
  });
  upstream.on("error", () => socket.destroy());
  socket.on("error", () => upstream.destroy());
});

await new Promise((resolve) => proxyServer.listen(proxyPort, "127.0.0.1", resolve));
console.log(`sympozium pi writer session: source proxy listening on 127.0.0.1:${proxyPort}`);

// The model endpoint must never go through the proxy: the allowlist is about source
// pages, and a proxied model call would be refused as an undeclared host. Cluster
// names and loopback are excluded for the same reason.
const modelHost = (() => {
  try {
    return new URL(process.env.MODEL_BASE_URL).hostname;
  } catch {
    return "";
  }
})();
process.env.NO_PROXY = ["127.0.0.1", "localhost", "::1", modelHost, ".svc", ".cluster.local"]
  .filter(Boolean)
  .join(",");

function proxyEnv(hosts) {
  if (!hosts) {
    for (const name of ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]) delete process.env[name];
    return;
  }
  const url = `http://127.0.0.1:${proxyPort}`;
  for (const name of ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]) process.env[name] = url;
}

// After a turn: the ledger's every URL is fetched here, the entries whose URL does
// not answer are dropped, and the file is rewritten with what the server saw.
// When a file was last written, 0 when it does not exist. A draft turn is supposed to write
// both artifacts; a model that answers in text instead leaves the previous attempt's files in
// place, and the caller then fetches them as if this run had produced them.
async function artifactMtime(path) {
  try {
    return (await stat(path)).mtimeMs;
  } catch {
    return 0;
  }
}

// The draft of record for this turn: the file it wrote, or the `<article>` block it answered
// with when it wrote none. A turn that did neither fails by name rather than handing back the
// last attempt's article.
async function adoptDraft(dir, response, before) {
  const wrote = (await artifactMtime(join(dir, ARTICLE_NAME))) > before.article;
  if (wrote) return;
  // The instruction is explicit: a draft answers inside one `<article>` block and writes the
  // files. Only that block is adopted; bare prose is not a draft, and a truncated answer of a
  // single character is the case that made this worth being strict about.
  if (/<article>[\s\S]*?<\/article>/.test(String(response ?? ""))) {
    const answered = splitArticle(response);
    if (answered.text) {
      console.log("sympozium pi writer session: the turn answered without writing article.md; adopting the answer");
      await writeArticle(dir, answered);
      return;
    }
  }
  // A turn may answer with the article itself, unwrapped. The H1 and a body's length are the
  // shape; a meta answer ("nothing changed since the last pass") or a truncated one has neither,
  // which is the case the strict rule was added for and still rejects.
  const plain = String(response ?? "").trim();
  if (/^#\s+\S/m.test(plain) && plain.length >= 600) {
    console.log("sympozium pi writer session: the turn answered with the article unwrapped; adopting it");
    await writeArticle(dir, splitArticle(plain));
    return;
  }
  throw new Error("the draft turn answered without writing article.md");
}

// The ledger, derived rather than declared: the transcript holds every page this session
// scraped and the text the model received, so a fence is quoted when it appears in that text
// and unquoted when it does not. No fetch is repeated to prove a page the pod already read.
async function writeDerivedLedger(dir, sessionID) {
  const path = join(dir, LEDGER_NAME);
  let article;
  try {
    article = await readFile(join(dir, ARTICLE_NAME), "utf8");
  } catch {
    article = "";
  }
  const pages = await transcriptPages(await readTranscript(sessionID));
  const { sources, unquoted, unquotedBlocks } = deriveLedger({ article, pages });
  for (const block of unquotedBlocks ?? []) {
    console.log(`sympozium pi writer session: block not in ${LEDGER_NAME}: ${block.firstLine}${block.reason ? ` (${block.reason})` : ""}`);
  }
  await writeFile(path, serialiseLedger(sources));
  return {
    sources: sources.length,
    quoted: sources.filter((entry) => entry.mode === "quoted").length,
    derived: sources.filter((entry) => entry.mode === "derived").length,
    unquoted,
    unquotedBlocks: unquotedBlocks ?? [],
    // The URLs the session actually read: the auditor names one of these as the fix, and a
    // page outside it has to be fetched before its block can be quoted.
    pages: [...new Set(pages.map((page) => page.url))],
    dropped: [],
    error: pages.length ? "" : "the turn scraped no page, so no block can be quoted",
  };
}

// Pi appends one JSONL file per session id; the newest is this run's.
async function transcriptFile(sessionID) {
  let names;
  try {
    names = await readdir(sessionDir);
  } catch {
    return "";
  }
  const files = names.filter((name) => name.endsWith(`_${sessionID}.jsonl`)).sort();
  return files.length ? join(sessionDir, files.at(-1)) : "";
}

async function readTranscript(sessionID) {
  const file = await transcriptFile(sessionID);
  if (!file) return [];
  const rows = [];
  for (const line of (await readFile(file, "utf8")).split("\n")) {
    if (!line.trim()) continue;
    try {
      rows.push(JSON.parse(line));
    } catch {
      // A transcript cut off mid-line is not evidence, and it is not an error either.
    }
  }
  return rows;
}

// The aspect registry is the one list of reviewers. Validate it before serving: a missing or
// empty registry would otherwise answer every aspect turn with an empty findings list, and
// the article would improve on nothing while every request looked healthy.
loadAspects().catch((err) => {
  console.error(`sympozium pi writer session: article_aspects.json is unusable: ${err?.message ?? err}`);
  process.exit(1);
});

http
  .createServer(async (req, res) => {
    if (req.method === "GET" && req.url === "/healthz") {
      res.writeHead(200).end("ok");
      return;
    }
    // The two files a workflow fetches after authoring. Only files this server
    // writes, under their own run directory, are reachable.
    const artifactMatch = req.method === "GET" && req.url.match(/^\/artifacts\/([^/]+)\/([^/]+)$/);
    if (artifactMatch) {
      let sessionId;
      let name;
      try {
        sessionId = decodeURIComponent(artifactMatch[1]);
        name = decodeURIComponent(artifactMatch[2]);
      } catch {
        res.writeHead(400).end();
        return;
      }
      const file = resolveArtifact(workDir, sessionId, name);
      if (!file) {
        res.writeHead(404).end();
        return;
      }
      try {
        const info = await stat(file);
        res.writeHead(200, { "content-type": contentTypeFor(name), "content-length": info.size });
        createReadStream(file).pipe(res);
      } catch {
        res.writeHead(404).end();
      }
      return;
    }
    if (req.method !== "POST" || req.url !== "/v1/chat/completions") {
      res.writeHead(404).end();
      return;
    }
    try {
      const request = await readJSON(req);
      const task = taskOf(request);
      const lane = laneOf(request);
      // `brief` is both lanes' shape; `messages` stays for a plain-text caller and for the
      // contract's own smoke checks.
      const brief = request.brief && typeof request.brief === "object" ? request.brief : null;
      if (lane === "article" && task === "draft" && !brief && !Array.isArray(request.messages)) {
        throw new Error("a draft needs brief or messages");
      }
      if (lane === "post") {
        if (!brief) throw new Error("a post turn needs a brief");
        if (task !== "draft" && task !== "review") throw new Error(`the post lane has no ${task} task`);
        if (task === "review" && !String(request.post?.text ?? "").trim()) {
          throw new Error("a post review needs post.text");
        }
      }
      const sessionID = safeSessionId(request.session_id);
      const hosts = parseSourceHosts(request.source_hosts);
      // Streaming is the article drafting turn's shape. A post draft is one short answer and
      // a review is structured, so neither streams.
      const stream = lane === "article" && request.stream === true && task === "draft";
      const id = `chatcmpl-${randomUUID()}`;
      const cancellation = new AbortController();
      let clientGone = false;
      res.once("close", () => {
        if (res.writableEnded) return;
        clientGone = true;
        // A draft is the artifact, not the answer: finishing it after the caller's timeout is
        // what lets the next attempt adopt the work instead of paying for it again. Every
        // other turn exists only in its response, so a hung-up caller cancels it.
        if (task !== "draft") cancellation.abort();
      });
      if (stream) {
        res.writeHead(200, {
          "content-type": "text/event-stream",
          "cache-control": "no-cache",
          connection: "keep-alive",
          "x-accel-buffering": "no",
        });
      }

      // One directory per session: a reused session continues in place, and a fresh
      // one is isolated so sequential turns never overwrite each other's artifacts.
      const dir = resolveRunDir(workDir, sessionID);
      await mkdir(dir, { recursive: true });
      const draftPrompt =
        lane === "article" && task === "draft"
          ? brief
            ? await articlePrompt(brief)
            : promptFrom(request.messages)
          : "";

      // The ledger verification runs inside the serialized turn, not after it: a second
      // request for the same session would otherwise start its turn while this one is
      // reading and rewriting `sources.json`.
      const result = await serializeTurn(sessionID, async () => {
          if (lane === "post") {
            // The post lane fetches nothing: the source text is on the brief, so no proxy,
            // no allowlist and no artifact. The chosen directives are read back from the
            // run directory, which is what makes the gate judge the drafter's own shape.
            proxyEnv(null);
            const direct = brief || {};
            const chosen = await resolvePostDirectives(dir, direct);
            if (task === "draft") {
              const prompt = await postDraftPrompt({ brief: direct, directives: chosen.directives });
              const response = await runPi(prompt, sessionID, undefined, cancellation.signal, dir, {
                noTools: true,
              });
              return {
                response,
                post: { text: postDraftAnswer(response), directives: chosen.directives },
              };
            }
            const prompt = await postReviewPrompt({
              brief: direct,
              text: String(request.post?.text ?? "").trim(),
              directives: chosen.directives,
            });
            const response = await runPi(prompt, sessionID, undefined, cancellation.signal, dir, {
              noTools: true,
            });
            return { response, post: { text: postReviewAnswer(response) } };
          }

          if (task === "draft") {
            // The instruction follows the directory: a session that already holds an article
            // is edited, a fresh one is authored. The caller starts every attempt in its own
            // session now, so `attempt > 1` no longer means "edit what is here" — a retry
            // carries the previous draft in its brief instead.
            const isIteration = await exists(join(dir, ARTICLE_NAME));
            const method = fillSourceHosts(await writingMethod(), hosts);
            const instruction = articleTurnInstruction({ isIteration });
            const turnPrompt = `${draftPrompt}\n\n---\n\nWorking directory: ${dir}\n${instruction}\n\n${method}`;
            const release = allowHosts(hosts);
            proxyEnv(hosts);
            const before = { article: await artifactMtime(join(dir, ARTICLE_NAME)) };
            try {
              const response = await runPi(
                turnPrompt,
                sessionID,
                stream
                  ? (chunk) =>
                      writeSSE(res, {
                        id,
                        object: "chat.completion.chunk",
                        created: Math.floor(Date.now() / 1000),
                        model: process.env.MODEL_NAME,
                        choices: [{ index: 0, delta: { content: chunk }, finish_reason: null }],
                      })
                  : undefined,
                cancellation.signal,
                dir,
                { budget: brief?.max_words }
              );
              await adoptDraft(dir, response, before);
              return { response, ledger: await writeDerivedLedger(dir, sessionID) };
            } finally {
              release();
              proxyEnv(null);
            }
          }

          // A review or an edit reads the draft the caller resolved and answers in its
          // response. No proxy by default: a turn that may not research cannot reach a page.
          proxyEnv(null);
          const article = await resolveArticle(request, dir);
          if (task === "audit") {
            // The gate runs first so the auditor argues with a list instead of guessing. A
            // block no page carries is named here with its own text and the pages the session
            // read, so the finding is the fix the retry applies rather than the gate's first
            // line handed back to a writer that cannot tell which block it means.
            const ledger = await writeDerivedLedger(dir, sessionID);
            // The audit reads the artifacts, not the writer's conversation. A fresh session keeps
            // its prompt to the article, the gate list and the prompts themselves, instead of
            // re-sending a 500k-token draft transcript — which is what made this turn take ten
            // minutes and outlive the caller's review timeout. Its evidence is unchanged: the
            // writer's transcript file is named in the prompt and it greps that.
            const auditSession = `${sessionID.slice(0, 70)}-audit`;
            let response;
            const release = allowHosts(hosts);
            proxyEnv(hosts);
            try {
              const prompt = await auditPrompt({
                brief: brief || {},
                article,
                unquoted: ledger.unquotedBlocks,
                pages: ledger.pages,
                sessionFile: await transcriptFile(sessionID),
              });
              response = await runPi(prompt, auditSession, undefined, cancellation.signal, dir, {
                sessionFile: await transcriptFile(sessionID),
              });
            } finally {
              release();
              proxyEnv(null);
            }
            const verdict = parseReview(response);
            const findings = parseFindings(response);
            const explanation = [verdict.explanation, findings.text].filter(Boolean).join(" ");
            return {
              response,
              // A draft the gate rejects does not pass, whatever the auditor concluded: the
              // count is code's, and a pass here would tell the writer the draft is fine in the
              // same breath as the gate naming blocks that cannot publish.
              review: { pass: verdict.pass && ledger.unquoted.length === 0, explanation },
              findings: [{ aspect: "audit", focus: "unsupported claims, the ask, educative value", error: "", ...findings }],
            };
          }
          if (task === "review") {
            const prompt = await reviewPrompt({ brief: brief || {}, article });
            const response = await runPi(prompt, sessionID, undefined, cancellation.signal, dir, { noTools: true });
            return { response, review: parseReview(response) };
          }
          if (task === "aspects") {
            const aspects = await loadAspects();
            const findings = [];
            for (const aspect of aspects) {
              let text = "";
              let error = "";
              try {
                const prompt = await aspectPrompt(aspect, { brief: brief || {}, article });
                text = await runPi(prompt, sessionID, undefined, cancellation.signal, dir, { noTools: true });
              } catch (err) {
                // One reviewer that cannot answer records no findings and the rest run,
                // because its findings are advice to the edit, not a gate.
                error = String(err?.message ?? err);
              }
              findings.push({ aspect: aspect.id, focus: aspect.focus, error, ...parseFindings(text) });
            }
            return { response: findings.map((finding) => finding.text).filter(Boolean).join("\n\n"), findings };
          }
          const prompt = await improvePrompt({
            brief: brief || {},
            article,
            findings: request.findings,
            problem: request.problem,
            hosts,
          });
          // The edit may fetch, because the fix the audit names is often a page: a block it
          // must quote cannot be written from memory, and this turn is where the gate's last
          // findings are applied. Same allowlist and same budget as the draft.
          let response;
          const release = allowHosts(hosts);
          proxyEnv(hosts);
          try {
            response = await runPi(prompt, sessionID, undefined, cancellation.signal, dir, {
              budget: brief?.max_words,
            });
          } finally {
            release();
            proxyEnv(null);
          }
          const edited = splitArticle(response);
          if (!edited.text) throw new Error("the improve turn returned no <article> block");
          await writeArticle(dir, { title: edited.title || article.title, text: edited.text });
          // The edit rewrote the article, so the ledger it was drafted with no longer describes
          // it: a block it dropped would keep a stale entry and a block it added would be
          // reported against a page that never carried it. Re-derive against this text.
          return { response, ledger: await writeDerivedLedger(dir, sessionID) };
        });

      await sweepIfDue(sessionID);

      if (stream) {
        if (clientGone) return;
        writeSSE(res, {
          id,
          object: "chat.completion.chunk",
          created: Math.floor(Date.now() / 1000),
          model: process.env.MODEL_NAME,
          choices: [{ index: 0, delta: {}, finish_reason: "stop" }],
        });
        if (!res.writableEnded) res.end("data: [DONE]\n\n");
        return;
      }
      if (clientGone) {
        // The article's work is done and on disk; only the answer had nowhere to go. The
        // caller's next attempt continues this session and adopts the artifacts. A post has
        // no artifact, so the turn is lost and the next attempt drafts again.
        console.log(
          lane === "post"
            ? "sympozium pi writer session: the caller hung up; the post turn finished with nowhere to answer"
            : "sympozium pi writer session: the caller hung up; the turn finished and its artifacts are on disk"
        );
        return;
      }
      const payload = {
        id,
        object: "chat.completion",
        created: Math.floor(Date.now() / 1000),
        model: process.env.MODEL_NAME,
        task,
        choices: [{ index: 0, message: { role: "assistant", content: result.response }, finish_reason: "stop" }],
      };
      if (lane === "post") payload.post = result.post;
      else payload.article = await articleAnswer(dir, result.ledger);
      if (result.review) payload.review = result.review;
      if (result.findings) payload.findings = result.findings;
      const body = JSON.stringify(payload);
      res.writeHead(200, { "content-type": "application/json", "content-length": Buffer.byteLength(body) }).end(body);
    } catch (err) {
      const message = err instanceof Error ? err.message : "session request failed";
      // A pre-turn failure leaves no trace in Pi's own output, and the caller only
      // sees a 400 it may not record -- so the pod log is the operator's only
      // evidence of why a turn never started.
      console.error(`sympozium pi writer session: turn failed: ${message}`);
      if (res.headersSent) {
        writeSSE(res, { error: { message, type: "harness_session_error" } });
        if (!res.writableEnded) res.end("data: [DONE]\n\n");
        return;
      }
      const body = JSON.stringify({ error: { message, type: "harness_session_error" } });
      res.writeHead(400, { "content-type": "application/json", "content-length": Buffer.byteLength(body) }).end(body);
    }
  })
  .listen(port, "0.0.0.0", () => console.log(`sympozium pi writer session listening on ${port}`));
