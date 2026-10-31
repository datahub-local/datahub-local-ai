// GitHub App installation-token minter for the opencode-server Pod.
//
// The OpenCode container is the agent's shell, so it must not hold the App key or
// a personal access token: anything it can read, the agent can read and, with a
// proxy in front, send. This sidecar holds the key, mints a token, and serves it
// on loopback. Nothing is written to disk, so a session that lives for days still
// gets a token minted at the moment git asks for one.
//
// Node and curl are both in the adapter image, which is why this runs there: the
// JWT needs RSA signing (node:crypto) and the exchange must honour HTTPS_PROXY
// (curl does; node's fetch does not).
import { spawn } from "node:child_process";
import crypto from "node:crypto";
import http from "node:http";

const appId = process.env.GITHUB_APP_ID;
const installationId = process.env.GITHUB_APP_INSTALLATION_ID;
// A Secret value is one line, so a PEM arrives with literal \n escapes.
const privateKey = (process.env.GITHUB_APP_PRIVATE_KEY ?? "").replace(/\\n/g, "\n");
const port = Number(process.env.MINTER_PORT ?? 8787);
// Re-mint while there is still time left: an hour-long token with ten minutes to
// run is not worth handing to a git process that may then sit in a long push.
const refreshMarginMs = 10 * 60 * 1000;

if (!appId || !installationId || !privateKey) {
  console.error("minter: GITHUB_APP_ID, GITHUB_APP_INSTALLATION_ID and GITHUB_APP_PRIVATE_KEY are required");
  process.exit(1);
}

let cached = null;

function appJwt() {
  const now = Math.floor(Date.now() / 1000);
  const header = Buffer.from(JSON.stringify({ alg: "RS256", typ: "JWT" })).toString("base64url");
  // GitHub rejects a lifetime over ten minutes; backdating `iat` absorbs clock skew.
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
      'header = "User-Agent: opencode-minter"',
      "",
    ].join("\n"),
  );
  const parsed = JSON.parse(body);
  if (!parsed.token || !parsed.expires_at) {
    throw new Error(`unexpected token response: ${body.slice(0, 200)}`);
  }
  return { token: parsed.token, expiresAt: Date.parse(parsed.expires_at) };
}

const server = http.createServer(async (req, res) => {
  if (req.method === "GET" && req.url === "/healthz") {
    res.writeHead(200, { "content-type": "text/plain" }).end("ok");
    return;
  }
  if (req.method !== "GET" || req.url !== "/token") {
    res.writeHead(404).end();
    return;
  }
  try {
    if (!cached || cached.expiresAt - Date.now() < refreshMarginMs) cached = await mint();
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ token: cached.token, expires_at: new Date(cached.expiresAt).toISOString() }));
  } catch (error) {
    // The reason is logged, never returned: it can quote the App key's subject.
    console.error(`minter: ${error.message}`);
    res.writeHead(502, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: "token mint failed" }));
  }
});

server.listen(port, "127.0.0.1", () => {
  console.log(`minter: listening on 127.0.0.1:${port}`);
});
