// GitHub App token proxy for the manager identity.
//
// github-mcp-server in http mode authenticates **per request** from the
// Authorization header and ignores GITHUB_PERSONAL_ACCESS_TOKEN, so there is no
// env var or file to feed it. Something has to put a token on each request, and
// that something must hold the App key instead of the caller. This is it: it
// mints an installation token, caches it until ten minutes before it expires,
// and forwards to the MCP server on loopback with the header set.
//
// curl, not fetch: the mint call has to honour HTTPS_PROXY, and Node's fetch
// ignores the proxy environment variables.
import { spawn } from "node:child_process";
import crypto from "node:crypto";
import http from "node:http";

import { upstreamHeaders } from "./mcp-forward.mjs";

const appId = process.env.GITHUB_APP_ID;
const installationId = process.env.GITHUB_APP_INSTALLATION_ID;
const privateKey = (process.env.GITHUB_APP_PRIVATE_KEY ?? "").replace(/\\n/g, "\n");
const port = Number(process.env.PROXY_PORT ?? 8080);
const upstreamPort = Number(process.env.UPSTREAM_PORT ?? 8081);
const refreshMarginMs = 10 * 60 * 1000;

if (!appId || !installationId || !privateKey) {
  console.error(
    "github-proxy: GITHUB_APP_ID, GITHUB_APP_INSTALLATION_ID and GITHUB_APP_PRIVATE_KEY are required",
  );
  process.exit(1);
}

let cached = null;

function appJwt() {
  const now = Math.floor(Date.now() / 1000);
  const header = Buffer.from(JSON.stringify({ alg: "RS256", typ: "JWT" })).toString("base64url");
  // GitHub refuses a lifetime over ten minutes; backdating `iat` absorbs clock skew.
  const payload = Buffer.from(
    JSON.stringify({ iat: now - 60, exp: now + 540, iss: appId }),
  ).toString("base64url");
  const signature = crypto.sign("RSA-SHA256", Buffer.from(`${header}.${payload}`), privateKey);
  return `${header}.${payload}.${signature.toString("base64url")}`;
}

// The Authorization header carries a short-lived JWT, so it is passed on stdin
// rather than argv, which /proc exposes to every process in the container.
function curl(config) {
  return new Promise((resolve, reject) => {
    const child = spawn("curl", ["--config", "-"], { stdio: ["pipe", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => (stdout += chunk));
    child.stderr.on("data", (chunk) => (stderr += chunk));
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve(stdout);
      else reject(new Error(`curl exited ${code}: ${stderr.trim()}`));
    });
    child.stdin.end(config);
  });
}

async function mint() {
  const body = await curl(
    [
      "silent",
      "show-error",
      "fail-with-body",
      "max-time = 20",
      "request = POST",
      `url = "https://api.github.com/app/installations/${installationId}/access_tokens"`,
      'header = "Accept: application/vnd.github+json"',
      `header = "Authorization: Bearer ${appJwt()}"`,
      'header = "User-Agent: datahub-local-github-proxy"',
      "",
    ].join("\n"),
  );
  const parsed = JSON.parse(body);
  if (!parsed.token || !parsed.expires_at) {
    throw new Error(`unexpected token response: ${body.slice(0, 200)}`);
  }
  return { token: parsed.token, expiresAt: Date.parse(parsed.expires_at) };
}

async function token() {
  if (cached && cached.expiresAt - Date.now() > refreshMarginMs) return cached.token;
  cached = await mint();
  return cached.token;
}

const server = http.createServer((req, res) => {
  // Answer the probe without minting: a pod whose App key is wrong should still
  // start and report the failure on the first real call, not crash-loop.
  if (req.url === "/healthz") {
    res.writeHead(200, { "content-type": "text/plain" });
    res.end("ok\n");
    return;
  }

  token()
    .then((value) => {
      const headers = upstreamHeaders(req.headers, value, upstreamPort);
      const upstream = http.request(
        { host: "127.0.0.1", port: upstreamPort, path: req.url, method: req.method, headers },
        (answer) => {
          res.writeHead(answer.statusCode ?? 502, answer.headers);
          answer.pipe(res);
        },
      );
      upstream.on("error", (error) => {
        console.error(`github-proxy: upstream failed: ${error.message}`);
        if (!res.headersSent) res.writeHead(502, { "content-type": "text/plain" });
        res.end(`upstream failed: ${error.message}\n`);
      });
      req.pipe(upstream);
    })
    .catch((error) => {
      console.error(`github-proxy: mint failed: ${error.message}`);
      if (!res.headersSent) res.writeHead(502, { "content-type": "text/plain" });
      res.end(`mint failed: ${error.message}\n`);
    });
});

// SSE sessions are long-lived: no timeout may cut them.
server.requestTimeout = 0;
server.headersTimeout = 0;
server.listen(port, "0.0.0.0", () => {
  console.log(`github-proxy: listening on ${port} -> 127.0.0.1:${upstreamPort}`);
});
